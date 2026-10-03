"""Every Alto account this computer can reach, and which one a call is about.

An Alto account is one Firebase project's user: a site (luke-alto.web.app), the
project behind it, and the Google account that signed in to it. A person can
have several — a school address and a personal one, each with its own site —
and a Claude chat that starts on its own (not from a timeline's "Edit timeline"
button) has to be able to find the right one and reach into it.

Where an account comes from, in the order they are listed:

  settings / managed  the one in the environment (ALTO_FIREBASE_*) or the site
                      set_up_site made. This is the DEFAULT account: what every
                      tool uses when it is not told otherwise, exactly as before
                      accounts existed.
  saved               accounts.json, written by connect_account: any existing
                      Alto site, found from its address alone.
  session             a sign-in kept in session-<project>.json (by an earlier
                      sign_in, or by another Alto install on this computer)
                      that nothing else names. Its site is learned from the
                      account's own published timelines the first time it is
                      used.

A tool call picks an account with its `account` argument (a site name, address,
project or email). There is deliberately no "current account" kept between
calls: one connector process can serve several chats, and a choice made in one
must never redirect another's writes. The
rest of Alto reads its Firebase settings from the environment and from one
store per call, so `scope()` points both at the chosen account for the length
of one call and puts them back after — nothing else needs to know accounts
exist. Tool calls are serialised by the stdio transport; the lock is for the
one background thread that also reads that environment (set_up_site's).

Stdlib only.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path

from . import CloudConfigError, load_config
from . import site as site_rec
from .session import CloudError, Session, SignInRequired, config_dir

_ALLOWED = ("apiKey", "authDomain", "projectId", "storageBucket",
            "messagingSenderId", "appId", "measurementId")
# A Firebase Hosting site id / GCP project id (the same rule publish_static
# enforces before either reaches a subprocess argument).
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")
_HOSTS = (".web.app", ".firebaseapp.com")
_ENV = ("ALTO_STORE", "ALTO_FIREBASE_SITE", "ALTO_FIREBASE_PROJECT",
        "ALTO_FIREBASE_CONFIG")

_ACTIVE: contextvars.ContextVar = contextvars.ContextVar("alto_account", default=None)
_LOCK = threading.RLock()
_SESSIONS: dict[str, Session] = {}


# ── where an account's site and web config come from ────────────────────────

def _fetch_config(host: str) -> dict:
    """The public web config of a Firebase Hosting site. Firebase serves it at
    /__/firebase/init.json on every site of a project that has a web app, so an
    existing Alto site is reachable from its address alone — nobody pastes
    anything."""
    from .session import _http
    try:
        status, js = _http("GET", f"https://{host}.web.app/__/firebase/init.json",
                           None, {"User-Agent": "Alto"}, 20)
    except (OSError, ValueError) as e:
        raise CloudError(f"could not reach https://{host}.web.app ({e})") from e
    if status != 200 or not isinstance(js, dict) \
            or not js.get("apiKey") or not js.get("projectId"):
        raise CloudError(f"https://{host}.web.app is not a Firebase site Alto "
                         "can read (it publishes no web config)")
    return {k: str(js[k]) for k in _ALLOWED if js.get(k)}


def _probe(url: str) -> int:
    from .provision import _http_get
    return _http_get(url)


fetch_config = _fetch_config       # swapped out by tests
probe = _probe
SIGN_IN_WAIT = 45                  # seconds a connect_account call waits for the click


def parse_site(ref: str) -> str:
    """luke-alto from "luke-alto", "luke-alto.web.app" or any address on it;
    "" for anything that is not a site name (an email, a title)."""
    s = re.sub(r"^https?://", "", (ref or "").strip().lower())
    s = re.split(r"[/?#]", s, 1)[0]
    for suf in _HOSTS:
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s if _NAME.match(s) else ""


# ── the stored pieces ───────────────────────────────────────────────────────

def accounts_path() -> Path:
    return config_dir() / "accounts.json"


def _load_saved() -> list[dict]:
    try:
        d = json.loads(accounts_path().read_text(encoding="utf-8"))
        rows = d.get("accounts") if isinstance(d, dict) else None
        return [r for r in rows or [] if isinstance(r, dict) and r.get("project")]
    except (OSError, ValueError):
        return []


def _save_saved(rows: list[dict]) -> None:
    p = accounts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"accounts": rows}, f, indent=2)
    os.replace(tmp, p)


def _peek(project: str) -> dict:
    """Who a project's stored sign-in is, without a network call."""
    try:
        d = json.loads((config_dir() / f"session-{project}.json")
                       .read_text(encoding="utf-8"))
        if d.get("refresh_token") and d.get("uid"):
            return {"email": d.get("email", ""), "uid": d["uid"], "signed_in": True}
    except (OSError, ValueError, AttributeError):
        pass
    return {"email": "", "uid": "", "signed_in": False}


def _acct(site: str, project: str, config: dict | None, source: str) -> dict:
    a = {"id": site or project, "site": site or "", "project": project,
         "config": dict(config or {}), "source": source}
    a.update(_peek(project))
    return a


