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
(pd | pd-no-image | in-copyright | unknown), source (the work's public page), commons (Commons file page title after https://commons.wikimedia.org/wiki/, or null), img (key in pma_art.json or null), px,
gs (key into gallery_sources), read_on. A row with lic != pd never gets an image.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PLAN = ROOT / "alto" / "buildings" / "pma_plan.json"
ART = ROOT / "alto" / "buildings" / "pma_art.json"
OUT = ROOT / "alto" / "buildings" / "pma_wall.json"
COMMONS = "https://commons.wikimedia.org/wiki/"          # a row's `commons` is the file page title after this prefix

PLAN_GALLERY = ("PMA gallery number as stated on the PMA object page / visitor map when the plan was built (2026-10-21; alto/buildings/README-pma.md). "
               "The live object pages no longer show a gallery (checked 2026-10-29).")
GREWE_SRC = ("Cordula Grewe, review of the European Galleries 1850-1900, 19th-Century Art Worldwide 21:3 (Autumn 2022), "
             "https://19thc-artworldwide.org/autumn22/grewe-reviews-european-galleries-1850-1900-philadelphia-museum-of-art-philadelphia, read 2026-10-29. "
             "A 2022 hang: check before relying on a work still being in its gallery.")
# artist death years for works that are not among the hosted images (a work is public domain only if its artist died before 1956)
DIED = {"Diego Rivera": 1957}
# Hand-added rows: works NAMED, with their gallery number, in a citable review of the reinstalled galleries (see GALLERY_SOURCES). Each tuple:
# (gallery, title, artist, year, died, PMA object id or None, Commons file title or None, [width, height] or None). A work whose artist died before 1956
# and whose Commons file licence label was read as public domain on COMMONS_READ is lic "pd" (the picture may hang); one with no Commons file found yet is
# "pd-no-image" (labelled frame; add the file later). Gallery -> plan room: 252 and 259 are signed rooms (pc "room"), 250, 255 and 264 only hold the gallery's label
# point (pc "cand"). `pc` also reserves "area" (placement by collection area, not a gallery claim) for a later decision; nothing uses it yet.
GALLERY_ROOMS = {"250": ("l2-n-gal-a", "cand"), "252": ("l2-n-prints", "room"), "255": ("l2-n-gal-b", "cand"), "259": ("l2-n-printstudy", "room"), "264": ("l2-n-end-b", "cand")}
COMMONS_READ = "2026-10-29"
GREWE = [
    ("250", "Morning", "Louis-Joseph-Raphael Collin", "1884", 1916, "103674", None, None),
    ("250", "Woman Ironing", "Francois Bonvin", "1858", 1887, "102735", "File:Woman Ironing, by François Bonvin.JPG", [2608, 3856]),
    ("250", "The Thames, London", "Jules Bastien-Lepage", "1882", 1884, "102724", None, None),
    ("252", "The Folkestone Boat, Boulogne", "Edouard Manet", "c. 1868-72", 1883, "59193", "File:Edouard Manet 091.jpg", [1024, 768]),
    ("252", "Marine in Holland", "Edouard Manet", "1872", 1883, "104451", "File:View in Holland, by Édouard Manet.JPG", [3355, 2706]),
    ("252", "The Steamboat, Seascape with Porpoises", "Edouard Manet", "1868", 1883, "54675", "File:The Steamboat, Seascape with Porpoises, by Édouard Manet.JPG", [2024, 1630]),
    ("255", "Le Bon Bock", "Edouard Manet", "1873", 1883, "59213", "File:Édouard Manet, French - Le Bon Bock - Google Art Project.jpg", [4338, 4921]),
    ("255", "Sappho", "Arnold Bocklin", "1862", 1901, "102730", "File:Arnold Böcklin - Sappho (1862).jpg", [1934, 2495]),
    ("255", "Nymph and Satyr", "Arnold Bocklin", "1871", 1901, "102731", "File:Arnold Böcklin - Nymphe und Satyr (1871).jpg", [3405, 2387]),
    ("255", "Apple Market, Landerneau, Brittany", "Leon-Augustin Lhermitte", "c. 1878", 1925, "102973", "File:Lhermitte - Landerneau, 1878.jpg", [1600, 1129]),
    ("255", "On the Balcony", "Mary Cassatt", "1873", 1926, "104435", None, None),
    ("255", "Legendary Saints of France", "Pierre Puvis de Chavannes", "c. 1879", 1898, "65177", None, None),
    ("255", "The Bridge at Loosduinen", "Jacob Maris", "1872", 1899, "101711", None, None),
    ("255", "Reading from Homer", "Lawrence Alma-Tadema", "1885", 1912, None, None, None),
    ("255", "Return from the Races", "Giuseppe de Nittis", "1875", 1884, None, None, None),
    ("255", "Moorish Chief", "Eduard Charlemont", "1878", 1906, None, None, None),
    ("255", "Highway of Combes-la-Ville", "Giovanni Boldini", "1873 or 1875", 1931, None, None, None),
    ("255", "Return of the Flock, Larens", "Anton Mauve", "1887", 1888, None, None, None),
    ("255", "The Last Breath", "Jozef Israels", "1872", 1911, "47810", None, None),
    ("255", "Faust and Marguerite", "Henri Leys", "1856", 1869, "102947", None, None),
    ("255", "Troubadour", "Thomas Couture", "1843", 1879, None, None, None),
    ("259", "In the Luxembourg Gardens", "John Singer Sargent", "1879", 1925, "101764", "File:John Singer Sargent, American (active London, Florence, and Paris) - In the Luxembourg Gardens - Google Art Project.jpg", [5244, 3669]),
    ("259", "The Rialto, Venice", "John Singer Sargent", "1911", 1925, "102984", "File:John Singer Sargent - The Rialto, Venice (1911).jpg", [3072, 1847]),
    ("259", "The Young Amphibians", "Joaquin Sorolla y Bastida", "1903", 1923, "104425", "File:Joaquin Sorolla Ninos A La Orilla Del Mar.jpg", [4096, 3028]),
    ("259", "Interior of a Tavern", "Peder Severin Kroyer", "1886", 1909, "101699", "File:I købmand Winthers butik i Skagen.jpg", [2362, 1761]),
    ("259", "Boy with Toy Soldiers", "Antonio Mancini", "c. 1876", 1930, "283507", "File:Boy with Toy Soldiers.jpg", [1258, 1500]),
    ("259", "Mermaid", "Edvard Munch", "1896", 1944, None, None, None),
    ("259", "Two Boys on a Log (The Little Boat)", "Albert Edelfelt", "1884", 1905, None, None, None),
    ("259", "Solitude", "Jean-Charles Cazin", "1889", 1901, "102748", None, None),
    ("259", "My Friends", "Viggo Johansen", "1887", 1935, "101698", None, None),
    ("259", "Water Mill", "Frits Thaulow", "1892", 1906, "101776", None, None),
    ("264", "Large Bathers", "Paul Cezanne", "1900-1906", 1906, None, None, None),
]


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]


