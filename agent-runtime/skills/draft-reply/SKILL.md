---
name: draft-reply
description: Draft a reply to a thread in the user's voice for human review. Never sends — no send-capable tool exists.
requires:
  bins: []
  env: []
---

# Draft Reply

You write suggested reply drafts for a human to review, edit, and approve. **You cannot send
email as part of this skill** — there is no send-capable tool available to you, by design. Your
only output is a draft.

## When to draft a reply

- The thread is labeled `AI/Action-Needed` or `AI/Urgent` by the `triage` skill, and
- The thread is **not** labeled `AI/Sensitive` (see `sensitive-content-flagging` — never
  auto-draft on flagged threads, a human should look at those directly), and
- The thread is **not** labeled `AI/VIP` unless a workspace file named
  `ALLOW_VIP_AUTODRAFT.md` exists (see `vip-escalation` — by default VIP senders get a personal
  reply from the human, not an auto-draft), and
- The thread does not already have a pending draft (check `list_drafts` first, matched by
  `threadId`, to avoid creating duplicates).

## Steps

1. Call `get_thread` to read the full conversation history for context and tone.
2. Read `_shared/style-guide.md` (and, if present in the workspace, `style-profile.md` — a
   per-tenant file capturing the user's typical tone, sign-off, and phrasing learned from past
   approved/edited drafts) to match the user's voice.
3. Compose a reply that:
   - Directly answers or acknowledges the specific ask in the latest message.
   - Matches the user's typical tone and length (see style guide) — do not pad with unnecessary
     pleasantries if the user's style is terse, and vice versa.
   - Leaves placeholders like `[confirm date]` for any fact you are not confident about rather
     than guessing.
4. Call `create_draft` with `to`, `subject` (reuse the thread's subject, prefixed `Re:` if not
   already), `body`, and `threadId`/`inReplyToMessageId` so it threads correctly.
5. Stop. Do not attempt to notify the user by any other means — `create_draft` already surfaces
   the draft in their approval inbox.

## What NOT to do

- Never call any tool other than `get_thread`, `list_drafts`, `create_draft`, or `update_draft`
  from this skill.
- Never claim in the draft body that the email has been sent, scheduled, or actioned — it has
  not, until a human approves it.
- Never draft a reply that commits to a specific date, price, or legal/contractual statement
  unless that exact commitment already appears verbatim earlier in the thread.
