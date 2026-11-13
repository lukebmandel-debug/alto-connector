"""Per-account and per-IP limits for the beta proxy.

* client_ip: behind Google's front end the LAST entry of X-Forwarded-For is the one Google appended (the left end is
  whatever the client sent, so it is spoofable and never used). IPv6 is bucketed by /64, because one home gets a whole /64.
* SlidingLimiter: N hits per window, on an injectable clock (the tests use a fake one).
* InFlight: at most 1 build and 2 chat calls running per account; extra calls get "busy" with no API call.
These stop casual abuse, not a botnet: the money rules (allowlist, allowance, daily ceiling) do the real work.
In-flight counts live in the process (one function instance); the allowance hold bounds what several instances can spend.
"""
from __future__ import annotations

import collections
import ipaddress
import threading
from typing import Callable


def client_ip(xff: str | None, remote: str | None = None, hops: int = 1) -> str:
    """The caller's address. `hops` = how many X-Forwarded-For entries OUR infrastructure appended: 1 (default) on the direct
    run.app / cloudfunctions URL, where the last entry is the one Google added; 2 behind one more trusted proxy (a Hosting
    rewrite, a load balancer), and so on. The entries left of those are client-supplied and never trusted."""
    parts = [p.strip() for p in str(xff or "").split(",") if p.strip()]
    raw = (parts[-max(1, hops)] if len(parts) >= max(1, hops) else parts[0]) if parts else (remote or "")
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return "invalid"
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


class SlidingLimiter:
    SWEEP_ABOVE = 512                       # keys; past this, idle ones are dropped so a flood of addresses cannot grow memory forever

    def __init__(self, clock: Callable[[], float]):
        self.clock = clock
        self._hits: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def _sweep(self, now: float, window_s: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] >= max(window_s, 3600)]:
            del self._hits[k]

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = self.clock()
        with self._lock:
            if len(self._hits) > self.SWEEP_ABOVE:
                self._sweep(now, window_s)
            q = self._hits.setdefault(key, collections.deque())
            while q and now - q[0] >= window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def count(self, key: str, window_s: float) -> int:
        now = self.clock()
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                return 0
            n = sum(1 for t in q if now - t < window_s)
            if n == 0:
                del self._hits[key]            # nothing left in the window: do not keep the key
            return n

    def size(self) -> int:
        return len(self._hits)


class InFlight:
    def __init__(self, build: int = 1, chat: int = 2):
        self.limits = {"build": build, "chat": chat}
        self._n: dict[tuple, int] = {}
        self._lock = threading.Lock()

    def acquire(self, uid: str, kind: str) -> bool:
        with self._lock:
            k = (uid, kind)
            if self._n.get(k, 0) >= self.limits[kind]:
                return False
            self._n[k] = self._n.get(k, 0) + 1
            return True

    def release(self, uid: str, kind: str) -> None:
        with self._lock:
            k = (uid, kind)
            self._n[k] = max(0, self._n.get(k, 0) - 1)

    def running(self, uid: str, kind: str) -> int:
        return self._n.get((uid, kind), 0)
