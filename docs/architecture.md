# Architecture

## What OpenClaw provides vs. what this repo provides

[OpenClaw](https://docs.openclaw.ai) is a self-hosted, daemon-based agent **Gateway**, not an
importable dev library. It is consumed as a dependency (npm/Docker install), configured via
`~/.openclaw/openclaw.json` (JSON5), and extended through:

- **Skills** — `SKILL.md` files (YAML frontmatter + markdown instructions) that teach the agent
  a capability. Discovered under configured skill roots with a workspace > project > personal >
  managed > bundled > extra-folder precedence.
- **MCP servers** — external tool integrations wired into `mcp.servers` in the config, stdio or
  HTTP transport, with per-agent `toolFilter.include/exclude` allow-lists.
- **Memory** — a `memory` config block (sqlite-vec backed) that indexes selected sources for
  recall across sessions.
- **Heartbeat + cron** — proactive scheduling driven by a per-agent `HEARTBEAT.md` and cron job
  definitions.
- **Fleet** — OpenClaw's own multi-tenancy answer: one hardened, isolated container ("cell") per
  tenant, driven via the `openclaw fleet ...` CLI (no HTTP API). Cells publish only to a
  loopback host port.

This repo builds an email-agent product **on top of** those primitives:

| Layer | Owns |
|---|---|
| `control-plane/` (FastAPI) | Org/user accounts, mailbox OAuth token custody, the draft-approval queue and audit log, and (Phase 3+) Fleet cell lifecycle |
| `dashboard/` (React) | Tenant-facing UI: connect mailbox, approve drafts, configure skills, view digests |
| `agent-runtime/` | The `SKILL.md` files and the Gmail/Outlook MCP servers that give an OpenClaw agent email capabilities |

## Key design decision: the agent never sends mail

`draft-reply` (and `scheduling`) only ever call a `create_draft` tool. The MCP servers in
`agent-runtime/mcp-servers/` deliberately expose **no send-capable tool at all** — this is a
structural control, not just a prompt instruction. The control plane performs the actual send,
using its own provider credentials, only after a human clicks Approve in the dashboard. This
keeps "send an email on someone's behalf" a deterministic, audited, human-gated action instead
of something an LLM does autonomously.

## Data custody

- OAuth refresh tokens are envelope-encrypted at rest in the control-plane database and never
  copied into an agent cell. Cells fetch short-lived access tokens per tool call from an internal
  token-broker endpoint, authenticated by a per-org JWT minted at cell-provisioning time
  (`core/security.py`'s `create_cell_service_token`) — the org identity comes from the verified
  token, never a client-supplied id. An earlier design used one global shared secret for every
  cell, which was a real cross-tenant vulnerability (any cell could request any other tenant's
  access token, or inject fake drafts into another tenant's approval inbox); caught and fixed in
  a security review pass, with regression tests in `app/tests/integration/test_token_broker.py`
  and `test_drafts_ingest.py`.
- The token-encryption key itself supports rotation without a flag day — `services/secrets.py`
  exposes a "current key + retired-but-still-decryptable keys" list (`MultiFernet` under the
  hood), pluggable behind an `EnvKeyProvider` (implemented, default) vs. `VaultKeyProvider`/
  `AwsKmsKeyProvider` (structural stubs — real Transit/KMS-backed envelope encryption is Phase 4+
  follow-up work once there's a real Vault/AWS environment to build against). Other secrets (JWT
  signing key, OAuth client secrets, DATABASE_URL, ...) are expected to flow into the deployment
  via infra-level secret sync (External Secrets Operator / Vault Agent Injector into the k8s
  Secret referenced by `infra/k8s/helm/emailagent/values.yaml`'s `existingSecret`) rather than an
  application-level provider, since env-var-based config already is the standard integration
  point for those tools.
- `Draft` rows store metadata (subject, snippet, status) but not full email bodies — bodies are
  fetched from the provider API on demand when a human opens a draft for review, minimizing PII
  at rest.
- Memory indexing defaults to `sources: ["memory"]` only — raw session/transcript indexing
  (which would include full email bodies) is opt-in per org.

## Phased roadmap

1. **Phase 1** (done): single-tenant, Gmail-only, one hand-configured OpenClaw container via
   Docker Compose, `triage` + `draft-reply` skills, minimal FastAPI + React approval flow.
2. **Phase 2** (done): Outlook/Graph support behind a provider abstraction, `digest` +
   `scheduling` skills, heartbeat/cron wiring, per-tenant memory files (style profile, VIP list).
3. **Phase 3** (built, not yet run against a real Fleet install — see caveat below):
   multi-tenant Fleet cell provisioning (`services/fleet_cli.py` + `workers/provision_cell.py`),
   RBAC + org invite flow, the remaining four skills (`followup-nudge`, `vip-escalation`,
   `unsubscribe-cleanup`, `sensitive-content-flagging`), skill-settings/VIP-rule management,
   a billing-tier gating stub, and an admin cells dashboard view.
4. **Phase 4** (built, see caveats): Helm chart for the control plane + dashboard
   (`infra/k8s/helm/emailagent/` — cells stay on dedicated Docker/Podman hosts, see
   `infra/k8s/notes.md`), a Prometheus/Grafana/Loki observability stack, a rotation-capable
   token-encryption key provider (`services/secrets.py`), real Stripe billing (checkout, customer
   portal, webhook signature verification), and a security review pass that found and fixed a
   real cross-tenant vulnerability (see below).

### Security review findings (Phase 4)

A review pass across the accumulated Phase 1-4 code found:

- **Cross-tenant token/draft access (fixed, high severity)**: the internal token-broker and
  drafts/digests-ingest endpoints authenticated every cell with one global shared secret and
  trusted a client-supplied `tenant_id`/`org_id` parameter — meaning any cell (or anyone holding
  that one secret) could request another tenant's Gmail/Outlook access token, or inject fake
  drafts into another tenant's approval inbox. Fixed by minting a per-org JWT at cell-provisioning
  time (`core/security.py`'s `create_cell_service_token`/`decode_cell_service_token`) and deriving
  org identity from the verified token instead of a caller-supplied parameter. Regression tests:
  `app/tests/integration/test_token_broker.py`, `test_drafts_ingest.py`.
- **Public exposure of internal-only endpoints (fixed, caught before shipping)**: the first draft
  of the Helm chart's Ingress routed `/internal/*` to the public internet. Split into a public
  Ingress (dashboard-facing API + the Stripe webhook, which must be internet-reachable) and a
  separate `internal-ingress.yaml` for the token-broker/ingest endpoints, disabled by default so a
  misconfigured deployment fails closed rather than silently exposing them.
- **Login timing side-channel + no rate limiting (fixed, low/medium severity)**: a login attempt
  for a nonexistent email skipped the bcrypt verify entirely, making response time distinguish
  "no such account" from "wrong password" — fixed by always verifying against a dummy hash.
  `/auth/login` also had no rate limiting (brute-force/credential-stuffing exposure); added
  `slowapi`-based limiting (5/minute per IP — see `core/rate_limit.py`'s caveat about per-process
  limits in a multi-replica deployment).
- **Zero test coverage on the token broker and drafts-ingest endpoints** before this review —
  the cross-tenant vulnerability above existed undetected because nothing exercised those routes
  at all. Now covered; see the regression tests referenced above.

Not fixed, tracked as follow-up: `VaultKeyProvider`/`AwsKmsKeyProvider` remain structural stubs
(see `services/secrets.py`); the Fleet CLI/Gateway RPC integration remains unverified against a
real OpenClaw install (see below); Stripe integration is untested against a real Stripe account.

### Phase 3 caveat

Everything in Phase 3 is built and covered by unit/integration tests, but the tests exercise
`CellProvisioner`/`GatewayClient` against **fakes**, not a real `openclaw` binary — because the
exact Fleet CLI subcommand flags, the config-delivery mechanism (how a cell actually receives
`openclaw.json`/`vip-list.md`), and the Gateway's WebSocket RPC protocol are unverified secondhand
assumptions (see `docs/openclaw-integration-notes.md`). `services/fleet_cli.py` and
`services/gateway_client.py` isolate those assumptions behind small interfaces specifically so
they can be corrected in one place once verified, rather than fixed by guessing twice. The
Phase 1/2 Docker Compose stack (a single static `openclaw` container, no Fleet) remains the only
part of this system that's been run against a real OpenClaw Gateway.

See `docs/openclaw-integration-notes.md` for OpenClaw specifics that still need verification
against primary docs before Phase 3's Fleet-based provisioning can be trusted in a real
deployment.
