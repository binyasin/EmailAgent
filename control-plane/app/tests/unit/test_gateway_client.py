import json

import httpx
import pytest
import respx
import websockets

from app.services.gateway_client import GatewayClient, GatewayProtocolError, GatewayRPCError


@respx.mock
def test_is_live_true_on_200():
    respx.get("http://cell-host:41000/healthz").mock(return_value=httpx.Response(200))
    client = GatewayClient(host="cell-host", port=41000, gateway_token="tok")
    assert client.is_live() is True


@respx.mock
def test_is_live_false_on_error_status():
    respx.get("http://cell-host:41000/healthz").mock(return_value=httpx.Response(503))
    client = GatewayClient(host="cell-host", port=41000, gateway_token="tok")
    assert client.is_live() is False


@respx.mock
def test_is_live_false_on_connection_error():
    respx.get("http://cell-host:41000/healthz").mock(side_effect=httpx.ConnectError("refused"))
    client = GatewayClient(host="cell-host", port=41000, gateway_token="tok")
    assert client.is_live() is False


async def _send_json(ws, payload) -> None:
    await ws.send(json.dumps(payload))


async def _recv_json(ws) -> dict:
    return json.loads(await ws.recv())


async def _handshake(ws) -> dict:
    """Fake-gateway side of the connect handshake: issue the challenge, validate
    the client's connect request, and reply hello-ok. Returns the connect params
    the client sent, so tests can assert on role/auth/device."""
    await _send_json(
        ws, {"type": "event", "event": "connect.challenge", "payload": {"nonce": "n-1", "ts": 1}}
    )
    connect = await _recv_json(ws)
    await _send_json(ws, {"type": "res", "id": connect["id"], "ok": True, "payload": {}})
    return connect["params"]


@pytest.mark.asyncio
async def test_trigger_run_completes_agent_and_agent_wait_round_trip():
    seen_params = {}

    async def handler(ws):
        seen_params.update(await _handshake(ws))
        agent_req = await _recv_json(ws)
        assert agent_req["method"] == "agent"
        params = agent_req["params"]
        assert params["agentId"] == "org-1-primary"
        assert params["message"] == "do the thing"
        assert isinstance(params["idempotencyKey"], str) and params["idempotencyKey"]
        await _send_json(
            ws, {"type": "res", "id": agent_req["id"], "ok": True, "payload": {"runId": "run-1"}}
        )
        wait_req = await _recv_json(ws)
        assert wait_req["method"] == "agent.wait"
        assert wait_req["params"] == {"runId": "run-1"}
        await _send_json(
            ws,
            {
                "type": "res",
                "id": wait_req["id"],
                "ok": True,
                "payload": {"status": "completed", "runId": "run-1"},
            },
        )

    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = GatewayClient(host="localhost", port=port, gateway_token="tok")
        result = await client.trigger_run(agent_id="org-1-primary", prompt="do the thing")

    assert result == {"status": "completed", "runId": "run-1"}
    assert seen_params["role"] == "operator"
    assert seen_params["auth"] == {"token": "tok"}
    assert "device" not in seen_params or seen_params["device"] is None


@pytest.mark.asyncio
async def test_trigger_run_raises_gateway_rpc_error_on_failure():
    async def handler(ws):
        await _handshake(ws)
        agent_req = await _recv_json(ws)
        await _send_json(
            ws,
            {
                "type": "res",
                "id": agent_req["id"],
                "ok": False,
                "error": {"code": "FORBIDDEN", "message": "no scope"},
            },
        )

    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = GatewayClient(host="localhost", port=port, gateway_token="tok")
        with pytest.raises(GatewayRPCError, match="no scope"):
            await client.trigger_run(agent_id="org-1-primary", prompt="do the thing")


@pytest.mark.asyncio
async def test_trigger_run_raises_protocol_error_when_connect_challenge_missing():
    async def handler(ws):
        # Skip the challenge and send something else entirely.
        await _send_json(ws, {"type": "event", "event": "tick", "payload": {}})

    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = GatewayClient(host="localhost", port=port, gateway_token="tok")
        with pytest.raises(GatewayProtocolError):
            await client.trigger_run(agent_id="a", prompt="p")


@pytest.mark.asyncio
async def test_stream_session_events_yields_broadcast_events_after_subscribe():
    async def handler(ws):
        await _handshake(ws)
        sub_req = await _recv_json(ws)
        assert sub_req["method"] == "sessions.messages.subscribe"
        assert sub_req["params"] == {"sessionKey": "sess-1", "includeApprovals": False}
        await _send_json(ws, {"type": "res", "id": sub_req["id"], "ok": True, "payload": {}})
        await _send_json(
            ws, {"type": "event", "event": "session.message", "payload": {"text": "hi"}}
        )
        await _send_json(
            ws, {"type": "event", "event": "session.observer", "payload": {"headline": "done"}}
        )

    events = []
    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = GatewayClient(host="localhost", port=port, gateway_token="tok")
        async for event in client.stream_session_events(session_key="sess-1"):
            events.append(event)
            if len(events) == 2:
                break

    assert [e["event"] for e in events] == ["session.message", "session.observer"]
