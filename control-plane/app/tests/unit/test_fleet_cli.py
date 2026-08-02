import pytest

from app.services.fleet_cli import CellProvisioner, FleetCliError, FleetCliResult


class FakeFleetCliRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.responses: dict[str, FleetCliResult] = {}

    def queue(self, subcommand: str, result: FleetCliResult) -> None:
        self.responses[subcommand] = result

    def run(self, args: list[str]) -> FleetCliResult:
        self.calls.append(args)
        subcommand = args[0]
        return self.responses.get(
            subcommand, FleetCliResult(returncode=0, stdout="", stderr="", json=None)
        )


def test_create_parses_host_port_and_gateway_token():
    runner = FakeFleetCliRunner()
    runner.queue(
        "create",
        FleetCliResult(
            returncode=0,
            stdout="",
            stderr="",
            json={"host_port": 41000, "gateway_token": "secret-token"},
        ),
    )
    provisioner = CellProvisioner(runner)

    result = provisioner.create(
        "org-1", image="openclaw/openclaw:latest", env={"TENANT_ID": "org-1"}
    )

    assert result.tenant_key == "org-1"
    assert result.host_port == 41000
    assert result.gateway_token == "secret-token"
    assert runner.calls[0][:2] == ["create", "org-1"]
    assert "--env" in runner.calls[0]
    assert "TENANT_ID=org-1" in runner.calls[0]


def test_start_stop_restart_remove_call_expected_subcommands():
    runner = FakeFleetCliRunner()
    provisioner = CellProvisioner(runner)

    provisioner.start("org-1")
    provisioner.stop("org-1")
    provisioner.restart("org-1")
    provisioner.remove("org-1", purge_data=True)

    assert runner.calls[0] == ["start", "org-1"]
    assert runner.calls[1] == ["stop", "org-1"]
    assert runner.calls[2] == ["restart", "org-1"]
    assert runner.calls[3] == ["rm", "org-1", "--force", "--purge-data"]


def test_nonzero_exit_raises_fleet_cli_error():
    runner = FakeFleetCliRunner()
    runner.queue(
        "start", FleetCliResult(returncode=1, stdout="", stderr="cell not found", json=None)
    )
    provisioner = CellProvisioner(runner)

    with pytest.raises(FleetCliError, match="cell not found"):
        provisioner.start("missing-org")


def test_status_returns_parsed_json():
    runner = FakeFleetCliRunner()
    runner.queue(
        "status", FleetCliResult(returncode=0, stdout="", stderr="", json={"status": "running"})
    )
    provisioner = CellProvisioner(runner)

    assert provisioner.status("org-1") == {"status": "running"}
