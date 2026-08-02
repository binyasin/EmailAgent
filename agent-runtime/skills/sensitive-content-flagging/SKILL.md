---
name: sensitive-content-flagging
description: Flag phishing, credential-harvest, and financial-request threads so a human reviews them directly; suppresses auto-drafting on flagged threads.
requires:
  bins: []
  env: []
---

# Sensitive Content Flagging

You identify threads that need a human's direct attention because they involve security or
financial risk, rather than routine correspondence. You only ever **read and label** — you never
draft a reply, delete, or take any remediation action yourself.

## When this runs

Called by the `triage` skill (as of this skill existing, `triage` should defer to these steps
in full rather than its own inline check) whenever a thread shows signs of:

- A request to reset a password, verify an account, or "confirm your identity" via a link.
- A request to transfer money, change payment/bank details, or pay an invoice unexpectedly.
- A sender address that doesn't match the claimed sender identity (e.g. display name says
  "IT Support" but the address is an unrelated free-mail domain).
- Urgency/pressure language combined with any of the above ("act now", "your account will be
  closed today").

## Steps

1. Call `get_thread` to read the full message, including sender address and any links or
   attachments referenced in the body text.
2. If it matches any pattern above, call `list_labels`; create `AI/Sensitive` via `create_label`
   if it doesn't exist yet.
3. Call `apply_sensitive_thread_label` with a short, specific `reason` (e.g. "sender domain
   mismatch + urgent payment request" — specific enough that a human skimming the label later
   understands why without re-reading the thread).
4. Stop. Do not call `create_draft`, `label_thread` with any other category, or any calendar
   tool for this thread in this run — a flagged thread should look untouched except for the one
   new label until a human looks at it.

## What NOT to do

- Never conclude a thread is "probably fine" and skip flagging when you are genuinely unsure —
  the cost of a human spending 30 seconds dismissing a false positive is far lower than the cost
  of a missed phishing attempt reaching the inbox unflagged.
- Never click, fetch, or otherwise resolve any link found in the message content.
- Never mention in any tool call or elsewhere that you've concluded a specific attempt is
  malicious with certainty — flag with your reasoning; let the human make the final call.
