---
name: unsubscribe-cleanup
description: Identify low-engagement bulk senders and propose (never auto-execute) cleanup via a label the human reviews and acts on.
requires:
  bins: []
  env: []
---

# Unsubscribe Cleanup

You identify newsletters and other bulk mail the user consistently ignores, and surface a
cleanup suggestion — you never unsubscribe, archive, or delete anything yourself. Unsubscribe
links are a known phishing/tracking vector, and archiving is a judgment call that belongs to the
user, not the agent.

## When this runs

Triggered alongside `digest` generation (weekly cadence is usually sufficient — this doesn't
need to run on every heartbeat tick).

## Steps

1. Call `search_threads` for mail labeled `AI/Newsletter` (applied by `triage`) received in the
   last 30 days.
2. For senders with multiple `AI/Newsletter` messages in that window where none appear to have
   been opened/replied to (use whatever read-state signal the provider's message metadata
   exposes), identify them as cleanup candidates.
3. Call `list_labels`; create `AI/Unsubscribe-Candidate` via `create_label` if it doesn't exist.
4. Call `label_thread` (on the most recent message from each candidate sender is sufficient —
   no need to label every historical message) to add `AI/Unsubscribe-Candidate`.
5. Do not take any further action. The `digest` skill's "Cleanup suggestions" section (see its
   SKILL.md) is responsible for surfacing these candidates to the human; this skill's job ends at
   labeling.

## What NOT to do

- Never call any tool that unsubscribes, deletes, or archives — no such tool is available to
  this skill for exactly that reason.
- Never flag a sender the user has recently replied to or forwarded mail from, even if most of
  their mail goes unread — an occasional reply signals the relationship still matters.
- Never re-flag a sender that already has an unresolved `AI/Unsubscribe-Candidate` label from a
  previous run.
