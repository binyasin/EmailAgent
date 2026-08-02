"""Thin client for talking to a *running* tenant cell's OpenClaw Gateway.

Per docs/openclaw-integration-notes.md — verified against
docs.openclaw.ai/gateway/protocol, /gateway/external-apps, /reference/rpc, and
(since the docs site alone left auth ambiguous) the OpenClaw source itself
(github.com/openclaw/openclaw) — the Gateway's client-facing surface is
WebSocket RPC protocol v4: connect over `ws://host:port/` (the core Gateway
upgrade handler doesn't route on path — only plugin/node-capability scoped
paths are special-cased in `attachGatewayUpgradeHandler`), receive a
`{type: "event", event: "connect.challenge", payload: {nonce, ts}}` frame,
reply with a `connect` request, then get `hello-ok`. Frames are text-JSON
`{type: "req", id, method, params}` -> `{type: "res", id, ok, payload}` or
`{..., ok: false, error: {code, message, ...}}`.

Despite an earlier pass concluding device-keypair signing was mandatory for
every connection, the source contradicts that: `verifyGatewayConnectDeviceProof`
(`src/gateway/server/ws-connection/connect-device-proof.ts`) explicitly
accepts an absent `device` object, and `buildDeviceConnectParams`
(`packages/gateway-client/src/client.ts`) only sends one when a device
identity is configured. Plain `auth.token` (shared secret) is a first-class
auth method (`src/gateway/auth.ts`), and the only connect-handshake roles are
`"operator"`/`"node"` (`"worker"` in an earlier docs-search summary is an
unrelated low-level protocol for local inference workers). So this client
connects as `role: "operator"` with `auth.token = gateway_token` and no
device — no keypair, no pairing/approval flow.

`is_live`/`is_ready` probe HTTP `/healthz`/`/readyz` — also confirmed
directly from source (`src/gateway/gateway-http-route-contracts.ts`'s
`GATEWAY_PROBE_ROUTES`), so despite the WS protocol docs only describing a
`health` RPC method, these HTTP routes are real.

Still open: whether `role: "operator"` with only a shared token is granted
the scopes needed to call `agent`/`agent.wait` by default, or whether some
Gateway auth configurations require more — not confirmed from source in this
pass. If `trigger_run`/`stream_session_events` fail with a scope/permission
error against a real cell, that's the first thing to check.
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets

GATEWAY_PROTOCOL_VERSION = 4
_CLIENT_ID = "emailagent-control-plane"
_CLIENT_VERSION = "0.1.0"


class GatewayRPCError(RuntimeError):
    """Raised when the Gateway answers a request frame with `ok: false`."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details
        super().__init__(f"{code}: {message}")


class GatewayProtocolError(RuntimeError):
    """Raised when a frame doesn't match the expected connect/RPC envelope shape."""


class GatewayClient:
    def __init__(self, *, host: str, port: int, gateway_token: str, timeout_seconds: float = 5.0):
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/"
        self._gateway_token = gateway_token
        self._timeout = timeout_seconds

    def is_live(self) -> bool:
        try:
            res = httpx.get(f"{self.base_url}/healthz", timeout=self._timeout)
            return res.status_code == 200
        except httpx.HTTPError:
            return False

    def is_ready(self) -> bool:
        try:
            res = httpx.get(f"{self.base_url}/readyz", timeout=self._timeout)
            return res.status_code == 200
        except httpx.HTTPError:
            return False

    async def _connect(self) -> websockets.ClientConnection:
        ws = await websockets.connect(self.ws_url, open_timeout=self._timeout)
        try:
            challenge = json.loads(await ws.recv())
        except Exception:
            await ws.close()
            raise
        if challenge.get("type") != "event" or challenge.get("event") != "connect.challenge":
            await ws.close()
            raise GatewayProtocolError(f"expected connect.challenge, got {challenge!r}")

        connect_frame = {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "connect",
            "params": {
                "minProtocol": GATEWAY_PROTOCOL_VERSION,
                "maxProtocol": GATEWAY_PROTOCOL_VERSION,
                "client": {
                    "id": _CLIENT_ID,
                    "version": _CLIENT_VERSION,
                    "platform": "server",
                    "mode": "operator",
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": {"token": self._gateway_token},
                "locale": "en-US",
                "userAgent": f"{_CLIENT_ID}/{_CLIENT_VERSION}",
            },
        }
        try:
            await ws.send(json.dumps(connect_frame))
            hello = json.loads(await ws.recv())
        except Exception:
            await ws.close()
            raise
        if hello.get("type") != "res" or hello.get("id") != connect_frame["id"]:
            await ws.close()
            raise GatewayProtocolError(f"expected connect response, got {hello!r}")
        if not hello.get("ok"):
            error = hello.get("error", {})
            await ws.close()
            raise GatewayRPCError(
                error.get("code", "CONNECT_FAILED"),
                error.get("message", "connect rejected"),
                error.get("details"),
            )
        return ws

    async def _request(
        self, ws: websockets.ClientConnection, method: str, params: dict[str, Any]
    ) -> Any:
        request_id = str(uuid.uuid4())
        await ws.send(json.dumps({"type": "req", "id": request_id, "method": method, "params": params}))
        # Event frames (broadcasts unrelated to this request) may interleave with our
        # response on the same socket — skip them while waiting for our matching id.
        while True:
            frame = json.loads(await ws.recv())
            if frame.get("type") == "res" and frame.get("id") == request_id:
                if not frame.get("ok"):
                    error = frame.get("error", {})
                    raise GatewayRPCError(
                        error.get("code", "UNKNOWN"),
                        error.get("message", f"{method} failed"),
                        error.get("details"),
                    )
                return frame.get("payload")

    async def trigger_run(self, *, agent_id: str, prompt: str) -> dict[str, Any]:
        """Start an agent run and block for its terminal result, per the documented
        `agent` + `agent.wait` pairing (docs.openclaw.ai/gateway/external-apps)."""
        ws = await self._connect()
        try:
            started = await self._request(ws, "agent", {"agentId": agent_id, "prompt": prompt})
            run_id = started.get("runId") if isinstance(started, dict) else None
            if not run_id:
                raise GatewayProtocolError(f"agent RPC response missing runId: {started!r}")
            return await self._request(ws, "agent.wait", {"runId": run_id})
        finally:
            await ws.close()

    async def stream_session_events(
        self, *, session_key: str, include_approvals: bool = False
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a session's broadcast events (`chat`, `session.message`,
        `session.operation`, `session.observer`) via `sessions.messages.subscribe`."""
        ws = await self._connect()
        try:
            await self._request(
                ws,
                "sessions.messages.subscribe",
                {"sessionKey": session_key, "includeApprovals": include_approvals},
            )
            async for raw in ws:
                frame = json.loads(raw)
                if frame.get("type") == "event":
                    yield frame
        finally:
            await ws.close()