def default() -> dict | None:
    """The account every tool uses when not told otherwise: the Firebase
    settings in the environment (an author's own, the extension's advanced
    settings, or what set_up_site filled in), else a finished managed site."""
    site = os.environ.get("ALTO_FIREBASE_SITE", "").strip()
    project = os.environ.get("ALTO_FIREBASE_PROJECT", "").strip()
    if site and project and not site.startswith("${") and not project.startswith("${"):
        try:
            cfg = load_config()
        except CloudConfigError:
            cfg = {}
        managed = os.environ.get(site_rec.MANAGED_FLAG) == "1"
        return _acct(site, project, cfg if cfg.get("apiKey") else {},
                     "managed" if managed else "settings")
    d = site_rec.load()
    if site_rec.ready(d):
        return _acct(d["site"], d["project"], d.get("config"), "managed")
    return None


def _discovered(skip_projects: set[str]) -> list[dict]:
    out = []
    try:
        files = sorted(config_dir().glob("session-*.json"))
    except OSError:
        return out
    for f in files:
        project = f.stem[len("session-"):]
        if project in skip_projects or not _NAME.match(project):
            continue
        a = _acct("", project, None, "session")
        if a["signed_in"]:
            out.append(a)
    return out


def known() -> list[dict]:
    """Every account this computer can reach, default first."""
    out: list[dict] = []
    seen_ids: set[str] = set()
    d = default()
    if d:
        out.append(d)
        seen_ids.add(d["id"])
    for r in _load_saved():
        a = _acct(r.get("site", ""), r["project"], r.get("config"), "saved")
        a["id"] = r.get("id") or a["id"]
        if a["id"] in seen_ids:
            continue
        out.append(a)
        seen_ids.add(a["id"])
    out += _discovered({a["project"] for a in out})
    return out


def is_default(a: dict | None) -> bool:
    d = default()
    return bool(a and d and a["id"] == d["id"])


def summary(a: dict) -> dict:
    """What the model is shown about an account. No config, no token."""
    out = {"account": a["id"], "email": a.get("email", ""),
           "site_url": f"https://{a['site']}.web.app" if a.get("site") else "",
           "project": a["project"], "signed_in": bool(a.get("signed_in")),
           "default": is_default(a)}
    return out


# ── choosing one ────────────────────────────────────────────────────────────

def _no_match(ref: str) -> dict:
    return {"error": "unknown_account",
            "message": (f"No Alto account on this computer matches {ref!r}. "
                        "list_accounts shows the ones Alto knows. If the user "
                        "has another Alto site, connect_account(site) adds it "
                        "from its address (e.g. luke-alto.web.app) — ask them "
                        "for the address, nothing else."),
            "accounts": [summary(a) for a in known()]}


def resolve(ref: str) -> tuple[dict | None, dict | None]:
    """(account, None) for a site name, address, project or email; else
    (None, error)."""
    r = (ref or "").strip().lower()
    if not r:
        return None, _no_match(ref)
    site = parse_site(ref)
    rows = known()
    hit = [a for a in rows
           if r in (a["id"].lower(), a["site"].lower(), a["project"].lower(),
                    a.get("email", "").lower())
           or (site and site in (a["site"], a["project"]))]
    if not hit and "@" not in r:
        hit = [a for a in rows if r in a["id"].lower() or r in a["project"].lower()]
    if len(hit) == 1:
        return hit[0], None
    if not hit:
        return None, _no_match(ref)
    return None, {"error": "ambiguous_account",
                  "message": (f"{ref!r} matches more than one account; name "
                              "the site (e.g. luke-alto) instead."),
                  "accounts": [summary(a) for a in hit]}


def pick(ref: str) -> tuple[dict | None, dict | None]:
    """The account a tool call is about: its own `account`. None means the
    default account, handled with no scoping at all."""
    r = (ref or "").strip()
    if not r or r.lower() in ("default", "all"):
        return None, None
    a, err = resolve(r)
    if err:
        return None, err
    return (None if is_default(a) else a), None


# ── sessions, stores, scoping ───────────────────────────────────────────────

def ensure_config(a: dict) -> dict:
    """The account's web config, fetched from its site when only a sign-in is
    known (a session-discovered account)."""
    if (a.get("config") or {}).get("apiKey"):
        return a["config"]
    host = a.get("site") or a["project"]
    cfg = fetch_config(host)
    if cfg.get("projectId") != a["project"]:
        raise CloudError(f"https://{host}.web.app belongs to project "
                         f"{cfg.get('projectId')!r}, not {a['project']!r}")
    a["config"] = cfg
    if a.get("source") != "settings":
        register(a)
    return cfg


def session_for(a: dict) -> Session:
    cfg = ensure_config(a)
    with _LOCK:
        s = _SESSIONS.get(a["project"])
        if s is None or s.config.get("apiKey") != cfg.get("apiKey"):
            s = Session(cfg)
            _SESSIONS[a["project"]] = s
        return s


def current() -> dict | None:
    return _ACTIVE.get()


def scoped_session() -> Session | None:
    a = _ACTIVE.get()
    return session_for(a) if a else None


