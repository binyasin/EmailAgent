# AI Email Agent

A multi-tenant SaaS AI email agent built on [OpenClaw](https://docs.openclaw.ai). OpenClaw
provides the agent runtime (Gateway daemon, Skills, MCP tool wiring, memory, heartbeat/cron
scheduling); this repo provides the SaaS control plane, the email-provider MCP integrations,
and the Skills that turn OpenClaw into an email triage/drafting/scheduling assistant.

## Architecture at a glance

- **`control-plane/`** — FastAPI backend. Owns orgs/users, mailbox OAuth connections, the
  draft-approval queue, and (from Phase 3) provisions one isolated OpenClaw
  [Fleet](https://docs.openclaw.ai/cli/fleet) "cell" per tenant.
- **`dashboard/`** — React SPA. Connect a mailbox, review/approve AI-drafted replies, configure
  which skills are enabled, view digests and the audit log.
- **`agent-runtime/`** — Everything that runs *inside* an OpenClaw cell: `SKILL.md` capability
  definitions (triage, draft-reply, digest, scheduling, ...) and the Gmail/Outlook MCP servers
  those skills call. The agent **never sends mail directly** — it creates drafts; the control
  plane sends only after a human approves.
- **`infra/`** — Local dev Docker Compose, a Helm chart for the control plane + dashboard
  (`infra/k8s/helm/emailagent/`), and a Prometheus/Grafana/Loki observability add-on.

See `docs/architecture.md` for the full design and `docs/phase1-runbook.md` for how to run the
current vertical slice end-to-end.

## Status

**Phases 1-4 built.** Gmail + Outlook, all 8 skills, RBAC + org invites, skill/VIP-rule settings,
real Stripe billing (checkout, portal, webhook signature verification), a Fleet-CLI-backed cell
provisioner with an admin cells view, a Helm chart, a Prometheus/Grafana/Loki observability stack,
and a rotation-capable token-encryption key provider. 85 automated tests pass (control-plane
pytest + skill-lint + gmail-mcp/outlook-mcp/dashboard vitest).

A security review pass (see `docs/architecture.md`'s "Data custody" section) found and fixed a
real cross-tenant vulnerability: the original per-cell auth design used one global shared secret
for every tenant, letting any cell request any other tenant's Gmail/Outlook access token or
inject fake drafts into another tenant's approval inbox. It's now a per-org JWT minted at
provisioning time, with regression tests. Also added: login rate limiting, a login timing
side-channel fix, and closed a public-ingress exposure of internal-only endpoints in the Helm
chart before it shipped.

**What's unverified**: the Fleet CLI's exact subcommands/flags, how a cell actually receives its
rendered config, and the Gateway's WebSocket RPC protocol are secondhand assumptions isolated
behind small interfaces (`services/fleet_cli.py`, `services/gateway_client.py`) and tested against
fakes, not a real `openclaw` binary — see `docs/openclaw-integration-notes.md`. Only the Phase 1/2
Docker Compose dev stack (single static `openclaw` container, no Fleet) has been run against a
real OpenClaw Gateway. The Helm chart has been reviewed by hand but not run through
`helm lint`/`helm template` (no `helm` binary was available while building it). Stripe billing
code is written directly against the documented SDK and tested with mocks, not against a real
Stripe test-mode account.

## Quickstart (Phase 1/2 dev stack)

```bash
cp .env.example .env   # fill in Google OAuth credentials
docker compose -f infra/docker-compose.dev.yml up -d
python control-plane/app/scripts/seed_dev_org.py
```

Then open the dashboard at http://localhost:5173, connect a Gmail account, and follow
`docs/phase1-runbook.md`.
