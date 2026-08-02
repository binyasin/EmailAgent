# Kubernetes topology notes

## Hybrid topology: control plane in k8s, cells on dedicated hosts

The Helm chart at `helm/emailagent/` deploys **only** the control-plane (FastAPI) and dashboard
(static React build behind nginx). Tenant OpenClaw [Fleet](https://docs.openclaw.ai/cli/fleet)
cells are **not** deployed by this chart, because:

- Fleet's documented interface is a CLI (`openclaw fleet create|start|stop|...`) driving
  Docker/Podman containers directly on a host — there is no documented Kubernetes operator or
  Helm chart for Fleet itself (verify this is still true before committing further, per
  `docs/openclaw-integration-notes.md`).
- Fleet cells are meant to publish only to a loopback host port, which doesn't map cleanly onto
  a typical multi-node k8s pod network without extra plumbing (hostNetwork, or a sidecar proxy)
  that would undercut the isolation Fleet's own hardened-container baseline provides.

So the intended production topology is:

- **Control plane + dashboard**: this Helm chart, on a standard k8s cluster, autoscaled.
- **Cell hosts**: a fleet (pun intended) of dedicated VMs running Docker/Podman + the `openclaw`
  CLI, each hosting some number of tenant cells via `openclaw fleet create/start`, provisioned
  and driven by `control-plane`'s `app/services/fleet_cli.py` over SSH or an agent process on
  each host (not yet built — `SubprocessFleetCliRunner` currently assumes it's running on the
  same host as the `openclaw` binary, which is only true if control-plane itself runs on a cell
  host rather than in the k8s cluster; reconciling this is Phase 4+ follow-up work once Fleet's
  real interface is verified).
- **Network path from cell hosts to control-plane**: cell hosts need to reach the control
  plane's token-broker and ingest endpoints (`/internal/v1/tokens`, `/internal/v1/drafts`,
  `/internal/v1/digests`) but **must not** do so over the public internet — see
  `helm/emailagent/values.yaml`'s `ingress.internal` block and
  `helm/emailagent/templates/internal-ingress.yaml`, which is disabled by default specifically
  so a deployment fails closed instead of silently exposing those endpoints publicly with a
  misconfigured annotation.

## Verification status

This chart was authored following standard Helm conventions but has **not** been run through
`helm lint` / `helm template` / a real cluster — no `helm` or `kubectl` binary was available in
the environment this was built in. `values.yaml` and `Chart.yaml` (pure YAML, no template
directives) were validated with a YAML parser; the templated files were reviewed by hand.
Run `helm lint infra/k8s/helm/emailagent && helm template infra/k8s/helm/emailagent` before
trusting this against a real cluster.

## What's still open

- How `cell_provisioner.py`/`fleet_cli.py` actually reaches a *remote* cell host (SSH exec? a
  small per-host agent daemon? Docker's remote API?) once cell hosts are no longer the same
  machine as control-plane. `SubprocessFleetCliRunner` only handles the local case today.
- Whether Fleet has gained a documented remote/API mode since this was last researched — worth
  re-checking `docs.openclaw.ai/cli/fleet` before building the remote-execution path, since it
  would change this design significantly if so.
- Database: this chart assumes an externally-managed Postgres (RDS/Cloud SQL/etc.) referenced via
  `existingSecret`'s `DATABASE_URL` — it does not vendor a Postgres subchart.
