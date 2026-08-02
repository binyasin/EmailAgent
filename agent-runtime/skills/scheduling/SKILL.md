---
name: scheduling
description: Detect meeting-scheduling requests, propose a tentative calendar hold, and draft a confirming reply for human review.
requires:
  bins: []
  env: []
---

# Scheduling

You handle threads that are asking to schedule a meeting or call. Like `draft-reply`, you never
send anything and you never create a calendar event that notifies the other party — you only
create a **tentative, self-only** hold and a **draft** reply, both of which a human must approve
before anything becomes real to the other side.

## When to act

The thread is labeled `AI/Action-Needed` or `AI/Urgent` by the `triage` skill, and its content
is asking to schedule, reschedule, or confirm a meeting/call time (look for phrases like "are you
free", "can we schedule", "does Thursday work", proposed specific date/times, etc.).

## Steps

1. Call `get_thread` to read the full request, including any specific times already proposed by
   the other party.
2. If specific candidate times were proposed, call `find_availability` (or `list_events` to
   inspect existing commitments) for those windows to check for conflicts. If no specific time
   was proposed, use `find_availability` to identify 2-3 open windows in the next 5 business days
   that roughly match any stated constraints (e.g. "sometime next week", "afternoons only").
3. Call `create_event` for **one** best-candidate time, as a tentative, self-only hold — this
   reserves the slot on the user's own calendar without notifying or inviting the other party.
4. Follow the `draft-reply` skill's steps to compose a reply that proposes that time (or the 2-3
   candidate windows, if no single time was clearly best) and asks for confirmation. Explicitly
   phrase it as a proposal ("Does 2pm ET on Thursday work?"), not a confirmed booking — the
   calendar hold is tentative and the invite hasn't gone out yet.
5. Call `create_draft` exactly as `draft-reply` does. Stop there.

## What NOT to do

- Never create a calendar event that emails an invite to the other party — only `create_event`
  calls that keep the event self-only/no-notification are allowed.
- Never tell the other party in the draft that the meeting is confirmed or booked — only that a
  time is proposed, pending their confirmation and the user's approval of this draft.
- Never double-book: if `find_availability`/`list_events` shows a conflict for every candidate
  window, say so in the draft honestly and ask the sender for alternatives rather than picking a
  conflicting time.
