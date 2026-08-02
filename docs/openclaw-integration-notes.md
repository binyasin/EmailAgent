# OpenClaw integration notes — verify before relying on

The facts below were gathered via web search summaries of `docs.openclaw.ai`, not by reading the
primary docs directly. They inform the design (see `architecture.md`) but the specifics should be
confirmed against the actual docs/CLI `--help` output before Phase 3 implementation locks them in.

- **`mcpServers` / `agents` config schema** — exact field names in `openclaw.json` for MCP server
  entries (stdio vs `streamable-http`), `toolFilter.include/exclude` glob syntax, and the
  `agents.defaults` / `agents.entries.<id>` shape (does an entry replace or merge array fields
  like `skills`?). Verify against `docs.openclaw.ai/cli/mcp` and
  `docs.openclaw.ai/gateway/configuration-reference`.
- **Gateway WebSocket RPC protocol (v4)** — the method table `services/gateway_client.py` (Phase
  3) will need to call for health/session inspection. Verify against
  `docs.openclaw.ai/gateway/protocol` and `docs.openclaw.ai/gateway/external-apps`. `/healthz`
  and `/readyz` HTTP probes are expected to exist regardless.
- **Fleet CLI surface** — `openclaw fleet create|start|stop|restart|upgrade|rm|list|status|logs|
  backup|restore|doctor`, `--json` output flag, and whether it's still marked experimental.
  Verify against `docs.openclaw.ai/cli/fleet`. Fleet state appears to be file-based per host
  (`<state-dir>/fleet/cells/<tenant>/`), so `cell_provisioner.py` must serialize mutations per
  host rather than issuing concurrent `fleet` calls.
- **Cron job schema** — `~/.openclaw/cron/jobs.json` / `jobs-state.json` shape for one-shot,
  interval, and cron-expression jobs with timezone + auto-staggering. The dev config at
  `agent-runtime/templates/dev-cron-jobs.json5` guesses a `{ id, schedule: { type, expression,
  timezone }, agent, prompt }` shape where `prompt` is injected as if a channel message arrived
  — **this specific shape, and in particular whether a cron job can trigger a skill via a
  synthetic prompt at all, is unverified** and is the single riskiest assumption in the Phase 2
  digest wiring. Verify against `docs.openclaw.ai/automation/cron-jobs` / `openclaw cron --help`
  before relying on scheduled digests in anything beyond local dev.
- **Config hot-reload scope** — whether editing `openclaw.json` (e.g. toggling a skill) applies
  live or requires a Gateway/cell restart. Affects whether `cell_provisioner.py`'s update path
  needs `fleet restart` on every config change.
- **Skill discovery precedence** — described as a 6-tier order (workspace > project agent >
  personal agent > managed/local > bundled > extra folders), up to 6 directory levels deep.
  Confirm exact tier names against `docs.openclaw.ai/tools/skills` /
  `docs.openclaw.ai/tools/creating-skills` when deciding where tenant-specific skill overrides
  (if ever needed) should live relative to the shared `agent-runtime/skills/` bundle.
- **Memory config** — `memory.search.sources` values (`"memory"`, `"sessions"`), default
  embedding provider, and the "dreaming" consolidation job. Verify against
  `docs.openclaw.ai/reference/memory-config` before enabling anything beyond the Phase 1/2
  default of `sources: ["memory"]`.
