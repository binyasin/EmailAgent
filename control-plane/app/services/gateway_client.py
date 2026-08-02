"""Thin client for talking to a *running* tenant cell's OpenClaw Gateway.

Per docs/openclaw-integration-notes.md, external apps are documented to talk
to a running Gateway over a WebSocket RPC protocol (v4) with roughly 200
methods — but only the description of that protocol's existence was
gathered during planning, not the actual method table. Rather than fabricate
a plausible-looking RPC implementation that would silently be wrong, only
the HTTP health probes (which are corroborated more concretely — `/healthz`
liveness, `/readyz` readiness) are implemented here. The RPC methods needed
for Phase 3+ (triggering an on-demand run, streaming session events) are
left as explicit NotImplementedError stubs so a caller fails loudly instead
of getting silently-wrong behavior, until the protocol is verified against
docs.openclaw.ai/gateway/protocol on a real install.
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
            "Gateway WebSocket RPC protocol is unverified — see "
            "docs/openclaw-integration-notes.md. For Phase 1/2 dev, trigger runs "
            "manually per docs/phase1-runbook.md instead of through this client."
        )

    def stream_session_events(self, *, agent_id: str):
        raise NotImplementedError(
            "Gateway WebSocket RPC protocol is unverified — see "
            "docs/openclaw-integration-notes.md."
        )
