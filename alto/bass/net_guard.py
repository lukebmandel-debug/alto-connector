"""Tests must not reach api.anthropic.com.

Layer 1: install() makes any DNS lookup, connect or create_connection to an
Anthropic host raise, unless ALTO_LIVE_ANTHROPIC=1 (Luke's go-ahead, set by hand).
Layer 2: ALTO_NO_NETWORK=1 also blocks every non-loopback host.
Layer 3: studio_key.get_key() refuses without the same gate.

Use: call net_guard.install() from tests/conftest.py (an autouse fixture, see
INSTALL.md) and from the mock layer's constructor.
"""
import datetime
import os
import pwd
import socket
import sys

BLOCKED_SUFFIXES = ("anthropic.com", "claude.ai", "claude.com")
_LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}
_installed = False


class RealNetworkBlocked(RuntimeError):
    pass


# -- the block log (incident 11 Nov): one line per block, so a blocked attempt is never known only from a transcript ------------------
# Fixed file: ~/Library/Logs/Alto/net_guard.log, where ~ is the REAL account's home from the password database, not $HOME. The Bass
# tools run under a private temp HOME (alto/bass/isolate.py); a log that followed $HOME would vanish with it. ~/Library/Logs is macOS's
# per-user log place (Console.app shows it), outside iCloud-synced Desktop/Documents. ALTO_NET_GUARD_LOG overrides it, for tests only
# (tests/conftest.py points it at a temp file so a test run never writes the real log).
# A line: <local time ISO>\tblocked\thost=<host>\tpid=<pid>\targv0=<argv[0]>\trule=<anthropic|no_network|google_url>. Nothing else: no
# URL path or query, no request body, no header, no environment. Writing it can never stop the block: any OSError is swallowed.
LOG_ENV = "ALTO_NET_GUARD_LOG"


def log_path() -> str:
    override = os.environ.get(LOG_ENV, "").strip()
    if override:
        return override
    try:
        home = pwd.getpwuid(os.getuid()).pw_dir
    except (KeyError, OSError):
        home = os.path.expanduser("~")
    return os.path.join(home, "Library", "Logs", "Alto", "net_guard.log")


def _clean(v, limit=200) -> str:
    return "".join(c if c.isprintable() and c not in "\t\n\r" else "?" for c in str(v))[:limit]


def _log_block(host, rule):
    try:
        argv0 = sys.argv[0] if sys.argv and sys.argv[0] else "?"
        line = "%s\tblocked\thost=%s\tpid=%d\targv0=%s\trule=%s\n" % (
            datetime.datetime.now().astimezone().isoformat(timespec="seconds"), _clean(host or "?"), os.getpid(), _clean(argv0), rule)
        p = log_path()
        os.makedirs(os.path.dirname(p) or ".", mode=0o700, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8", "replace"))
        finally:
            os.close(fd)
    except Exception:  # noqa: BLE001 -- the log must never turn a block into anything else
        pass


def _host(addr):
    h = addr[0] if isinstance(addr, tuple) else addr
    if isinstance(h, bytes):
        h = h.decode("ascii", "ignore")
    return str(h or "").lower().rstrip(".")


def _check(host):
    if os.environ.get("ALTO_LIVE_ANTHROPIC") == "1":
        return
    if any(host == s or host.endswith("." + s) for s in BLOCKED_SUFFIXES):
        _log_block(host, "anthropic")
        raise RealNetworkBlocked("blocked: test tried to reach %s" % host)
    if os.environ.get("ALTO_NO_NETWORK") == "1" and host not in _LOOPBACK and not host.startswith("127."):
        _log_block(host, "no_network")
        raise RealNetworkBlocked("blocked: ALTO_NO_NETWORK=1 and test tried to reach %s" % host)


def install():
    global _installed
    if _installed:
        return
    _installed = True
    real_gai, real_connect, real_cc = socket.getaddrinfo, socket.socket.connect, socket.create_connection

    def gai(host, *a, **k):
        _check(_host(host))
        return real_gai(host, *a, **k)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _check(_host(address))
        return real_connect(self, address)

    def cc(address, *a, **k):
        _check(_host(address))
        return real_cc(address, *a, **k)

    socket.getaddrinfo, socket.socket.connect, socket.create_connection = gai, connect, cc


# -- Google Drive egress (alto/bass/drive.py): the ONLY non-Anthropic place Bass code may call, and only these two hosts, over https, with no
# credentials in the address and no redirect followed (the transport refuses a 3xx rather than follow it).
GOOGLE_HOSTS = ("www.googleapis.com", "oauth2.googleapis.com")


def check_google_url(url: str) -> str:
    """-> the url, or raises RealNetworkBlocked: https only, one of GOOGLE_HOSTS exactly, default port, no userinfo, no fragment."""
    from urllib.parse import urlsplit
    try:
        u = urlsplit(url)
        host, port = (u.hostname or "").lower().rstrip("."), u.port
    except ValueError:
        _log_block("?", "google_url")
        raise RealNetworkBlocked("blocked: unreadable address")
    if u.scheme != "https" or host not in GOOGLE_HOSTS or port not in (None, 443) or u.username or u.password or u.fragment:
        _log_block(host, "google_url")              # the host only: never the path, query or userinfo of the refused address
        raise RealNetworkBlocked("blocked: not a Google Drive address")
    return url
