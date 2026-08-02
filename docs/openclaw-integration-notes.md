# OpenClaw integration notes

Originally these facts were gathered secondhand and flagged "verify before relying on." That
verification pass happened against the real `docs.openclaw.ai` (fetched directly, not from
training data) — findings below are marked **RESOLVED** (confirmed, code updated to match),
**PARTIALLY RESOLVED** (confirmed enough to fix the known bug, but a detail remains open), or
**STILL OPEN** (still needs a real `openclaw` binary/install to confirm). None of this has been
exercised against a live Gateway or Fleet install — it's still "docs say X," not "we ran X and it
worked."

## Fleet CLI surface — RESOLVED

Confirmed against `docs.openclaw.ai/cli/fleet`. Fleet is explicitly documented as experimental:
"command names, flags, output shapes, and the container profile can change between releases
without a deprecation window."

Subcommands: `create <tenant>`, `list`/`ls`, `status <tenant>`, `logs <tenant>` (`--follow`,
`--tail`, `--since`), `start`/`stop`/`restart <tenant>`, `upgrade <tenant>`, `backup <tenant>
--out <path>`, `restore <tenant> --from <path>`, `doctor [<tenant>]`, `rm <tenant> [--force]
[--purge-data]`. Key flags on `create`: `--image`, `--runtime` (docker/podman), `--port`,
`--memory`, `--cpus`, `--env KEY=VALUE` (repeatable), `--gateway-token`, `--no-start`. `--json`
gives machine-readable output on all subcommands.

**Cell config delivery was wrong and has been fixed.** There is no `--config-dir` flag — that was
a guess in the original `fleet_cli.py`/`provision_cell.py` and has been removed. Fleet instead
owns `<state-dir>/fleet/cells/<tenant>/` (bind-mounted to `/home/node/.openclaw` in the
container) and seeds a default config there itself before first start; a second directory,
`<state-dir>/fleet/auth-profile-secrets/<tenant>/`, mounts to `/home/node/.config/openclaw`. The
corrected flow, now implemented in `app/workers/provision_cell.py`: `create(..., no_start=True)`,
then overwrite the rendered `openclaw.json`/`vip-list.md` directly into
`<openclaw_state_dir>/fleet/cells/<tenant>/`, then `start()`. `<state-dir>` defaults to
`~/.openclaw` (overridable via `OPENCLAW_STATE_DIR`, per `docs.openclaw.ai/help/environment`);
exposed as `Settings.openclaw_state_dir` in `app/core/config.py`.

Config updates to an already-running cell now call `restart()` instead of re-`start()`ing an
already-running cell (see "Config hot-reload" below for why a restart might not even be strictly
necessary, but it's the safe choice given that's still not 100% confirmed).

**Still open**: the exact JSON keys `fleet create --json`/`fleet status --json` return for host
port and gateway token (`CellCreateResult` guesses `host_port`/`port` and `gateway_token`/`token`
— plausible given the flag names `--port`/`--gateway-token`, but not confirmed from an actual
example payload). `list`, `logs`, `backup`, `restore`, `doctor`, `upgrade` aren't wired into
`CellProvisioner` yet — not needed for Phase 3 provisioning, but worth adding once an admin
cells-ops UI needs them.

## Gateway WebSocket RPC protocol (v4) — PARTIALLY RESOLVED, one hard blocker found

Confirmed against `docs.openclaw.ai/gateway/protocol`, `/gateway/external-apps`, and
`/reference/rpc`. Connection: server sends `{type: "event", event: "connect.challenge", payload:
{nonce, ts}}`, client replies with a `connect` request, server answers `hello-ok`. Protocol v4
current, v3 supported for one version back. Request/response envelope:
`{type: "req", id, method, params}` → `{type: "res", id, ok: true, payload}` or `{..., ok: false,
error: {code, message, details, retryable, retryAfterMs}}`; out-of-band updates arrive as
`{type: "event", event, payload}`. Pre-auth frames capped at 64 KiB; post-auth cap comes from
`hello-ok.policy.maxPayload` (default 25 MB); server sends `tick` keepalives at
`policy.tickIntervalMs`, and silence beyond 2x that triggers a client-side close (code 4000).

