#!/usr/bin/env python3
"""LOCAL-ONLY Bass server: lets Luke use the real Bass screens on his own Mac. MOCK unless every live gate is open.

    python3 tools/bass_local_server.py --purpose own  --site <built page.html> [--port 8765]                       # MOCK: no real model
    ALTO_STORE=local ALTO_LIVE_ANTHROPIC=1 python3 tools/bass_local_server.py --purpose own --live --site ...       # LIVE: refuses unless ALL gates are open

Any ALTO_STORE but local is refused (exit 2); a live server must be given ALTO_STORE=local; the mock server runs under a private temp
HOME (alto/bass/isolate.py).

It builds ONE alto.bass.beta_proxy.Proxy (the same engine, ledger and guards as the hosted beta; nothing relaxed) over a LOCAL file store and serves
Proxy.handle_http over http.server on 127.0.0.1 ONLY (hard-coded: there is no --host, the bound address is asserted). The same origin also serves the
page you built (--site) and the Bass bundle, so there is no CORS or file:// problem. For every .html it serves, it injects a tiny script before the
page's own: it points the page's Bass at this server and gives it a sign-in stub holding the per-run token from the URL fragment (#bassdev=<token>).
No build is changed: published and hosted pages never get this.

Gates for --live (refuses with exit 2, nothing constructed, zero requests, unless ALL hold):
    1. ~/.config/alto/bass/LIVE_GO exists (alto.bass.client.go_flag_path); deleting it later makes the NEXT request fall back to mock;
    2. ALTO_LIVE_ANTHROPIC=1 for this run;
    3. the Keychain item answers (alto.bass.studio_key.key_present). The key is read ONLY through studio_key, only when a live call needs it,
       and is never printed, logged, written or returned in a response.
Money (review finding M3): every hold is ALSO taken from the one local reserve file (alto/bass/local_reserve.py: $10 per credit period for
everything local, shared with tools/bass_live_check.py and across both purposes), and a LIVE server refuses any --store-root but the fixed
one, so a new directory is never a fresh grant. A mock server may use any root and books its mock money into <root>/reserve.mock.json.
Within that: two separate ledgers of 500 credits ($5) each, `--purpose own` (Luke's own test) and `--purpose runs` (the 24 Strategy runs), each with its
own store dir under ~/Documents/Alto-bass-local/<purpose>/. A purpose is granted ONCE (the credit period is confirmed only at first creation, never on
a restart); a hold that does not fit is refused before any call; per-action cap 100 credits ($1) for `own`, 300 for `runs` (--per-action-credits, max
300). The first upstream error, sign-in failure or low balance trips the kill switch: no retry. The Anthropic Console spend limit ($10) is the
OUTSIDE brake that works even if this code were wrong: Luke or IT sets it once; it cannot be tested here.
The log is metadata only: method, path, status, size, milliseconds. Never notes, model text, a token or a key.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hmac
import json
import os
import secrets as _secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.bass import client as C                                       # noqa: E402
from alto.bass import studio_key                                        # noqa: E402
from alto.bass.beta_config import BetaConfig                            # noqa: E402
from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key              # noqa: E402
from alto.bass.beta_proxy import AuthError, Proxy, SecretReader, TokenVerifier   # noqa: E402
from alto.bass.beta_store import FakeStore                              # noqa: E402
from alto.bass.local_reserve import LocalReserve, ReservedLedger        # noqa: E402
from alto.bass.tools import ToolBox                                     # noqa: E402
from alto.store.local import LocalStore                                 # noqa: E402

HOST = "127.0.0.1"                                                      # the ONLY address this server ever binds
PURPOSES = ("own", "runs")
CREDITS = 500                                                           # $5 per purpose
DEFAULT_PER_ACTION = {"own": 100, "runs": 300}
MAX_PER_ACTION = 300
EMAIL = "luke-local@alto.invalid"                                       # the one local identity; the only email on the allowlist
BANNER = "MOCK: no real model"
LIVE_BANNER = "LIVE: real model, real credits"
DEFAULT_ROOT = Path.home() / "Library" / "Application Support" / "Alto-bass-local"      # NOT under Desktop/Documents: those sync to iCloud and the other Mac
SYNCED = ("Desktop", "Documents", "Library/Mobile Documents")


class Refused(SystemExit):
    def __init__(self, why: str):
        super().__init__(f"bass_local_server: {why}")
        self.code = 2


def gates(env=None) -> dict:
    """The three live gates, each True/False. Reads no key (key_present does not fetch the value). The Keychain is asked ONLY when the other two
    gates are open: with either closed there is no lookup at all (curated public head, 12 Nov), and "keychain" is False."""
    env = os.environ if env is None else env
    go, on = C.go_flag_path().is_file(), env.get("ALTO_LIVE_ANTHROPIC") == "1"
    return {"live_go_file": go, "env": on, "keychain": bool(go and on and studio_key.key_present())}


class LocalVerifier(TokenVerifier):
    """Accepts ONE per-run random token (constant-time compare) and maps it to one fixed local uid. Anything else is a 401."""

    def __init__(self, token: str, purpose: str):
        self._token, self.uid = token, f"local-{purpose}"

    def verify(self, id_token: str) -> dict:
        if not isinstance(id_token, str) or not hmac.compare_digest(id_token.encode("utf-8"), self._token.encode("utf-8")):
            raise AuthError
        return {"uid": self.uid, "email": EMAIL, "email_verified": True}


class LocalSecretReader(SecretReader):
    """The Bass key: from the Keychain through studio_key only, and only when a live call asks. Never anywhere else."""

    def read(self, name: str) -> str:
        return studio_key.get_key().reveal()


class PersistentStore(FakeStore):
    """The guard store on disk (one JSON file, written atomically after every write). bass_beta/live_go is VIRTUAL: it answers from the gates on every
    read, so removing LIVE_GO falls back to mock at the next request and nothing is ever stored as 'on'."""

    def __init__(self, path: Path, live_wanted: bool):
        super().__init__(auto_terms=True)                               # this is Luke's own Mac: the Beta Terms box is not asked
        self.path, self.live_wanted = Path(path), live_wanted
        self._plock = threading.Lock()
        if self.path.is_file():
            self.docs = json.loads(self.path.read_text("utf-8"))
        self.fresh = not self.path.is_file()

    def get(self, key: str):
        if key == LIVE_GO_KEY:
            return {"on": bool(self.live_wanted and C.go_flag_path().is_file())}
        return super().get(key)

    def _flush(self) -> None:
        with self._plock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.docs, sort_keys=True), "utf-8")
            os.replace(tmp, self.path)

    def put(self, key: str, doc: dict) -> None:
        super().put(key, doc)
        self._flush()

    def run_transaction(self, fn, retries: int = 5):
        out = super().run_transaction(fn, retries)
        self._flush()
        return out


def check_root(root: Path) -> Path:
    """The ledger and the built pages must never sit in an iCloud-synced folder (a stale copy on the other Mac could overwrite the ledger)."""
    r = Path(root).expanduser().resolve()
    home = Path.home().resolve()
    for name in SYNCED:
        if r == home / name or (home / name) in r.parents:
            raise Refused(f"--store-root may not be under ~/{name} (it syncs to iCloud); use ~/Library/Application Support/Alto-bass-local")
    return r


def make_config(purpose: str, port: int, per_action: int | None = None) -> BetaConfig:
    pa = DEFAULT_PER_ACTION[purpose] if per_action is None else int(per_action)
    if not 1 <= pa <= MAX_PER_ACTION:
        raise Refused(f"--per-action-credits must be 1..{MAX_PER_ACTION}")
    return BetaConfig(testers=1, allowlist=frozenset({EMAIL}), pool_credits=CREDITS, server_ceiling_credits=CREDITS, tester_daily_credits=CREDITS,
                      global_daily_credits=CREDITS, per_action_cap_credits=pa, allowed_origins=(f"http://{HOST}:{port}",),
                      function_timeout_s=3600, action_wall_s=1800)       # no platform timeout here; an action still ends by itself


def build_proxy(purpose: str, root: Path, port: int, token: str, live: bool, per_action: int | None = None, clock=None, mock=None,
                reserve: LocalReserve | None = None):
    """-> Proxy over this purpose's own store. The credit period is confirmed ONLY when the store is first created: a restart never re-grants,
    and a later credit period stays unconfirmed (Bass closed) until a human decides."""
    if purpose not in PURPOSES:
        raise Refused("--purpose must be own or runs")
    clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
    cfg = make_config(purpose, port, per_action)
    if live:
        if check_root(root) != DEFAULT_ROOT.expanduser().resolve():
            raise Refused(f"a live server uses the one fixed store root ({DEFAULT_ROOT}); another root would be a fresh grant")
        reserve = LocalReserve(clock=clock, cfg=cfg)                    # the fixed file, whatever was passed in
        reserve.require_fixed()
    elif reserve is None:
        reserve = LocalReserve(check_root(root) / "reserve.mock.json", clock=clock, cfg=cfg)      # mock money, never the real reserve
    base = check_root(root) / purpose
    base.mkdir(parents=True, exist_ok=True)
    store = PersistentStore(base / "guard.json", live)
    if store.fresh:
        store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True, "local_first_grant": clock().isoformat()})
    proxy = Proxy(cfg, store, LocalVerifier(token, purpose), LocalSecretReader(), ToolBox(LocalStore(base / "alto")), clock=clock, mock=mock)
    proxy.reserve = reserve
    # every hold the engine takes also comes out of the shared local reserve, and every real cost is booked into it
    proxy.service.actions.engine.ledger = ReservedLedger(proxy.ledger, reserve, f"local-server:{purpose}")
    return proxy


def build_site(root: Path) -> Path:
    """Build the local homepage WITH the Bass buttons (ALTO_BASS_UI=1, set only for this one build call) into <root>/site/index.html. The page build
    itself is untouched: with the variable unset, build_home is byte-identical to today (a test pins it)."""
    from alto.build import pages
    old = os.environ.get("ALTO_BASS_UI")
    os.environ["ALTO_BASS_UI"] = "1"
    try:
        html = pages.build_home([])
    finally:
        if old is None:
            os.environ.pop("ALTO_BASS_UI", None)
        else:
            os.environ["ALTO_BASS_UI"] = old
    out = check_root(root) / "site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, "utf-8")
    return out


def inject(html: str, port: int, token_in_fragment: bool, mock: bool) -> str:
    """Before the page's own scripts: point Bass at this server, give it a sign-in stub holding the token from the URL fragment, show the banner."""
    base = f"http://{HOST}:{port}/bass"
    js = ("(function(){var m=location.hash.match(/bassdev=([A-Za-z0-9_-]+)/),t=m&&m[1];window._ALTO_BASS_BASE=" + json.dumps(base) + ";"
          "if(t&&!window.AltoCloud){window.AltoCloud={user:{uid:'bass-local',getIdToken:function(){return Promise.resolve(t)}}};}"
          "var b=document.createElement('div');b.setAttribute('style','position:fixed;top:0;left:0;right:0;z-index:99999;color:#fff;font:600 12px system-ui;text-align:center;padding:3px');"
          "function st(j){var l=j&&j.live===true;b.textContent=l?" + json.dumps(LIVE_BANNER) + ":" + json.dumps(BANNER) + ";b.style.background=l?'#1b6e3c':'#b3261e'}st(null);"
          "function poll(){fetch('/bass-status').then(function(r){return r.json()}).then(st).catch(function(){st(null)})}"
          "addEventListener('DOMContentLoaded',function(){document.body.appendChild(b);poll();setInterval(poll,3000)});})();")
    tag = f'<script id="bass-local-dev">{js}</script>'
    i = html.lower().find("<head>")
    return html[:i + 6] + tag + html[i + 6:] if i >= 0 else tag + html


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, proxy: Proxy, site: Path | None, live: bool):
        super().__init__((HOST, int(port)), _Handler)
        if self.server_address[0] != HOST:                              # belt and braces: never anything but loopback
            self.server_close()
            raise Refused("bound to a non-loopback address; refusing")
        self.proxy, self.site, self.live = proxy, site, live
        self.lock = threading.Lock()                                    # one request at a time through the guards (single user: no cost, no races)
        self.port = self.server_address[1]
        self.log: list = []


