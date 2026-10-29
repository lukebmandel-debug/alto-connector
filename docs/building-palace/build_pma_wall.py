#!/usr/bin/env python3
"""Assemble alto/buildings/pma_wall.json, the PMA "wall table": one row per work that hangs (or has a labelled empty frame) in a gallery.

    python docs/building-palace/build_pma_wall.py [--out alto/buildings/pma_wall.json]

DATA ONLY (Luke C-1029-001950, "Labelled frame"): a public-domain/open-licence work hangs as its real picture, an in-copyright or unknown-licence work gets
a matching empty frame labelled title, artist and year. The table is hosted off the page (like pma_art.json); nothing here touches the renderer.

Rows come from two inputs, both already cited:
  * alto/buildings/pma_plan.json `sl` (the art slots: room, gallery, work, pc "room"|"cand" = the room is that gallery or only holds its label point)
  * alto/buildings/pma_art.json (the 36 hosted public-domain images: Commons file, artist death year, licence read on 2026-10-21, original pixels)
  * EXTRA below: curated rows added by hand, each with a gallery source (gs) and, for a public-domain image, a Commons file and the date its licence was read.
Plaque slots ("Gallery 220") and period-room markers are not works and are left out.

Row fields: key, rm (plan room id), gl (gallery number as signed), pc, kind, title, artist, year, died (artist's death year or null), lic
(pd | in-copyright | unknown), source (the work's public page), commons (Commons file page title after https://commons.wikimedia.org/wiki/, or null), img (key in pma_art.json or null), px,
gs (key into gallery_sources), read_on. A row with lic != pd never gets an image.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PLAN = ROOT / "alto" / "buildings" / "pma_plan.json"
ART = ROOT / "alto" / "buildings" / "pma_art.json"
OUT = ROOT / "alto" / "buildings" / "pma_wall.json"
COMMONS = "https://commons.wikimedia.org/wiki/"          # a row's `commons` is the file page title after this prefix

PLAN_GALLERY = ("PMA gallery number as stated on the PMA object page / visitor map when the plan was built (2026-10-21; alto/buildings/README-pma.md). "
               "The live object pages no longer show a gallery (checked 2026-10-29).")
# artist death years for works that are not among the hosted images (a work is public domain only if its artist died before 1956)
DIED = {"Diego Rivera": 1957}
# hand-added rows (none yet): {"key", "rm", "gl", "pc", "kind", "title", "artist", "year", "died", "lic", "source", "commons", "gs", "read_on", "px"}
EXTRA: list[dict] = []


def rows() -> list[dict]:
    plan = json.loads(PLAN.read_text("utf-8"))
    art = json.loads(ART.read_text("utf-8"))["images"]
    by_obj = {v["pma_object"]: (k, v) for k, v in art.items()}
    out = []
    for s in plan["sl"]:
        w = s["work"]
        if s["id"].startswith(("sl-plaque-", "sl-g")) and not w.get("artist"):
            continue                                              # a gallery plaque or a period-room marker, not a work
        obj = (w.get("pma_url") or "").rstrip("/").rsplit("/", 1)[-1]
        key, im = by_obj.get(obj, (None, None))
        kind = "tapestry" if s["id"].startswith("sl-const-") else ("textile" if "Wampum" in (w.get("title") or "") else "painting")
        died = im["artist_died"] if im else DIED.get(w.get("artist"))
        lic = "pd" if (im and w.get("img")) else "in-copyright" if (died and died >= 1956) else "unknown"
        out.append({"key": s["id"].removeprefix("sl-"), "rm": s["rm"], "gl": str(s.get("gl")), "pc": s["pc"], "kind": kind,
                    "title": w["title"], "artist": w.get("artist"), "year": w.get("date"), "died": died, "lic": lic,
                    "source": w.get("pma_url"), "commons": im["commons"].removeprefix(COMMONS) if im else None, "img": key, "px": im["orig_px"] if im else None,
                    "gs": "plan", "read_on": art_date()})
    out.extend(EXTRA)
    return out


def art_date() -> str:
    return json.loads(ART.read_text("utf-8"))["verified"]


def table() -> dict:
    r = rows()
    plan = json.loads(PLAN.read_text("utf-8"))
    rooms = {x["id"]: x for x in plan["rm"] if not x.get("gp")}
    per_room = Counter(x["rm"] for x in r)
    return {"building": "pma", "built_from": ["alto/buildings/pma_plan.json", "alto/buildings/pma_art.json"], "rule": json.loads(ART.read_text("utf-8"))["rule"],
            "lic_values": {"pd": "Commons file licence label 'pd' read on read_on AND the artist died before 1956: the real picture hangs",
                           "in-copyright": "artist died in 1956 or later: labelled empty frame only", "unknown": "licence not established: labelled empty frame only"},
            "gallery_sources": {"plan": PLAN_GALLERY},
            "rows": r, "counts": {"rows": len(r), "pd_images": sum(1 for x in r if x["img"]), "in_copyright": sum(1 for x in r if x["lic"] == "in-copyright"),
                                  "unknown": sum(1 for x in r if x["lic"] == "unknown"), "rooms": len(per_room),
                                  "rooms_with_picture": len({x["rm"] for x in r if x["img"]}),
                                  "per_room": {k: {"gallery": rooms[k].get("no"), "area": rooms[k].get("ca"), "n": per_room[k],
                                                   "pictures": sum(1 for x in r if x["rm"] == k and x["img"])} for k in sorted(per_room) if k in rooms}}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(OUT)); a = ap.parse_args()
    t = table(); Path(a.out).write_text(json.dumps(t, separators=(",", ":"), ensure_ascii=True) + "\n", "utf-8")
    print({k: v for k, v in t["counts"].items() if k != "per_room"})