RPC method shapes now known: `agent` (params: `prompt` required, `agentId`/`model`/`deliver`/
`bestEffortDeliver`/`idempotencyKey` optional) paired with `agent.wait` (params: `runId`) — the
pairing `/gateway/external-apps` explicitly recommends for external integrations. Session-scoped
alternative: `sessions.create` (params: `model`/`thinkingLevel`/`worktree`/`parentSessionKey`/...,
returns `sessionKey`) → `sessions.send` (params: `key`, `message`, `queueMode`, ...). Streaming:
`sessions.messages.subscribe` (params: `sessionKey`, `includeApprovals`); broadcast event families
are `chat`, `session.message`, `session.operation`, `session.observer`.

**Hard blocker found this pass, not present in the earlier summary**: `connect.params.auth.token`
alone is not sufficient. "All connections must sign the server-provided connect.challenge nonce" —
`connect.params.device` (`id`, `publicKey`, `signature`, `signedAt`, `nonce`) is a **required**
object for every role (operator/node/worker), not just paired end-user devices. Neither
`/gateway/external-apps` nor `/reference/rpc` documents a simpler non-interactive path for a
backend service, and the signing algorithm itself wasn't found anywhere in this pass. This means
`GatewayClient` can't be a bearer-token WS client — it needs a provisioned device keypair, and how
that reconciles with this repo's one-`gateway_token`-per-cell model (`AgentCell.gateway_token_encrypted`,
`services/fleet_cli.py`'s `--gateway-token`) is an open design question, not just an
implementation detail. `gateway_client.py`'s docstring and `NotImplementedError` messages now spell
this out; do not guess at the signing algorithm — get it from the OpenClaw source or an official
SDK before writing real signing code here.

**Also still open**: the protocol docs do **not** describe HTTP `/healthz`/`/readyz` endpoints —
they describe a WS-only `health` RPC method instead. `GatewayClient.is_live()`/`is_ready()` still
probe HTTP `/healthz`/`/readyz` as a best-effort fallback (plausible as a container-level liveness
probe separate from the client protocol), but that's flagged as unverified rather than
"corroborated" as the original docstring claimed. Confirm against a real cell before depending on
it for anything but local dev convenience.

## `mcp`/`agents` config schema — RESOLVED, one real bug fixed

Confirmed against `docs.openclaw.ai/gateway/configuration-reference` and `/cli/mcp`.

**Bug fixed**: the config's MCP servers section is nested as `mcp.servers`, not a top-level
`mcpServers` key. All three places that rendered/asserted the old shape have been corrected:
`agent-runtime/templates/openclaw.json5.jinja`, `agent-runtime/templates/dev-openclaw.json5`, and
`control-plane/app/tests/unit/test_config_renderer.py`. Root-level config keys, for reference:
`gateway`, `agents`, `channels`, `models`, `mcp`, `skills`, `plugins`, `browser`, `ui`, `auth`,
`hooks`, `cron`, `discovery`, `env`, `secrets`, `logging`, `diagnostics`, `update`, `acp`,
`wizard`, `cloudWorkers`.

Server entry shapes were already correct: stdio uses `command`/`args`/`env`; remote uses `url` +
`transport: "streamable-http"` (or `"sse"`), plus optional `headers`/`connectionTimeoutMs`/
`requestTimeoutMs`/`auth`/`sslVerify`/`clientCert`/`clientKey`. `toolFilter.include`/`exclude`
takes exact tool names or simple `*` globs — matches what's rendered.

`agents.entries.<id>` **merges** with `agents.defaults.*` rather than replacing — confirmed,
including array fields like `skills`. `config_renderer.py` already prepends `"_shared"` into each
agent's own `skills` list in addition to `agents.defaults.skills: ["_shared"]`; since arrays
merge, this is redundant (relying on the Gateway to dedupe) rather than wrong — worth simplifying
later but not a bug.

## Cron job schema — RESOLVED, and the original digest-wiring assumption was wrong

