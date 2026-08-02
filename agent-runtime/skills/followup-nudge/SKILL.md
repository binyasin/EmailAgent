---
name: followup-nudge
description: Surface threads the user sent that have gone unanswered past a threshold, so nothing important is silently forgotten.
requires:
  bins: []
  env: []
---

# Follow-up Nudge

You catch threads where the user sent a message and never got a reply, so they can decide
whether to follow up — you only read and label, you never draft or send a follow-up yourself.

## When this runs

Triggered periodically (every few hours is reasonable — frequent enough to be useful, infrequent
enough not to relabel the same threads repeatedly) rather than on every heartbeat tick.

## Steps

1. Call `search_threads` for threads where the latest message was sent **by the user** (not
   received) more than 3 business days ago, excluding threads already labeled
   `AI/Awaiting-Reply` or `AI/VIP` (VIP threads are the human's own responsibility to track, not
   this skill's).
2. For each match, call `get_thread` to confirm no reply has since arrived (search results can
   lag) and that the message genuinely expected a response (not a pure FYI/no-reply-needed
   message — skip anything that reads like a heads-up rather than a question or request).
3. Call `list_labels`; create `AI/Awaiting-Reply` via `create_label` if it doesn't exist.
4. Call `label_thread` to add `AI/Awaiting-Reply`.
5. Do not take any further action — the label itself, plus this label's inclusion in the
   `digest` skill's summary, is the notification mechanism.

## What NOT to do

- Never draft or send a follow-up message on the user's behalf.
- Never nudge on a thread where the most recent message (from either party) is less than 3
  business days old.
- Never remove the `AI/Awaiting-Reply` label yourself — it should only come off once the other
  party actually replies (at which point `triage` will naturally not re-flag it, since the
  latest message is no longer from the user).
