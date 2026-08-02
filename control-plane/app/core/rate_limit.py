"""Rate limiting, keyed by remote IP. `limiter` is attached to `app.state`
in main.py; individual routes opt in with `@limiter.limit("N/period")`.

Starting with just `/auth/login` — unlimited login attempts is a classic
brute-force/credential-stuffing vector, and it's the one endpoint that's
reachable with no prior authentication at all, unlike the org-scoped API
which at least requires a valid JWT first. Other endpoints can gain limits
as needed; this isn't meant to be a blanket global limiter.

Caveat: in a multi-replica deployment this is per-process, in-memory
(slowapi's default), so the effective limit is N × replica count, not a
strict global N. A shared backend (Redis) would fix that — not needed at
this scale/threat model yet, but noted rather than silently assumed away.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
