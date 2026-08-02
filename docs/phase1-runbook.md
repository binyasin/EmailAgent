# Phase 1 runbook — single-tenant local vertical slice

Goal: prove the core loop end-to-end — triage runs on real Gmail mail, a draft reply shows up in
the dashboard, a human approves it, and it actually sends — before any multi-tenant provisioning
exists.

## Prerequisites

- Docker + Docker Compose.
- A Google Cloud project with the Gmail API and Google Calendar API enabled and an OAuth 2.0
  **Web application** client (Google Cloud Console → APIs & Services → Credentials). Authorized
  redirect URI: `http://localhost:8000/api/v1/mailboxes/gmail/oauth/callback`.
- (Phase 2, optional if only testing Gmail) A Microsoft Entra ID (Azure AD) **app registration**
  with Microsoft Graph delegated permissions `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`,
  `User.Read`, `offline_access`, and a client secret. Redirect URI:
  `http://localhost:8000/api/v1/mailboxes/outlook/oauth/callback`.
- Node 22+ and Python 3.12+ installed locally (only needed to build the MCP servers and run
  migrations/seed from the host — the app services themselves run in containers).

## 1. Configure environment

```bash
cp .env.example .env
```

Fill in `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` from the Cloud Console credential,
and (if testing Outlook) `MS_OAUTH_CLIENT_ID` / `MS_OAUTH_CLIENT_SECRET` / `MS_OAUTH_TENANT_ID`
from the Entra app registration. Generate a real `TOKEN_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Build the gmail-mcp and outlook-mcp servers

The OpenClaw container launches these as local subprocesses (stdio MCP transport), so both need
to be built before `openclaw` starts — even if you only plan to connect one provider, since both
are wired into `dev-openclaw.json5`:

```bash
for pkg in gmail-mcp outlook-mcp; do
  (cd agent-runtime/mcp-servers/$pkg && npm install && npm run build)