def _guard_background() -> None:
    """set_up_site's thread reads the same environment; do not swap it under
    a deploy that is running."""
    from . import provision
    p = provision._PROVISIONER
    t = getattr(p, "_thread", None)
    if t is not None and t.is_alive():
        raise CloudError("Alto is still setting up the user's own site in the "
                         "background; try this again in a minute.")


@contextlib.contextmanager
def scope(a: dict | None):
    """Run one tool call as account `a`. None is the default account: nothing
    changes."""
    if a is None:
        yield None
        return
    _guard_background()
    with _LOCK:
        cfg = ensure_config(a)
        saved = {k: os.environ.get(k) for k in _ENV}
        tok = _ACTIVE.set(a)
        try:
            os.environ["ALTO_STORE"] = "cloud"
            # No site means no deploy target (publish writes the page only),
            # never a guess: the project's default site may be someone else's.
            os.environ["ALTO_FIREBASE_SITE"] = a.get("site") or ""
            os.environ["ALTO_FIREBASE_PROJECT"] = a["project"]
            os.environ["ALTO_FIREBASE_CONFIG"] = json.dumps(cfg)
            yield a
        finally:
            _ACTIVE.reset(tok)
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


# ── remembering ─────────────────────────────────────────────────────────────

def register(a: dict, replaces: str = "") -> None:
    """Keep an account in accounts.json (no tokens; the sign-in is its own
    file). The default account is never copied here. `replaces` is an id this
    account was known by before (its project name, before its site was
    learned), so it is not listed twice."""
    if is_default(a):
        return
    rows = [r for r in _load_saved()
            if (r.get("id") or r.get("site") or r["project"]) not in (a["id"], replaces)]
    rows.append({"id": a["id"], "site": a.get("site", ""), "project": a["project"],
                 "config": a.get("config") or {}, "email": a.get("email", ""),
                 "uid": a.get("uid", ""), "added": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    _save_saved(rows)


def infer_site(a: dict, timelines: list[dict]) -> str:
    """The site an account publishes to, read off its own published timelines'
    addresses. Used when a sign-in is all that is known; never guessed from the
    project name. The account takes the site's name as its id; its project name
    still finds it (resolve), so a name the model already used keeps working."""
    hosts = Counter()
    for t in timelines:
        m = re.match(r"https://([a-z0-9-]+)\.web\.app/", (t.get("urls") or {}).get("view_url", ""))
        if m and _NAME.match(m.group(1)):
            hosts[m.group(1)] += 1
    if not hosts:
        return ""
    site = hosts.most_common(1)[0][0]
    if not a.get("site"):
        old = a["id"]
        a["site"], a["id"] = site, site     # the name the user knows; the old one still resolves
        if a.get("source") != "settings":
            register(a, replaces=old)
    return site


def _reset_for_tests() -> None:
    _SESSIONS.clear()


# ── connect_account ─────────────────────────────────────────────────────────

def connect(site_ref: str, email: str = "") -> dict:
    """Add an existing Alto site: fetch its config from its address, then sign
    in on its /connect/ page (the user clicks Continue with Google, with
    whichever Google account that site belongs to)."""
    site = parse_site(site_ref)
    if not site:
        return {"error": "bad_site",
                "message": (f"{site_ref!r} is not a site address. Give the "
                            "Alto site's address, e.g. luke-alto.web.app.")}
    base = f"https://{site}.web.app"
    try:
        cfg = fetch_config(site)
    except CloudError as e:
        return {"error": "site_not_found", "message": str(e),
                "next": ("Ask the user to check the address of their Alto "
                         "site (the one they open to see their timelines).")}
    if probe(base + "/connect/") != 200:
        return {"error": "not_an_alto_site",
                "message": (f"{base} is a Firebase site but has no Alto "
                            "sign-in page, so it is not an Alto site."),
                "next": "Ask the user for the address of their Alto site."}
    a = _acct(site, cfg["projectId"], cfg, "saved")
    s = session_for(a)
    if s.signed_in and email and s.email.lower() != email.strip().lower():
        s.forget()                  # a different Google account was asked for
    if s.signed_in:
        try:
            s.id_token(force=True)
            return _connected(a, s)
        except SignInRequired:
            s.forget()
    p = s.start(base)
    if s.wait(SIGN_IN_WAIT):
        return _connected(a, s)
    return {"status": "waiting", "url": p["url"], "site_url": base,
            "message": ("A sign-in page for the user's Alto site is open in "
                        "their browser. They click Continue with Google there"
                        + (f", as {email}" if email else "") + "."),
            "next": ("Tell the user to click Continue with Google on the page "
                     "that opened (give `url` if nothing did), then call "
                     "connect_account again with the same site. Never ask "
                     "them to copy or paste anything."
                     + (f" Last error: {p['error']}" if p.get("error") else ""))}


def _connected(a: dict, s: Session) -> dict:
    a.update(email=s.email, uid=s.uid, signed_in=True)
    register(a)
    return {"status": "connected", **summary(a),
            "next": ("Pass account=%r to the other Alto tools to work in this "
                     "account." % a["id"])}
