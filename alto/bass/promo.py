"""The free-credit promo cutoff: ONE place. Live Bass refuses from CUTOFF_UTC (promo end minus a one-hour margin), fail closed.

The promo's free credit ends at PROMO_END_UTC. After that, Anthropic would bill purchased credit that the Console's own limit would not stop,
so every LIVE entry point (the local reserve's holds, make_client("live"), bass_local_server --live, bass_live_check) calls check() first and
makes no request when it raises BassError(code="promo_ended"). Mock paths never call it. The clock is the caller's injectable clock; one that
cannot be read, is not a timezone-aware datetime, or reads before SANE_AFTER_UTC counts as past the cutoff."""
from __future__ import annotations

import datetime as dt
from typing import Callable

from .errors import BassError

PROMO_END_UTC = dt.datetime(2026, 11, 19, 0, 0, tzinfo=dt.timezone.utc)
MARGIN = dt.timedelta(hours=1)
CUTOFF_UTC = PROMO_END_UTC - MARGIN                         # 18 Nov 2026 23:00Z
SANE_AFTER_UTC = dt.datetime(2026, 11, 1, 0, 0, tzinfo=dt.timezone.utc)


def _default_clock() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _now(clock: Callable[[], dt.datetime] | None) -> dt.datetime | None:
    try:
        t = (clock or _default_clock)()
        if isinstance(t, dt.datetime) and t.tzinfo is not None and t.utcoffset() is not None:
            return t.astimezone(dt.timezone.utc)
    except Exception:
        pass
    return None


def live_allowed(clock: Callable[[], dt.datetime] | None = None) -> bool:
    t = _now(clock)
    return t is not None and SANE_AFTER_UTC <= t < CUTOFF_UTC


def check(clock: Callable[[], dt.datetime] | None = None) -> None:
    """Raise BassError(promo_ended) unless live use is allowed right now."""
    if not live_allowed(clock):
        raise BassError(code="promo_ended")
