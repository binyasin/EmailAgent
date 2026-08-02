"""Wraps the OpenClaw `fleet` CLI, which is the *only* documented interface
for tenant-cell lifecycle (create/start/stop/rm/status) — there is no Fleet
HTTP API. Subcommand names and flags below are verified against
docs.openclaw.ai/cli/fleet — see docs/openclaw-integration-notes.md for
citations. Fleet itself is still explicitly documented as experimental
("command names, flags, output shapes ... can change between releases
without a deprecation window"), so `CellProvisioner` stays written against
the small `FleetCliRunner` protocol below so a future break is a one-file
fix, and so it can be unit tested today with a fake runner instead of a
real `openclaw` binary.

Fleet's cell state is file-based per host, so callers MUST serialize
concurrent `fleet` invocations against the same host — see
`app/workers/provision_cell.py` for the lock that enforces this.

Cell config (openclaw.json, vip-list.md) is NOT handed to Fleet via a CLI
flag — no such flag exists. Fleet owns `<state-dir>/fleet/cells/<tenant>/`
(mounted to `/home/node/.openclaw` in the container) and seeds a default
config there itself before first start. Callers must create the cell with
`no_start=True`, overwrite the rendered config files into that directory,
then call `start()` — see `app/workers/provision_cell.py`.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Protocol


class FleetCliError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.args = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"fleet {' '.join(args)} exited {returncode}: {stderr}")


@dataclass
class FleetCliResult:
    returncode: int
    stdout: str
    stderr: str
    json: dict | None


class FleetCliRunner(Protocol):
    def run(self, args: list[str]) -> FleetCliResult: ...


class SubprocessFleetCliRunner:
    """Real implementation — shells out to `openclaw fleet <args> --json`."""

    def __init__(self, *, openclaw_bin: str = "openclaw", timeout_seconds: int = 120):
        self.openclaw_bin = openclaw_bin
        self.timeout_seconds = timeout_seconds

    def run(self, args: list[str]) -> FleetCliResult:
        proc = subprocess.run(  # noqa: S603 — args are constructed internally, not from user input
            [self.openclaw_bin, "fleet", *args, "--json"],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        parsed = None
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
            except json.JSONDecodeError:
                parsed = None
        return FleetCliResult(
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, json=parsed
        )


@dataclass
class CellCreateResult:
    tenant_key: str
    host_port: int | None
    gateway_token: str | None


class CellProvisioner:
    """Orchestrates the create → configure → start lifecycle of a tenant's
    Fleet cell. Config file writing (openclaw.json, vip-list.md) is the
    caller's responsibility via `config_renderer.py` — this class only
    drives the Fleet CLI itself."""

    def __init__(self, runner: FleetCliRunner):
        self._runner = runner

    def _run_or_raise(self, args: list[str]) -> FleetCliResult:
        result = self._runner.run(args)
        if result.returncode != 0:
            raise FleetCliError(args, result.returncode, result.stderr)
        return result

    def create(
        self,
        tenant_key: str,
        *,
        image: str,
        env: dict[str, str],
        no_start: bool = False,
    ) -> CellCreateResult:
        args = ["create", tenant_key, "--image", image]
        for key, value in env.items():
            args += ["--env", f"{key}={value}"]
        if no_start:
            # Create the container without starting it, so the caller can
            # overwrite Fleet's self-seeded config in
            # <state-dir>/fleet/cells/<tenant>/ with our rendered
            # openclaw.json/vip-list.md before the Gateway process ever reads it.
            args += ["--no-start"]
        result = self._run_or_raise(args)
        payload = result.json or {}
        return CellCreateResult(
            tenant_key=tenant_key,
            host_port=payload.get("host_port") or payload.get("port"),
            gateway_token=payload.get("gateway_token") or payload.get("token"),
        )

    def start(self, tenant_key: str) -> None:
        self._run_or_raise(["start", tenant_key])

    def stop(self, tenant_key: str) -> None:
        self._run_or_raise(["stop", tenant_key])

    def restart(self, tenant_key: str) -> None:
        self._run_or_raise(["restart", tenant_key])

    def remove(self, tenant_key: str, *, purge_data: bool = False) -> None:
        args = ["rm", tenant_key, "--force"]
        if purge_data:
            args.append("--purge-data")
        self._run_or_raise(args)

    def status(self, tenant_key: str) -> dict:
        result = self._run_or_raise(["status", tenant_key])
        return result.json or {}
