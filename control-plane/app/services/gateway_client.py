"""Thin client for talking to a *running* tenant cell's OpenClaw Gateway.

Per docs/openclaw-integration-notes.md (verified against
docs.openclaw.ai/gateway/protocol, /gateway/external-apps, and
/reference/rpc), the Gateway's client-facing surface is WebSocket RPC
protocol v4, text-frame JSON with envelope `{type, id, method, params}` ->
`{type: "res", id, ok, payload}` or `{..., ok: false, error: {code,
message, ...}}`, plus out-of-band `{type: "event", event, payload}` frames.
There is no confirmation that plain HTTP `/healthz`/`/readyz` probes exist
for this protocol — the docs describe a WS-only `health` RPC method
instead. `is_live`/`is_ready` below are kept as a best-effort HTTP fallback
(plausible for a container-level liveness probe) but are UNVERIFIED and may
need replacing with the `health` RPC once a WS client exists here.

Method shapes needed for Phase 3+ are now known: `agent` (params: `prompt`
required, `agentId`/`model`/`deliver`/`bestEffortDeliver`/`idempotencyKey`
optional) paired with `agent.wait` (params: `runId`) for a terminal result;
`sessions.create` / `sessions.send` (params: `key`, `message`, ...) as the
session-scoped alternative; `sessions.messages.subscribe` (params:
`sessionKey`) for streaming, handling `chat`/`session.message`/
`session.operation`/`session.observer` broadcast events.

**Real blocker to implementing this, found this pass**: the `connect`
handshake requires every client — not just paired end-user devices — to
sign the server's `connect.challenge` nonce with `device.publicKey`/
`device.signature`/`device.signedAt` ("All connections must sign the
server-provided connect.challenge nonce," per docs.openclaw.ai). The
signing algorithm itself isn't documented anywhere found in this pass, and
`/gateway/external-apps` doesn't describe a simpler non-interactive path
for a backend service. This means a service-token client isn't a bearer
token over a socket — it needs a provisioned device keypair, and it's
unclear how that reconciles with this repo's one-`gateway_token`-per-cell
model (`AgentCell.gateway_token_encrypted`). Don't guess at the signing
algorithm; get it from the OpenClaw source or an SDK before implementing
`trigger_run`/`stream_session_events` for real. Left as explicit
NotImplementedError stubs so a caller fails loudly instead of getting
silently-wrong behavior.
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
            "Gateway WS connect handshake requires signing connect.challenge with a "
            "device keypair (algorithm unverified) — see docs/openclaw-integration-notes.md. "
            "The documented shape once that's resolved: connect+auth handshake, then the "
            "`agent` RPC (params: prompt, agentId, ...) paired with `agent.wait` (params: "
            "runId) for a terminal result. For Phase 1/2 dev, trigger runs manually per "
            "docs/phase1-runbook.md instead of through this client."
        )

    def stream_session_events(self, *, agent_id: str):
        raise NotImplementedError(
            "Gateway WS connect handshake requires signing connect.challenge with a "
            "device keypair (algorithm unverified) — see docs/openclaw-integration-notes.md. "
            "The documented shape once that's resolved: subscribe via "
            "`sessions.messages.subscribe` (params: sessionKey) and handle `chat`/"
            "`session.message`/`session.operation`/`session.observer` broadcast events."
        )