def extra() -> list[dict]:
    out = []
    for gl, title, artist, year, died, obj, cf, px in GREWE:
        rm, pc = GALLERY_ROOMS[gl]
        lic = ("pd" if cf else "pd-no-image") if died < 1956 else "in-copyright"
        out.append({"key": f"{gl}-{_slug(title)}", "rm": rm, "gl": gl, "pc": pc, "kind": "painting", "title": title, "artist": artist, "year": year, "died": died,
                    "lic": lic, "source": ("https://www.philamuseum.org/objects/" + obj) if obj else None, "commons": cf, "img": None,
                    "px": px, "gs": "grewe2022", "read_on": COMMONS_READ})
    return out


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
                    "source": w.get("pma_url"), "commons": "File:" + im["commons"].removeprefix(COMMONS).removeprefix("File:") if im else None, "img": key, "px": im["orig_px"] if im else None,
                    "gs": "plan", "read_on": art_date()})
    out.extend(extra())
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
                           "in-copyright": "artist died in 1956 or later: labelled empty frame only", "unknown": "licence not established: labelled empty frame only",
                           "pd-no-image": "artist died before 1956 but no Commons file found yet: labelled frame now, the picture can be added once a file is read as pd"},
            "gallery_sources": {"plan": PLAN_GALLERY, "grewe2022": GREWE_SRC},
            "rows": r, "counts": {"rows": len(r), "pd_images": sum(1 for x in r if x["img"]), "in_copyright": sum(1 for x in r if x["lic"] == "in-copyright"),
                                  "unknown": sum(1 for x in r if x["lic"] == "unknown"), "pd_files": sum(1 for x in r if x["lic"] == "pd" and x["commons"]), "pd_no_image": sum(1 for x in r if x["lic"] == "pd-no-image"), "rooms": len(per_room),
                                  "rooms_with_picture": len({x["rm"] for x in r if x["img"]}), "rooms_with_pd_file": len({x["rm"] for x in r if x["lic"] == "pd" and x["commons"]}),
                                  "per_room": {k: {"gallery": rooms[k].get("no"), "area": rooms[k].get("ca"), "n": per_room[k],
                                                   "pictures": sum(1 for x in r if x["rm"] == k and x["img"])} for k in sorted(per_room) if k in rooms}}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(OUT)); a = ap.parse_args()
    t = table(); Path(a.out).write_text(json.dumps(t, separators=(",", ":"), ensure_ascii=True) + "\n", "utf-8")
    print({k: v for k, v in t["counts"].items() if k != "per_room"})