done
```

## 3. Start postgres, control-plane, and dashboard (not openclaw yet)

```bash
docker compose -f infra/docker-compose.dev.yml up -d --build postgres control-plane dashboard
```

`openclaw` is deliberately left out of this first `up` — it needs `CELL_SERVICE_TOKEN` in `.env`
before it starts (gmail-mcp/outlook-mcp require it at process start), and that token doesn't
exist until step 4 mints one.

## 4. Run migrations, seed the dev org, and mint its cell service token

```bash
cd control-plane
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed_dev_org
cd ..
```

This creates a fixed `dev-org` org, prints a dev admin login (`admin@dev.local` / see script
output for the password), and prints a `CELL_SERVICE_TOKEN=...` line — copy that into `.env`.

## 5. Start openclaw

```bash
docker compose -f infra/docker-compose.dev.yml up -d openclaw
```

(Gateway on :18789, config from `agent-runtime/templates/dev-openclaw.json5`.) If you edit
`CELL_SERVICE_TOKEN` in `.env` after this container is already running, restart it to pick up
the new value: `docker compose -f infra/docker-compose.dev.yml restart openclaw`.

## 6. Connect Gmail and verify the loop

1. Open http://localhost:5173/login, log in with the seeded admin credentials.
2. Go to **Mailboxes** → **Connect Gmail** → complete the Google OAuth consent screen for a real
   or test Gmail account.
3. Send that mailbox a test email that clearly needs a reply (e.g. "Can you confirm you're free
   Thursday at 2pm?").
4. Trigger a run. In Phase 1 there's no scheduled heartbeat wired up yet, so trigger the agent
   manually — either via `openclaw`'s own CLI/dashboard against the running container
   (`docker compose exec openclaw openclaw ...` — exact subcommand depends on the installed
   OpenClaw version, see `docs/openclaw-integration-notes.md`), or by asking it directly through
   whatever interactive channel the container exposes.
5. In Gmail, confirm the thread received an `AI/Action-Needed` (or `AI/Urgent`) label from the
   `triage` skill.
6. In the dashboard's **Approval Inbox**, confirm a new draft appears with a matching subject and
   snippet.
7. Click **Approve & send**. Confirm:
   - The message appears in the Gmail account's **Sent** folder.
   - The draft's status flips to `sent` (refresh the inbox — it should disappear from the
     pending list).
8. Query the audit trail directly if needed:
   ```sql
   select action, resource_type, created_at from audit_logs order by created_at desc limit 10;
   ```
   You should see `mailbox.connected`, `draft.created`, and `draft.approved` entries.

## Phase 2 additions — Outlook, digest, scheduling

1. **Connect Outlook**: same as step 6.2 above but click **Connect Outlook**; completes a
   Microsoft identity platform OAuth flow instead of Google's.
2. **Scheduling**: send the connected mailbox a message like "Are you free Thursday at 2pm?".
   After a triage/scheduling run (trigger manually as in step 6.4), confirm: a **tentative**,
   self-only calendar hold appears on the connected calendar (no invite sent to the sender), and
   a draft proposing that time appears in the Approval Inbox.
3. **Digest**: rather than waiting for the real cron cadence in `dev-cron-jobs.json5`, manually
   trigger the `digest` skill the same way you trigger triage in step 6.4 (e.g. ask the agent
   directly to "run the digest skill now for the daily period"). Confirm a new entry appears in
   the dashboard's **Digests** view with the expected sections (Needs attention / Drafts awaiting
   review / Flagged for review).
4. Confirm `digest.created` appears in `audit_logs` alongside the Phase 1 entries.

## Phase 4 addition — observability stack

```bash
docker compose -f infra/docker-compose.dev.yml -f infra/docker-compose.observability.yml up -d
```

Adds Prometheus (http://localhost:9090, scraping control-plane's `/metrics`), Loki + Promtail
(shipping container logs), and Grafana (http://localhost:3000, default `admin`/`admin` —
change it on first login) pre-provisioned with a "EmailAgent — Control Plane Overview" dashboard
(request rate/latency, agent-cell counts by status, recent logs). `/healthz` is a cheap liveness
check; `/readyz` additionally pings the database — use `/readyz` for k8s/LB readiness probes.

## Troubleshooting

- **OAuth callback 404s / state mismatch**: the Phase 1/2 OAuth state map is in-process memory in
  `control-plane`; restarting that container mid-flow invalidates any in-flight OAuth attempt —
  just restart the connect flow from the dashboard.
- **MCP server can't reach the control plane**: confirm `CONTROL_PLANE_INTERNAL_URL` inside the
  `openclaw` container resolves to `http://control-plane:8000` (Docker Compose service DNS), not
  `localhost`.
- **`openclaw` container crash-loops on gmail-mcp/outlook-mcp startup**: `CELL_SERVICE_TOKEN` is
  missing or empty in `.env` — see step 4. It's required at process start, not lazily checked.
- **Token broker returns 401**: `CELL_SERVICE_TOKEN` is missing, malformed, or was minted for a
  different `JWT_SECRET_KEY` than the control plane is currently running with (e.g. `.env` changed
  and only one of the two services was restarted) — re-run `seed_dev_org` and update `.env` again.
- **Token broker 404 "No connected mailbox for tenant/provider"**: the OAuth flow for that
  provider didn't complete yet.
- **Outlook OAuth exchange fails with "did not return a refresh_token"**: the Entra app
  registration's requested scopes are missing `offline_access`, or admin consent hasn't been
  granted for the delegated permissions — check the app registration's API permissions blade.
- **`create_event` succeeds but the other party got an invite anyway**: this shouldn't happen —
  `gmail-mcp`'s `create_event` always passes `sendUpdates: "none"` and `outlook-mcp`'s always sets
  `showAs: "tentative"` with no attendees; if you see an invite, treat it as a bug in those tools,
  not expected behavior.
