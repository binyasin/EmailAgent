"""Thin client for talking to a *running* tenant cell's OpenClaw Gateway.

Per docs/openclaw-integration-notes.md (verified against
docs.openclaw.ai/gateway/protocol and /gateway/external-apps), the Gateway's
client-facing surface is WebSocket RPC protocol v4 — a pre-connect
challenge/nonce handshake, then a `connect` request (role, scopes, auth
token or password) answered with `hello-ok`. There is no confirmation that
plain HTTP `/healthz`/`/readyz` probes exist for this protocol — the
protocol docs describe a WS-only `health` RPC method instead. `is_live`/
`is_ready` below are kept as a best-effort HTTP fallback (plausible for a
container-level liveness probe) but are UNVERIFIED and may need replacing
with the `health` RPC once a WS client exists here.

The RPC methods needed for Phase 3+ are now known by name (though the full
request/response shapes are not): triggering a run pairs the `agent` RPC
with `agent.wait` for a terminal result (equivalently `chat.send` /
`sessions.create` + `sessions.send` for session-scoped turns); streaming
session events means subscribing via `sessions.messages.subscribe` and
handling the `chat`, `session.message`, `session.operation`, and
`session.observer` broadcast event families. Implementing the actual WS
client (handshake, auth, reconnect) is left as explicit NotImplementedError
stubs so a caller fails loudly instead of getting silently-wrong behavior,
until that handshake is verified against a real install.
"""

import httpx


class GatewayClient:
    def __init__(self, *, host: str, port: int, gateway_token: str, timeout_seconds: float = 5.0):
        self.base_url = f"http://{host}:{port}"
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

    def trigger_run(self, *, agent_id: str, prompt: str) -> None:
        raise NotImplementedError(
            "Gateway WebSocket RPC protocol v4 handshake/auth is unverified against a "
            "real install — see docs/openclaw-integration-notes.md. The documented "
            "shape is: connect+auth handshake, then the `agent` RPC paired with "
            "`agent.wait` for a terminal result. For Phase 1/2 dev, trigger runs "
            "manually per docs/phase1-runbook.md instead of through this client."
        )

    def stream_session_events(self, *, agent_id: str):
        raise NotImplementedError(
            "Gateway WebSocket RPC protocol v4 handshake/auth is unverified against a "
            "real install — see docs/openclaw-integration-notes.md. The documented "
            "shape is: subscribe via `sessions.messages.subscribe` and handle `chat`/"
            "`session.message`/`session.operation`/`session.observer` broadcast events."
        )
