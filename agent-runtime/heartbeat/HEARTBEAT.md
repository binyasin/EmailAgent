# Heartbeat instructions

On each heartbeat tick:

1. Run the `triage` skill's steps against any thread that doesn't yet have an `AI/*` category
   label applied and arrived since the last tick.
2. For any thread the `triage` skill just labeled `AI/Urgent` or `AI/Action-Needed` (and that
   isn't `AI/Sensitive`), follow the `scheduling` skill's steps first if it looks like a
   scheduling request, otherwise follow the `draft-reply` skill's steps.
3. If nothing new needed triage or drafting this tick, do nothing further — do not report "no new
   mail" or otherwise produce output. Silence is the correct outcome for most ticks.

Do **not** run the `digest` skill from the heartbeat — digest generation is driven by its own
cron schedule (see `agent-runtime/templates/dev-cron-jobs.json5`), not every heartbeat tick, so
digests stay periodic rather than firing on every wake-up.