Confirmed against `docs.openclaw.ai/automation/cron-jobs`. This was flagged as "the single
riskiest assumption in the Phase 2 digest wiring," and the risk was real:

**The original assumption — a cron job's `prompt` gets injected "as if a channel message
arrived" — is explicitly contradicted by the docs.** The documented model is an unattended
scheduler-run agent turn (`--session` + `--message` payload), which the docs state runs "within
the scheduler's unattended execution boundary — not as a simulated channel message." Whatever
distinction the agent/skills make between a real channel message and a scheduler-run turn (if
any) should be treated as a real behavioral difference, not a naming detail — see
`agent-runtime/templates/dev-cron-jobs.json5` and `agent-runtime/heartbeat/HEARTBEAT.md` for
where this assumption fed into skill/heartbeat design.

Documented schedule/payload shape, refined against `docs.openclaw.ai/cli/cron` on a second pass:
the cron expression and message are **positional** arguments (`openclaw cron add "<cron-expr>"
"<message>" ...`), not `--cron`/`--message` flags as first guessed. One-shot jobs use `--at
<datetime>` (ISO 8601 or relative like `20m`) instead of a cron expression, `--tz <iana>` applies
to either form. `--session main|isolated|current|session:<id>` selects the session-binding
target (`isolated` = fresh transcript per run), `--agent <id>` picks the agent, and delivery is
`--announce` / `--webhook <url>` / `--no-deliver`. `--command <shell>` / `--command-argv '[...]'`
exist for deterministic shell execution instead of an agent prompt. Top-of-hour cron expressions
auto-stagger by up to 5 minutes unless `--exact` or an explicit `--stagger` is given. All cron
mutations (add/update/remove/run) require `operator.admin`. This is all CLI-flag surface — the
docs describe the CLI as the interface, not a hand-editable `jobs.json` file schema, so the exact
on-disk format `dev-cron-jobs.json5` guesses at (`{ id, schedule: { type, expression, timezone },
agent, prompt }`) is **still unverified**. That file now documents the equivalent `openclaw cron
add` command (using `--session isolated --no-deliver` for the digest use case) as the more
likely-correct approach; if the bind-mounted file doesn't work against a real build, switch Phase
1/2 dev to running that command inside the container instead.

There's also a `cron.*` RPC family (`cron.add`, `cron.list`, `cron.get`, `cron.update`,
`cron.remove`, `cron.run`, `cron.runs`) for managing jobs over the same WebSocket protocol as
`agent`/`sessions.*` above — an internal experiments-tracker page (not primary API docs) mentions
`cron.add` RPC params including `sessionTarget`, `wakeMode`, and `payload`, but didn't give enough
detail to trust those field names; treat that RPC family as existing but its exact shape as
unverified, separate from the confirmed CLI flag surface above.

## Config hot-reload — RESOLVED

Confirmed against `docs.openclaw.ai/gateway/configuration` (via search summary, not a direct
fetch — slightly less certain than the other items here). The Gateway watches `openclaw.json` and
applies most changes automatically. `gateway.reload.mode` controls this: `"off"` (ignore live
edits), `"restart"` (always restart), `"hot"` (in-process, no restart), `"hybrid"` (default — try
hot, fall back to restart if required). `debounceMs` (default 300–500ish depending on doc
version) and `deferralTimeoutMs` (default 300000) tune the reload timing. Invalid external edits
are skipped, keeping the current runtime config active.

Practical effect: `provision_cell.py`'s config-update path calling `cell_provisioner.restart()`
after rewriting the config file may be unnecessary in `"hybrid"` mode for most changes (the
Gateway would pick it up itself), but was kept as the safe explicit choice since it's not fully
confirmed which config changes (e.g. adding a new MCP server) actually qualify for in-process hot
reload vs needing a restart. Revisit once tested against a real install — this could remove a
`fleet restart` round-trip from every skill-setting/mailbox-connection change.

## Skill discovery precedence — RESOLVED, matched existing assumption

