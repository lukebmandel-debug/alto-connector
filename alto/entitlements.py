"""Which formats an account may make: the ONE check every way of making a format goes through.

A format is one of the ids in FORMATS (the same ids the home page's file badges use). `allowed(uid, fmt)` answers
{"ok": True} or {"ok": False, "needs_plan": <level>, "message": ...} for the format being MADE (the target): an
outline turned into a Memory palace is checked on "palace", whatever the file was before.

In the beta every format is open to every account: FORMAT_MIN_PLAN says "free" for all of them and PAYWALL is off, so
`allowed` always says yes without looking anything up. When prices and levels are set, the paywall build changes the
table (which format sits at which level is a business decision, not code's) and turns the one switch on (ALTO_PAYWALL=1
on the server) and supplies the account's plan with `set_plan_lookup`; no route has to change. The same call guards
the connector's tools (create_timeline, build_timeline, set_up_palace / _world / _building), the homepage's "Turn into
another format…" and the Bass route, so there is no free back door around it. Beta guard order on a server route: IP
limit, allowlist, account limiter, terms, THEN this, then the credit hold; a refusal costs no upstream call.
"""
from __future__ import annotations

import os

FORMATS = ("timeline", "outline", "system", "lanes", "palace", "world", "building")

LABELS = {
    "timeline": "Timeline (sketch)",
    "outline": "Outline",
    "system": "System",
    "lanes": "Horizontal timeline",
    "palace": "Mind Palace (a city)",
    "world": "World-map palace",
    "building": "Memory palace (a building)",
}

PLANS = ("free", "plus", "pro")                     # lowest first

# format -> the lowest plan that includes it. Beta: every format is in every plan.
FORMAT_MIN_PLAN = {f: "free" for f in FORMATS}

# the formats that need a place (a city, countries, a building): the place is where cards sit, not content
NEEDS_PLACE = ("palace", "world", "building")


def paywall_on() -> bool:
    return os.environ.get("ALTO_PAYWALL", "") == "1"


def _no_plan(uid) -> str:
    return "free"


_plan_lookup = _no_plan


def set_plan_lookup(fn) -> None:
    """The paywall build supplies how an account's plan is read (from the account's own record)."""
    global _plan_lookup
    _plan_lookup = fn or _no_plan


def plan_of(uid) -> str:
    p = _plan_lookup(uid)
    return p if p in PLANS else "free"


def format_of_brief(brief: dict) -> str:
    """The format a brief builds (the layout / palace_view arguments already applied)."""
    mode = (brief or {}).get("mode") or "linear"
    if mode == "palace":
        v = (brief or {}).get("palace_view") or "city"
        return {"building": "building", "world": "world"}.get(v, "palace")
    if mode == "lanes":
        return "lanes"
    if mode == "outline":
        return "system" if (brief or {}).get("layout") == "solar" else "outline"
    return "timeline"


def allowed(uid, fmt: str) -> dict:
    if fmt not in FORMAT_MIN_PLAN:
        return {"ok": False, "needs_plan": None, "message": f"{fmt!r} is not a format Alto makes."}
    need = FORMAT_MIN_PLAN[fmt]
    if not paywall_on() or PLANS.index(plan_of(uid)) >= PLANS.index(need):
        return {"ok": True}
    return {"ok": False, "needs_plan": need,
            "message": f"{LABELS[fmt]} is in the {need.capitalize()} plan."}


def formats_for(uid) -> list:
    """Every format with whether this account may make it (the homepage greys a row that says no)."""
    out = []
    for f in FORMATS:
        a = allowed(uid, f)
        out.append({"id": f, "label": LABELS[f], "ok": a["ok"], "needs_plan": a.get("needs_plan"),
                    "place": f in NEEDS_PLACE})
    return out
