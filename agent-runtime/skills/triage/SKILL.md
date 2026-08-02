---
name: triage
description: Classify incoming email into urgent/action-needed/fyi/newsletter and apply Gmail/Outlook labels accordingly.
requires:
  bins: []
  env: []
---

# Email Triage

You classify newly arrived email so the inbox stays organized without a human having to sort it
by hand. You only ever **read and label** — you never draft, send, delete, or archive anything in
this skill (drafting is the `draft-reply` skill's job).

## When this runs

Triggered by the heartbeat, or on demand, to process threads that don't yet have an `AI/*`
triage label applied.

## Steps

1. Call `search_threads` with a query that finds unlabeled recent mail, e.g.
   `-label:AI/Urgent -label:AI/Newsletter -label:AI/Action-Needed -label:AI/FYI newer_than:2d`.
2. For each thread, call `get_thread` to read the latest message's subject, sender, and body.
3. Classify into exactly one primary category:
   - **Urgent** — time-sensitive, from a person (not automated), asks for something now or today.
   - **Action-Needed** — requires a reply or decision, but not urgent.
   - **Newsletter** — bulk/marketing/automated digest content.
   - **FYI** — informational, no reply expected.
4. Call `list_labels`; if the corresponding `AI/Urgent`, `AI/Action-Needed`, `AI/Newsletter`, or
   `AI/FYI` label doesn't exist, call `create_label` to create it first.
5. Call `label_thread` to add the matching label.
6. If the sender or content looks like a phishing attempt, a credential reset request, or a
   request for money/financial account details: stop here and follow the
   `sensitive-content-flagging` skill's steps instead of continuing this run's category labeling
   — that skill owns the `AI/Sensitive` label and its own handling. Err on the side of deferring
   to it when unsure.
7. If a `vip-list.md` file exists in the workspace and the sender's address matches an entry in
   it: stop here and follow the `vip-escalation` skill's steps instead — that skill owns the
   `AI/VIP` label and decides whether auto-drafting proceeds.

## What NOT to do

- Never delete, archive, or mark-as-read.
- Never apply more than one primary `AI/*` category label to the same thread in a single run.
- Never invent a label name outside the four categories above (plus `AI/Sensitive`, which is
  owned by `sensitive-content-flagging`).