Confirmed against `docs.openclaw.ai/tools/skills`: workspace > project agent (`<workspace>/.agents/skills`)
> personal agent (`~/.agents/skills`) > managed/local (`<state-dir>/skills`) > bundled > extra
directories (`skills.load.extraDirs` + plugin skills), `SKILL.md` discovered up to 6 levels deep
under any configured root. `docs/architecture.md`'s existing "workspace > project > personal >
managed > bundled > extra-folder" description already matched this — no correction needed.

## Memory config — RESOLVED, matches existing default

Confirmed against `docs.openclaw.ai/reference/memory-config`. `memory.search.sources` defaults to
`["memory"]` (indexes Markdown memory files); adding `"sessions"` indexes conversation transcripts
and needs `memory.qmd.sessions.enabled: true` for QMD backends (or the higher-level
`rememberAcrossConversations` setting, which implies it). Default embedding provider is OpenAI;
`provider: "none"` falls back to lexical full-text search. Dreaming (memory consolidation) is
configured under `plugins.entries.memory-core.config.dreaming` — `enabled: true` by default,
`frequency: "0 3 * * *"` (3am daily), writes to `memory/.dreams/` and `DREAMS.md`. This repo's
current config only sets `memory.search.sources: ["memory"]`, which matches the documented
default — no code changes needed, nothing here was being relied on incorrectly.

## Summary of code changes made across this verification effort

- `agent-runtime/templates/openclaw.json5.jinja`, `dev-openclaw.json5`: `mcpServers` → `mcp.servers`.
- `control-plane/app/tests/unit/test_config_renderer.py`: assertions updated to match.
- `control-plane/app/services/fleet_cli.py`: removed the nonexistent `--config-dir` flag; `create()`
  now takes `no_start: bool` mapping to the real `--no-start` flag.
- `control-plane/app/core/config.py`: `cell_state_root` replaced with `openclaw_state_dir` (default
  `~/.openclaw`), matching where Fleet actually looks for `OPENCLAW_STATE_DIR`.
- `control-plane/app/workers/provision_cell.py`: create-then-write-config-then-start ordering for
  new cells (Fleet must create the directory before we can overwrite it); config updates on an
  existing cell now `restart()` instead of re-`start()`.
- `control-plane/app/services/gateway_client.py`: docstring/error messages updated with the real
  envelope/method shapes and the device-signature blocker; HTTP health-probe assumption downgraded
  from "corroborated" to "unverified fallback." `trigger_run`/`stream_session_events` deliberately
  left as `NotImplementedError` — the device-signing algorithm is unverified, and guessing at
  cryptographic signing code would be worse than an explicit stub.
- `agent-runtime/templates/dev-cron-jobs.json5`: corrected the "injected as if a channel message"
  framing and the flag syntax (positional cron-expr/message, `--session`, `--agent`); documented
  the real `openclaw cron add` equivalent command.

## Still not exercised against a real install

Everything above is now grounded in the real `docs.openclaw.ai` rather than a secondhand summary,
but none of it has been run against an actual `openclaw` binary or a live Gateway/Fleet cell.
Before trusting this beyond local dev, in priority order:

1. **Resolve the Gateway device-signing blocker** — find the actual signing algorithm/keypair
   provisioning flow (OpenClaw source or SDK, not docs search) and decide how it reconciles with
   this repo's one-`gateway_token`-per-cell model. Nothing calls the real Gateway RPC until this
   is answered; `trigger_run`/`stream_session_events` stay unimplemented until then.
2. Run `openclaw fleet create --help` (and the real command) to confirm the `--json` output shape
   for host port/gateway token, and confirm `<state-dir>/fleet/cells/<tenant>/` is really where a
   config write lands.
3. Stand up a real cell and hit its `/healthz` to see if it actually exists, or if `health` is
   WS-RPC-only as the protocol docs suggest.
4. Test one `openclaw cron add "<cron>" "<message>" --session isolated --agent ... --no-deliver`
   invocation end-to-end to confirm the agent actually receives and acts on it as a "scheduler
   turn," and to reveal the on-disk `jobs.json` schema if there is one.
