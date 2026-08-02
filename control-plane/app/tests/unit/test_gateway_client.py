import httpx
import pytest
import respx

from app.services.gateway_client import GatewayClient


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


def test_trigger_run_raises_not_implemented():
    client = GatewayClient(host="cell-host", port=41000, gateway_token="tok")
    with pytest.raises(NotImplementedError):
        client.trigger_run(agent_id="a", prompt="p")
