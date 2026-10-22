"""Look up each palace city's CURRENT mayor on Wikidata and record it in alto/buildings/city_mayors.json.

The first-person views' avatar (alto/build/fpv_avatar.py) is a stylised figure after the mayor of the palace's city. Who that is changes
with elections, so it is never typed in by hand: this tool reads the city's "head of government" (Wikidata P6), takes the statement that is
current (rank preferred, or no end time), and writes the name, the Wikidata id, the start of the term, the source and today's date.

A city's `look` (the public-facing cues the figure is drawn from) names the person it was written for (`look.for`). When the mayor
changes, the old look no longer matches and the avatar falls back to the neutral generic figure until a new look is written: the
tool says so. Run before a release (no key, no login):

    python -m alto.buildings.mayors            # every city in the file
    python -m alto.buildings.mayors --check    # report only, write nothing (exit 1 when something changed)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = Path(__file__).resolve().parent / "city_mayors.json"
API = "https://www.wikidata.org/w/api.php"
UA = "AltoMayorRefresh/1.0 (https://github.com/lukebmandel-debug/alto-connector)"


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def current_head(city_q: str) -> dict | None:
    """{q, since} of the city's current head of government (P6), or None when Wikidata has no current statement."""
    ent = _get({"action": "wbgetentities", "ids": city_q, "props": "claims"})["entities"][city_q]
    best = None
    for c in ent.get("claims", {}).get("P6", []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value" or c.get("rank") == "deprecated":
            continue
        qual = c.get("qualifiers", {})
        if "P582" in qual and c.get("rank") != "preferred":           # an ended term
            continue
        since = ""
        for s in qual.get("P580", []):
            since = (s.get("datavalue", {}).get("value", {}).get("time") or "").lstrip("+")[:10]
        cand = {"q": snak["datavalue"]["value"]["id"], "since": since, "pref": c.get("rank") == "preferred"}
        if best is None or (cand["pref"], cand["since"]) > (best["pref"], best["since"]):
            best = cand
    return best


def label(q: str) -> str:
    ent = _get({"action": "wbgetentities", "ids": q, "props": "labels", "languages": "en"})["entities"][q]
    return ent.get("labels", {}).get("en", {}).get("value", "")


def refresh(data: dict, today: str) -> list[str]:
    notes = []
    for city in data["cities"]:
        head = current_head(city["wikidata"])
        if not head:
            notes.append(f"{city['name']}: Wikidata has no current head of government; the generic avatar is used")
            city["mayor"] = None
            continue
        old = city.get("mayor") or {}
        name = label(head["q"])
        city["mayor"] = {"name": name, "wikidata": head["q"], "since": head["since"],
                         "source": f"https://www.wikidata.org/wiki/{city['wikidata']}#P6", "retrieved": today}
        if old.get("wikidata") != head["q"]:
            notes.append(f"{city['name']}: mayor is now {name} ({head['q']}), was {old.get('name') or 'none'}")
        look = city.get("look")
        if look and look.get("for") != head["q"]:
            notes.append(f"{city['name']}: the look was written for {look.get('for')}, not {head['q']}: the generic avatar is used until a new look is written")
    return notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    a = ap.parse_args(argv)
    data = json.loads(DATA.read_text("utf-8"))
    before = json.dumps(data, sort_keys=True)
    today = _dt.date.today().isoformat()
    notes = refresh(data, today)
    for n in notes:
        print(n)
    changed = [n for n in notes if "mayor is now" in n or "look was written" in n or "no current" in n]
    if not a.check:
        DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
        print(f"wrote {DATA.relative_to(ROOT)} ({'changed' if json.dumps(data, sort_keys=True) != before else 'dates only'})")
    for c in data["cities"]:
        m = c.get("mayor") or {}
        print(f"  {c['name']}: {m.get('name') or '-'} ({m.get('wikidata') or '-'}, since {m.get('since') or '?'}), retrieved {m.get('retrieved') or '-'}")
    return 1 if (a.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
