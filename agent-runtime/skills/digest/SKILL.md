---
name: digest
description: Produce a daily/weekly summary of inbox activity — triaged threads, pending drafts, and open nudges — and notify the control plane it's ready.
requires:
  bins: []
  env: []
---

# Digest

You produce a periodic (daily or weekly, per the org's configured cadence) summary of inbox
activity so the human doesn't have to read every message to stay oriented. You only read and
summarize — you never label, draft, or send anything in this skill.

## When this runs

Triggered by a cron job (see `docs/openclaw-integration-notes.md` for the cron config schema)
at the org's configured cadence and timezone — not on every heartbeat tick.

## Steps

1. Call `search_threads` (or the provider-equivalent) to gather:
   - Threads labeled `AI/Urgent` or `AI/Action-Needed` since the last digest.
   - Threads currently in `list_drafts` awaiting human approval.
   - Any threads flagged `AI/Sensitive` since the last digest (surface these prominently — a
     human should see these regardless of how busy the digest is).
   - Threads labeled `AI/Awaiting-Reply` by the `followup-nudge` skill.
   - Senders labeled `AI/Unsubscribe-Candidate` by the `unsubscribe-cleanup` skill.
2. For each item, keep the summary to one line: sender, subject, and why it matters (e.g. "needs
   a reply by Friday" or "draft ready for review").
3. Group the summary into five sections: **Needs attention**, **Drafts awaiting your review**,
   **Flagged for review** (sensitive-content items), **Awaiting a reply from them** (nudges), and
   **Cleanup suggestions** (unsubscribe candidates).
4. If there is nothing to report in a section, omit that section entirely rather than writing
   "nothing to report" — keep the digest short.
5. Call the `notify_digest_ready` tool with the assembled summary text and the period
   (`daily`/`weekly`) so the control plane can store it and surface it in the dashboard's Digest
   view. Do not attempt to email the digest directly — the dashboard is the delivery channel.

## What NOT to do

- Never include full email bodies in the digest — one-line summaries only, both to keep it
  readable and to avoid unnecessarily duplicating sensitive content outside the mailbox itself.
- Never re-summarize a thread that was already included in the previous digest unless its status
  has changed (e.g. moved from "needs attention" to "draft ready").
