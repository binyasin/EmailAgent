---
name: vip-escalation
description: Escalate mail from an org's VIP senders with an urgent label and, by default, hold back auto-drafting so a human replies personally.
requires:
  bins: []
  env: []
---

# VIP Escalation

You give special handling to mail from senders the org has designated as VIPs (read from
`vip-list.md` in the workspace — one email address or `@domain` per line, populated via the
dashboard's Skill Settings screen or by editing the file directly). VIP senders get faster
visibility, not necessarily an automated reply — the default assumption is that these
relationships are important enough to warrant the user's own words.

## When this runs

Called by the `triage` skill whenever a thread's sender address matches an entry in
`vip-list.md` (exact address match, or domain match for `@domain` entries).

## Steps

1. Call `list_labels`; create `AI/VIP` and `AI/Urgent` via `create_label` if either doesn't
   exist yet.
2. Call `label_thread` to add both `AI/VIP` and `AI/Urgent`, regardless of what `triage`'s
   content-based classification concluded.
3. By default, do **not** proceed to `draft-reply` or `scheduling` for this thread — VIP mail is
   surfaced (via the label, and via the digest's "Needs attention" section) for the human to
   answer directly, rather than auto-drafted.
4. Exception: if the workspace contains a file named `ALLOW_VIP_AUTODRAFT.md`, auto-drafting for
   VIP senders is allowed — in that case, continue to the `draft-reply` (or `scheduling`, if
   applicable) skill's steps as normal after finishing step 2.

## What NOT to do

- Never remove the `AI/VIP` or `AI/Urgent` label once applied, even in later runs.
- Never treat a sender as VIP based on your own judgment of "this seems important" — only exact
  matches against `vip-list.md` count; use `triage`'s normal urgency classification for everyone
  else.
