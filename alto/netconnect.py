"""Happy-eyeballs connect (RFC 8305) for every https call Alto makes.

Luke's network (2026-11-26): every IPv6 address of securetoken / identitytoolkit.googleapis.com black-holes while IPv4 connects in 10 ms.
Python's socket.create_connection tries the addresses one after another, each for the full timeout (30 s), so a cloud call hung for minutes
and Claude Desktop gave up ("Device did not respond within 140s"). curl was fine: it races them.

create_connection() here races them the same way: the addresses are interleaved by family (the first family getaddrinfo returned goes first),
each next attempt starts 250 ms after the one before (at once if that one has already failed), the first to connect wins and the rest are
closed. It changes only HOW the socket connects: TLS (urllib / http.client wrap the socket afterwards) and certifi are untouched.
install() puts it in place of socket.create_connection, which http.client (so urllib) calls; alto/__init__.py does that on import.
"""
from __future__ import annotations

import os
import queue
import socket
import threading
import time

STAGGER = 0.25                                  # seconds between attempts (RFC 8305 "connection attempt delay")
_REAL = socket.create_connection
_DEFAULT = socket._GLOBAL_DEFAULT_TIMEOUT       # type: ignore[attr-defined]


def _interleave(infos):
    fams = []
    for i in infos:
        if i[0] not in fams:
            fams.append(i[0])
    by = {f: [i for i in infos if i[0] == f] for f in fams}
    out = []
    while any(by.values()):
        for f in fams:
            if by[f]:
                out.append(by[f].pop(0))
    return out


def _attempt(info, timeout, source_address):
    """One connect to one address (tests replace this)."""
    af, st, proto, _cn, sa = info
    s = socket.socket(af, st, proto)
    try:
        if timeout is not _DEFAULT:
            s.settimeout(timeout)
        if source_address:
            s.bind(source_address)
        s.connect(sa)
        return s
    except BaseException:
        s.close()
        raise


def create_connection(address, timeout=_DEFAULT, source_address=None, *args, **kw):
    host, port = address
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    except OSError:
        return _REAL(address, timeout, source_address, *args, **kw)
    seen, uniq = set(), []
    for i in infos:
        if i[4] not in seen:
            seen.add(i[4])
            uniq.append(i)
    if len(uniq) < 2:
        return _REAL(address, timeout, source_address, *args, **kw)
    infos = _interleave(uniq)
    if timeout is not None and timeout is not _DEFAULT and timeout <= 0:
        raise ValueError("Non-blocking socket (timeout=0) is not supported")
    cap = None if timeout in (None, _DEFAULT) else float(timeout)
    deadline = None if cap is None else time.monotonic() + cap
    q: queue.Queue = queue.Queue()
    done = threading.Event()
    socks: list = []
    lock = threading.Lock()

    def run(info):
        try:
            s = _attempt(info, timeout, source_address)
        except BaseException as e:               # noqa: BLE001 - reported to the racer
            q.put((None, e))
            return
        with lock:
            late = done.is_set()
            if not late:
                socks.append(s)
        if late:
            s.close()
        else:
            q.put((s, None))

    started = pending = 0
    winner = None
    next_at = time.monotonic()
    errs: list = []
    try:
        while True:
            now = time.monotonic()
            if started < len(infos) and (pending == 0 or now >= next_at):
                threading.Thread(target=run, args=(infos[started],), daemon=True).start()
                started += 1
                pending += 1
                next_at = time.monotonic() + STAGGER
                continue
            if pending == 0 and started >= len(infos):
                break
            waits = []
            if started < len(infos):
                waits.append(next_at - now)
            if deadline is not None:
                waits.append(deadline - now)
                if deadline - now <= 0:
                    raise socket.timeout("timed out")
            try:
                s, e = q.get(timeout=max(0.001, min(waits)) if waits else None)
            except queue.Empty:
                continue
            pending -= 1
            if s is not None:
                winner = s
                if timeout is not _DEFAULT:
                    s.settimeout(timeout)
                return s
            errs.append(e)
    finally:
        with lock:
            done.set()
            extra = [x for x in socks if x is not winner]
        for x in extra:                          # (the winner is returned; any other that also connected is closed, and a late one closes itself)
            try:
                x.close()
            except OSError:
                pass
    if errs:
        raise errs[-1]
    raise OSError("getaddrinfo returns an empty list")


def install():
    """Idempotent. ALTO_NO_HAPPY_EYEBALLS=1 leaves Python's own create_connection in place."""
    if os.environ.get("ALTO_NO_HAPPY_EYEBALLS") or socket.create_connection is create_connection:
        return
    global _REAL
    _REAL = socket.create_connection
    socket.create_connection = create_connection
