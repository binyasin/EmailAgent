# OpenClaw integration notes

Originally these facts were gathered secondhand and flagged "verify before relying on." Later
passes verified against the real `docs.openclaw.ai` (fetched directly) and the OpenClaw source
(`github.com/openclaw/openclaw`, cloned directly). Findings below are marked **RESOLVED**
(confirmed, code updated to match), **PARTIALLY RESOLVED** (confirmed enough to fix the known bug,
but a detail remains open), or **STILL OPEN** (needs more confirmation).

## Live-verified against a real install (2026-08-02)

Everything above was "docs/source say X" until this pass, which installed and ran actual
`openclaw` binaries (an isolated `--dev` Gateway process, plus a separate isolated `npm install
openclaw@beta` — neither touched the user's real global install, config, or state). Key results:

- **`fleet` does not exist on the `stable` channel** (the user's installed version,
  `2026.7.1-2`) — `openclaw fleet` fails with "Unknown command." It exists only on the **`beta`**
  channel (`2026.7.2-beta.7`), explicitly labeled "(experimental)" in its own `--help` output.
  **This means the this repo's entire Fleet-based multi-tenant cell architecture depends on a
  feature that isn't in OpenClaw's stable release.** Anyone deploying this for real needs to run
  their OpenClaw hosts on the beta channel, with whatever stability/support tradeoffs that implies
  — this is a product decision worth surfacing, not just an implementation detail.
- On the beta binary, `fleet create/status/rm --help` output matches this repo's
  (already-corrected) `fleet_cli.py` flag-for-flag: no `--config-dir` flag exists, `--no-start` /
  `--json` / `--gateway-token` / `--port` / `--memory` / `--cpus` / `--runtime` / `--env` all
  present on `create`; `--force`/`--purge-data` on `rm`. Could not test an actual `fleet create`
  end-to-end — no Docker/Podman available in this environment — so the exact `--json` output keys
  for host port/gateway token are still unconfirmed.
- **`/healthz` and `/readyz` are real** — confirmed by running `openclaw --dev gateway run --auth
  token ...` and curling both: `{"ok":true,"status":"live"}` / `{"ready":true,"failing":[],...}`.
  `GatewayClient.is_live()`/`is_ready()` were correct all along.
- **Ran the actual Python `GatewayClient.trigger_run()` against the live Gateway and got a full
  connect → `agent` → `agent.wait` round trip to complete**, returning a real terminal snapshot
  (`{"runId": ..., "status": "error", "endedAt": ..., "error": "FailoverError: No API key found
  for provider \"openai\"..."}` — the "error" is just the throwaway dev profile having no model
  auth configured; the protocol round trip itself succeeded). This is the strongest evidence yet
  that the Gateway RPC design in this repo is correct. Three real bugs were found and fixed via
  this live test, none of which were visible from docs alone:
  - `client.id` and `client.mode` are **closed enums**, not free-form strings — the Gateway
    rejected `"emailagent-control-plane"` / `"operator"` with `must be equal to one of the allowed
    values`. Correct generic values (from the SDK's own `client-info.ts`, read out of the beta
    package's dist bundle): `client.id: "gateway-client"`, `client.mode: "backend"`.
  - The `agent` RPC's prompt field is named **`message`, not `prompt`** as the docs-search summary
    claimed.
  - **`idempotencyKey` is required** on the `agent` RPC, not optional as the docs-search summary
    claimed — `gateway_client.py` now generates one (`uuid.uuid4()`) per call.
  - (Not a bug, just an operational note: the agent id used in a real `agent` RPC call must match
    a configured agent, e.g. `openclaw agents list` — a fresh dev profile only has one, named
    `dev`.)
- `stream_session_events` (`sessions.messages.subscribe`) was **not** exercised live this pass —
  still only verified against the in-process fake server, not a real Gateway.

## Fleet CLI surface — RESOLVED (and beta-channel-only, confirmed live)

Confirmed against `docs.openclaw.ai/cli/fleet` and, since this pass, a real beta-channel install
(see "Live-verified" above — **`fleet` is not in the `stable` channel at all**). Fleet is
explicitly documented, and confirmed live, as experimental: "command names, flags, output shapes,
and the container profile can change between releases without a deprecation window."

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
— plausible given the flag names `--port`/`--gateway-token`, confirmed live via `--help`, but no
Docker/Podman was available in this pass to actually run `fleet create` and see a real payload).
`list`, `logs`, `backup`, `restore`, `doctor`, `upgrade` aren't wired into `CellProvisioner` yet —
not needed for Phase 3 provisioning, but worth adding once an admin cells-ops UI needs them.

## Gateway WebSocket RPC protocol (v4) — RESOLVED, blocker was wrong

Confirmed against `docs.openclaw.ai/gateway/protocol`, `/gateway/external-apps`, `/reference/rpc`,
and — because the docs site alone left the signing question unanswered — the OpenClaw source
itself (`github.com/openclaw/openclaw`, `main` branch, read directly via a shallow clone; not
guessed). Connection: server sends `{type: "event", event: "connect.challenge", payload: {nonce,
ts}}`, client replies with a `connect` request, server answers `hello-ok`. Protocol v4 current, v3
supported for one version back. Request/response envelope: `{type: "req", id, method, params}` →
`{type: "res", id, ok: true, payload}` or `{..., ok: false, error: {code, message, details,
retryable, retryAfterMs}}`; out-of-band updates arrive as `{type: "event", event, payload}`.
Pre-auth frames capped at 64 KiB; post-auth cap comes from `hello-ok.policy.maxPayload` (default 25
MB); server sends `tick` keepalives at `policy.tickIntervalMs`, and silence beyond 2x that triggers
a client-side close (code 4000).

RPC method shapes: `agent` (params, **live-confirmed** by running it against a real Gateway —
see "Live-verified" above: `message` required — not `prompt` as the docs-search summary said —
and `idempotencyKey` required, contradicting the docs-search summary's "optional." `agentId` was
always sent in this pass's test calls, so whether it's truly required or just validated-when-
present wasn't isolated; `model`/`deliver`/`bestEffortDeliver` untested, still per the original
docs-search summary) paired with `agent.wait` (params: `runId`) — the pairing
`/gateway/external-apps` explicitly recommends for external integrations. Session-scoped
alternative: `sessions.create` (params: `model`/`thinkingLevel`/`worktree`/`parentSessionKey`/...,
returns `sessionKey`) → `sessions.send` (params: `key`, `message`, `queueMode`, ...). Streaming:
`sessions.messages.subscribe` (params: `sessionKey`, `includeApprovals`); broadcast event families
are `chat`, `session.message`, `session.operation`, `session.observer`.

**The "device signing is mandatory for every connection" blocker from the previous pass was
wrong** — that was an overread of a docs-search summary, and the source code contradicts it
directly. Server-side, `verifyGatewayConnectDeviceProof` in
`src/gateway/server/ws-connection/connect-device-proof.ts` opens with `if (!device) { return {
ok: true, devicePublicKey: null, ... } }` — an absent `device` object is explicitly accepted, not
rejected. Client-side, `packages/gateway-client/src/client.ts`'s `buildDeviceConnectParams`
returns `undefined` whenever no `deviceIdentity` is configured. Device signing is only exercised
for the **paired end-user device** flow (phone/CLI pairing with persistent identity); it is not
required for plain shared-secret auth. `src/gateway/auth.ts` treats `"token"` as a first-class,
independent auth method alongside `"password"`/`"tailscale"`/`"trusted-proxy"`. The top-level
connect roles are only `"operator"` and `"node"` (`src/gateway/role-policy.ts`) — "worker" in the
earlier docs-search summary refers to a separate, unrelated low-level protocol for local
inference-worker processes, not a connect-handshake role.

**Conclusion: `GatewayClient` can be a plain token-auth WS client.** Connect with `role:
"operator"`, `auth: {token: <gateway_token>}`, and omit `device` entirely — no keypair, no
signing, no device pairing/approval flow needed. This fully resolves what was reported as a hard
blocker; `trigger_run`/`stream_session_events` are implementable now. (For completeness, since it
was tracked down anyway: device signing, when used, is Ed25519 — Node's
`crypto.generateKeyPairSync("ed25519")`, PEM-encoded PKCS8/SPKI keys, `crypto.sign(null, payload,
privateKey)` over a pipe-delimited payload string, output base64url-encoded; device id is the
sha256 hex digest of the raw 32-byte public key. See
`src/infra/{device-identity,ed25519-signature}.ts` if the paired-device flow is ever needed for a
different feature.)

**Resolved live**: despite the WS protocol docs only describing a `health` RPC method, `/healthz`
and `/readyz` are real HTTP routes — confirmed by running a real Gateway and curling both (see
"Live-verified" above). `GatewayClient.is_live()`/`is_ready()` are correct.

**Also resolved live, provisionally**: `role: "operator"` with only a shared token (no device) was
sufficient to successfully call `agent` and `agent.wait` against a real (dev-profile, default
`--auth token`) Gateway — no `operator.admin` or extra scope was needed for this pairing. That's
one data point on one dev config, though, not a guarantee across every `gateway.auth` mode; worth
re-confirming against a production-shaped Gateway config before relying on it fully.

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

## Model provider auth (`models` config key) — confirmed via docs, not yet live-verified

This is the missing piece behind the `FailoverError: No API key found for provider "openai"` seen
in the live Gateway RPC test above — the throwaway dev profile used for that test had no `models`
config at all. Confirmed against `docs.openclaw.ai/gateway/configuration-reference`:
`models.providers.<name>.apiKey` accepts either a plaintext string or a `${VAR}` env-interpolation
reference (same substitution syntax already used for `CELL_SERVICE_TOKEN` in `mcp.servers.*.env`
— only uppercase `[A-Z_][A-Z0-9_]*` names are recognized, and a missing/empty variable throws at
config load) or a `SecretRef` object (`{ source: "env", provider: "default", id: "..." }`).

Wired in as `models.providers.anthropic.apiKey: "${ANTHROPIC_API_KEY}"` in both
`agent-runtime/templates/openclaw.json5.jinja` and `agent-runtime/templates/dev-openclaw.json5`.
The variable itself is sourced from `Settings.anthropic_api_key` (`control-plane/app/core/config.py`,
env var `ANTHROPIC_API_KEY`, set in `.env`) and injected two different ways depending on which
OpenClaw deployment path is in play:

- **Phase 1/2 single-tenant dev container** (`infra/docker-compose.dev.yml`'s `openclaw` service):
  already loads the whole `../.env` file via `env_file`, so no extra wiring was needed there beyond
  adding the key to `.env`.
- **Phase 3 per-tenant Fleet cells** (`app/workers/provision_cell.py`): env vars are passed
  explicitly and allow-listed via `--env KEY=VALUE` on `fleet create` (not inherited from the
  control-plane process), same as `CELL_SERVICE_TOKEN`/`TENANT_ID` already were — so
  `ANTHROPIC_API_KEY` was added to that `env={...}` dict alongside them.

**Still open**: not yet live-verified against a real Gateway the way the Fleet CLI surface and the
`agent`/`agent.wait` RPC round trip were — no real `ANTHROPIC_API_KEY` was exercised against a live
`openclaw` process in this pass, so whether the Gateway actually resolves `${ANTHROPIC_API_KEY}` at
config-load time exactly as documented (versus e.g. requiring `models.providers.anthropic.models`
to also list at least one allowed model id) remains to be confirmed the same way the RPC blocker
above was — by running a real Gateway and a real `agent`/`agent.wait` call and checking the
`FailoverError` is gone.

**Gemini (`models.providers.google`) — weaker source than the Anthropic entry above.** The main
`/gateway/configuration-reference` page does not itself document a Google/Gemini provider entry
(only Anthropic and OpenAI examples appear there); the provider key `google` and the
`api: "google-generative-ai"` adapter field (as opposed to `google-vertex`, a separate adapter for
Vertex AI's different auth mechanism) came from a docs-search summary of
`/gateway/config-tools#custom-providers-and-base-urls`, not a page fetch confirmed side-by-side
with a real install the way the Fleet CLI and RPC findings above were. Wired in as
`models.providers.google: { apiKey: "${GEMINI_API_KEY}", api: "google-generative-ai" }` in the same
two template files, `Settings.gemini_api_key` (env var `GEMINI_API_KEY`), and the same
`fleet create --env` list in `provision_cell.py`. If a real install rejects the `api` field or uses
a different provider key, this is the first place to check — ideally via `openclaw config schema`
against a real install, which the config-tools page itself suggests as the authoritative source.

**OpenRouter (`models.providers.openrouter`) — same weaker source, one level further out.**
OpenRouter isn't a named provider in either OpenClaw doc page fetched so far; it has to go in as a
**custom provider** (the `/gateway/config-tools#custom-providers-and-base-urls` mechanism used for
things like Cerebras/Kimi/MiniMax/Moonshot in that page's own examples), which per a docs-search
summary of that page requires a provider-ID key, `baseUrl`, `apiKey`, and an `api` adapter field —
picked `api: "openai-completions"` since OpenRouter exposes an OpenAI-compatible chat completions
endpoint, one of the adapter values a follow-up docs-search summary listed as valid (alongside
`openai-responses`, `anthropic-messages`, `google-generative-ai`, `google-vertex`,
`github-copilot`, `bedrock-converse-stream`, `ollama`, `azure-openai-responses`). Wired in as
`models.providers.openrouter: { baseUrl: "https://openrouter.ai/api/v1", apiKey:
"${OPENROUTER_API_KEY}", api: "openai-completions" }` in both template files,
`Settings.openrouter_api_key` (env var `OPENROUTER_API_KEY`), and the same `fleet create --env`
list.

**`models` allowlist — added 2026-08-04, ids verified live against OpenRouter's own catalog.** The
user initially asked for `deepseek/deepseek-chat` and `anthropic/claude-sonnet-4.5`; a direct fetch
of `https://openrouter.ai/api/v1/models` (OpenRouter's own API, not an OpenClaw doc) found **neither
id exists** — confirmed by a substring search of the raw response, not just a summary skim. Real
current ids, with `context_length`/`top_provider.max_completion_tokens` read verbatim from that
same response: `anthropic/claude-sonnet-5` (name "Anthropic: Claude Sonnet 5", context 1,000,000,
max completion 128,000) and `deepseek/deepseek-v4-flash-0731` (name "DeepSeek: DeepSeek V4 Flash
0731", context 1,048,576, max completion 65,536). User confirmed both substitutions before they
were written into config. Mapped into the provider's `models: [...]` array as `id`/`name`/
`contextWindow`/`maxTokens` per the config-tools custom-provider example shape. **Still open**:
whether OpenClaw's own schema wants exactly these field names (`contextWindow`/`maxTokens`) or
something else, since this array's shape itself is still only sourced from a docs-search summary,
not a page fetch — same caveat as the rest of this OpenRouter section.

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
- `control-plane/app/services/gateway_client.py`: implemented `trigger_run`/`stream_session_events`
  as a real token-auth WebSocket client (`role: "operator"`, `auth.token`, no device object),
  then corrected against a live Gateway: `client.id`/`client.mode` are closed enums
  (`"gateway-client"`/`"backend"`), the `agent` RPC field is `message` not `prompt`, and
  `idempotencyKey` is required.
- `agent-runtime/templates/dev-cron-jobs.json5`: corrected the "injected as if a channel message"
  framing and the flag syntax (positional cron-expr/message, `--session`, `--agent`); documented
  the real `openclaw cron add` equivalent command.
- `agent-runtime/templates/openclaw.json5.jinja`, `dev-openclaw.json5`: added
  `models.providers.anthropic.apiKey: "${ANTHROPIC_API_KEY}"`,
  `models.providers.google: { apiKey: "${GEMINI_API_KEY}", api: "google-generative-ai" }`, and
  `models.providers.openrouter: { baseUrl: "https://openrouter.ai/api/v1", apiKey:
  "${OPENROUTER_API_KEY}", api: "openai-completions" }` so cells actually have LLM provider auth
  (see "Model provider auth" above). `control-plane/app/core/config.py`: added
  `anthropic_api_key`/`gemini_api_key`/`openrouter_api_key` settings.
  `control-plane/app/workers/provision_cell.py`: added `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/
  `OPENROUTER_API_KEY` to the Fleet cell's `--env` on create.

## Still not exercised against a real install

The Gateway RPC connect→`agent`→`agent.wait` path is now live-verified (see "Live-verified"
above), and `/healthz`/`/readyz` and the Fleet CLI flag surface are confirmed too. What's left, in
priority order:

1. **A real `fleet create`** — no Docker/Podman was available in this pass, so the actual cell
   lifecycle (create → config write → start) and the `--json` output shape for host port/gateway
   token are still unconfirmed beyond `--help` text. This needs a host with a container runtime.
   Checked twice (2026-08-02): neither this dev machine (no Docker/Podman, and WSL isn't even
   installed — `wsl --list` fails with `REGDB_E_CLASSNOTREG`) nor a remote cloud sandbox agent had
   Docker available. Deliberately not faked — the remote agent correctly stopped rather than run
   `fleet create` without a real container runtime backing it. Needs an environment with Docker or
   Podman actually running (a CI runner, a cloud box, or Docker Desktop installed locally).
2. **`stream_session_events`** (`sessions.messages.subscribe`) — implemented and unit-tested
   against the fake server, but not yet run against a real Gateway the way `trigger_run` was.
3. **A real `openclaw cron add`** invocation, to confirm the agent actually receives and acts on a
   scheduler-run turn as expected, and to see whether it's really CLI-only or has a companion
   `cron.*` RPC path worth using instead (see the cron section above).
4. Whether `role: "operator"` + shared token holds up against a Gateway with a stricter
   `gateway.auth`/scopes configuration than the default dev profile used in this pass.
5. Helm chart (`helm lint`/`helm template`) and Stripe billing against a real test-mode account —
   untouched by this or the previous verification passes.
4. Test one `openclaw cron add "<cron>" "<message>" --session isolated --agent ... --no-deliver`
   invocation end-to-end to confirm the agent actually receives and acts on it as a "scheduler
   turn," and to reveal the on-disk `jobs.json` schema if there is one.