class _Handler(BaseHTTPRequestHandler):
    server_version = "AltoBassLocal"

    def log_message(self, *a):                                          # metadata only, our own line below
        pass

    def _meta(self, status: int, size: int, t0: float) -> None:
        line = {"m": self.command, "path": self.path.split("?")[0][:60], "status": status, "bytes": size, "ms": int((time.time() - t0) * 1000)}
        self.server.log.append(line)
        print(json.dumps(line), flush=True)

    def _host_ok(self) -> bool:                                         # DNS rebinding: only our own name:port
        return self.headers.get("Host", "") in (f"{HOST}:{self.server.port}", f"localhost:{self.server.port}")

    def _send(self, status: int, headers: dict, body: bytes, t0: float) -> None:
        self.send_response(status)
        for k, v in {**headers, "Content-Length": str(len(body)), "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
        self._meta(status, len(body), t0)

    def do_GET(self):
        t0 = time.time()
        if not self._host_ok():
            return self._send(403, {"Content-Type": "text/plain"}, b"forbidden", t0)
        from alto.build import bass_ui
        p = self.path.split("?")[0].split("#")[0]
        if p == "/bass-status":                                         # the banner follows the live gate on every poll, not the start-up state
            return self._send(200, {"Content-Type": "application/json"}, json.dumps({"live": bool(self.server.proxy.live_go())}).encode("utf-8"), t0)
        if p == bass_ui.PATH:
            return self._send(200, {"Content-Type": "application/javascript; charset=utf-8"}, bass_ui.ASSET.encode("utf-8"), t0)
        site = self.server.site
        if site is not None and p in ("/", "/index.html"):
            html = site.read_text("utf-8")
            return self._send(200, {"Content-Type": "text/html; charset=utf-8"}, inject(html, self.server.port, True, not self.server.live).encode("utf-8"), t0)
        self._send(404, {"Content-Type": "text/plain"}, b"not found", t0)

    def do_POST(self):
        t0 = time.time()
        origin = self.headers.get("Origin")
        if not self._host_ok() or self.path.split("?")[0] != "/bass" or (origin and origin != f"http://{HOST}:{self.server.port}"):
            return self._send(403, {"Content-Type": "text/plain"}, b"forbidden", t0)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 <= n <= self.server.proxy.cfg.max_request_bytes:
                raise ValueError
        except ValueError:                                              # garbage, negative or oversize: never read the socket on a guess
            return self._send(400, {"Content-Type": "text/plain"}, b"bad request", t0)
        body = self.rfile.read(n)
        with self.server.lock:
            st, hd, out = self.server.proxy.handle_http("POST", dict(self.headers), body)
        self._send(st, hd, out, t0)

    def do_OPTIONS(self):                                               # same origin: nothing to negotiate, and the proxy is never asked
        t0 = time.time()
        self._send(204 if self._host_ok() else 403, {"Content-Type": "text/plain"}, b"", t0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--purpose", required=True, choices=PURPOSES)
    ap.add_argument("--site", type=Path, help="a built page (.html) to serve at / (built with ALTO_BASS_UI=1); default: <store-root>/site/index.html")
    ap.add_argument("--build-site", action="store_true", help="first build the local homepage with the Bass buttons into <store-root>/site/index.html")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--live", action="store_true", help="live Anthropic calls: refuses unless ALL three gates are open; without it the server is MOCK only")
    ap.add_argument("--per-action-credits", type=int, default=None)
    ap.add_argument("--store-root", type=Path, default=DEFAULT_ROOT)
    a = ap.parse_args(argv)
    g = gates()
    if a.live and not all(g.values()):
        raise Refused("refusing to start live: missing " + ", ".join(k for k, v in g.items() if not v))
    site = a.site or (build_site(a.store_root) if a.build_site else a.store_root / "site" / "index.html")
    if not site.is_file():
        raise Refused(f"no page to serve at {site}: run once with --build-site (or pass --site)")
    token = _secrets.token_urlsafe(24)
    proxy = build_proxy(a.purpose, a.store_root, a.port, token, a.live, a.per_action_credits)
    srv = Server(a.port, proxy, site, a.live)
    print(("LIVE" if a.live else BANNER) + f" | purpose={a.purpose} | {CREDITS} credits | per action {proxy.cfg.per_action_cap_credits}", flush=True)
    print(f"Open: http://{HOST}:{srv.port}/#bassdev={token}   (shown once; Ctrl-C stops the server)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    # never the default store; the mock server runs under a private temp HOME / XDG_CONFIG_HOME (its store root is unchanged); a live
    # server needs ALTO_STORE=local given explicitly (alto/bass/isolate.py)
    from alto.bass import isolate
    isolate.start("bass_local_server", mock="--live" not in sys.argv[1:])
    sys.exit(main())
