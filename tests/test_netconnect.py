"""B-1126-IPV6-HANG: black-holed IPv6 must never hold a connect up. No real network: getaddrinfo is mocked, the black hole is a stubbed attempt."""
import socket
import threading
import time

import pytest

from alto import netconnect as nc

V6 = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::%d" % i, 443, 0, 0)) for i in range(8)]
V4 = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))]


class Fake:
    def __init__(self, info):
        self.info, self.closed, self.t = info, False, None

    def close(self):
        self.closed = True

    def settimeout(self, t):
        self.t = t


@pytest.fixture
def net(monkeypatch):
    made = []

    def attempt(info, timeout, src):
        if info[0] == socket.AF_INET6:                     # black hole: nothing ever answers, it fails only at the timeout
            time.sleep(timeout if timeout else 30)
            raise socket.timeout("timed out")
        s = Fake(info)
        made.append(s)
        time.sleep(0.01)
        return s
    monkeypatch.setattr(nc, "_attempt", attempt)
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p, *a, **k: list(V6) + list(V4))
    return made


def test_eight_black_holed_ipv6_addresses_do_not_delay_the_ipv4_one(net):
    t = time.monotonic()
    s = nc.create_connection(("securetoken.googleapis.com", 443), timeout=30)
    took = time.monotonic() - t
    assert s.info[0] == socket.AF_INET and took < 3, took       # (the old way: 8 x 30 s)
    assert s.t == 30                                            # the caller's timeout is kept on the socket


def test_ipv4_is_interleaved_so_it_starts_after_one_stagger_not_after_all_the_ipv6(net):
    t = time.monotonic()
    nc.create_connection(("x.example", 443), timeout=30)
    assert time.monotonic() - t < 1.0


def test_a_failing_first_address_moves_on_at_once(monkeypatch):
    calls = []

    def attempt(info, timeout, src):
        calls.append(info[0])
        if info[0] == socket.AF_INET6:
            raise ConnectionRefusedError()
        return Fake(info)
    monkeypatch.setattr(nc, "_attempt", attempt)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: list(V6) + list(V4))
    t = time.monotonic()
    nc.create_connection(("x.example", 443), timeout=30)
    assert time.monotonic() - t < 0.2 and socket.AF_INET in calls


def test_all_addresses_dead_raises_within_the_callers_timeout(monkeypatch):
    monkeypatch.setattr(nc, "_attempt", lambda i, t, s: (time.sleep(t), (_ for _ in ()).throw(socket.timeout("timed out")))[1])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: list(V6) + list(V4))
    t = time.monotonic()
    with pytest.raises(OSError):
        nc.create_connection(("x.example", 443), timeout=1.0)
    assert time.monotonic() - t < 3


def test_the_loser_that_connects_late_is_closed(monkeypatch):
    made = []

    def attempt(info, timeout, src):
        time.sleep(0.6 if info[0] == socket.AF_INET6 else 0.0)    # v6 starts first, answers after v4 has won
        s = Fake(info)
        made.append(s)
        return s
    monkeypatch.setattr(nc, "_attempt", attempt)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: V6[:1] + V4)
    s = nc.create_connection(("x.example", 443), timeout=5)
    assert s.info[0] == socket.AF_INET
    time.sleep(1.0)
    late = [m for m in made if m is not s]
    assert late and all(m.closed for m in late) and not s.closed


def test_a_single_address_goes_straight_to_pythons_own_connect(monkeypatch):
    seen = []
    monkeypatch.setattr(nc, "_REAL", lambda *a, **k: seen.append(a) or "real")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: list(V4))
    assert nc.create_connection(("x.example", 443), timeout=4) == "real" and seen


def test_a_real_local_connection_works_and_install_is_idempotent():
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    def _acc():
        try:
            srv.accept()
        except OSError:
            pass
    threading.Thread(target=_acc, daemon=True).start()
    nc.install(); nc.install()
    import http.client
    assert socket.create_connection is nc.create_connection
    c = socket.create_connection(("127.0.0.1", srv.getsockname()[1]), timeout=3)
    c.close(); srv.close()
    assert http.client.HTTPConnection("x")._create_connection is nc.create_connection

