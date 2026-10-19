"""Hosted scripts of the Mind Palace: code the page loads, not part of the page.

A private page is ONE Firestore document (private_shell.MAX_PAGE_BYTES stored bytes) and the palace is already within a few KB of it, so code
that only some palaces use goes to the site instead, in a folder named by the content hash of the file (it never changes under that name, the
browser keeps it for a year). The page holds a ~350 byte loader and every use of what it loads is guarded, so a page whose file is missing
(an exported single file, an old page that asks for an earlier hash) simply lacks that feature.

  ride    the first-person ride (palace_ride.py; its own RIDE_LOADER stands where RIDE_JS used to, loaded at once)
  street  the street-level data of the city (palace_street.py: buildings with their materials and roofs, shop signs, doors, trees, lamps, lanes) for the first-person view — a
          content-hashed JSON blob per city, not a script: every manifest a published page names (m["street"]["h"]), each box's newest and any under two weeks old is published with its shards
          (palace_street.blobs(referenced=...)); a file a page names that the cache lacks is reported (LAST_MISSING -> LAST_STALE), never dropped silently
  bldg    the Building Palace (palace_view "building"): its renderer (palace_building_asset.py, the blueprint and the seam for the first-person view) and, beside it,
          each published Building Palace's plan as plan-<hash>.json (building_schema.hosted_json), written from the briefs at publish (`assets(building_plans=...)`),
          and the first-person interior renderer (palace_building_fpv.py, fetched by the blueprint the first time someone walks in)
  fleet   the toy weapons: the battleship, destroyers, carriers, submarines and military bases of any city, with their sound, the crowd that
          runs from a collapse and the construction rebuild (palace_fleet_asset.py; loaded only by a city that has a vessel or a base)

`ASSETS` lists them; publish_static.regenerate_site writes every one into site/<folder>/ and the hosting headers keep the folder. A new hosted
script is one line here plus its module's `<name>_asset() -> (file name, text)`.
"""
from __future__ import annotations

import importlib
import json as _json

# (folder, module, function) — the function returns (file name under /<folder>/, the script text)
ASSETS = (
    ("ride", "palace_ride", "ride_asset"),
    ("fleet", "palace_fleet_asset", "fleet_asset"),
    ("bldg", "palace_building_asset", "building_asset"),
    ("bldg", "palace_building_fpv", "fpv_asset"),
)


BLOB_FOLDERS = ("street",)


def folders() -> list:
    return [a[0] for a in ASSETS] + list(BLOB_FOLDERS)


def assets(street_refs=None, building_plans=None) -> list:
    """[(folder, file name, text)] of every hosted script. `street_refs`: the street manifest hashes the published pages name (all are published; see palace_street.blobs).
    `building_plans`: {file name: JSON text} of the Building Palace plans the published pages name (building_schema.hosted_json), written into /bldg/ beside the renderer."""
    out = []
    for folder, mod, fn in ASSETS:
        name, text = getattr(importlib.import_module("." + mod, __package__), fn)()
        out.append((folder, name, text))
    out += [("bldg", name, text) for name, text in sorted((building_plans or {}).items())]
    from . import palace_street
    out += [(palace_street.FOLDER, name, text) for name, text in palace_street.blobs(referenced=street_refs)]
    return out


def find(path: str, building_plans=None):
    """(content type, text) for a request path such as /fleet/palace-fleet-0123456789.js (or /street/palace-street-0123456789.json) (the QA kit's server uses it), else None."""
    p = path.split("?")[0]
    for folder, name, text in assets(building_plans=building_plans):
        if p == "/" + folder + "/" + name:
            return ("application/json; charset=utf-8" if name.endswith(".json") else "text/javascript; charset=utf-8"), text
    return None


def loader(path: str, guard: str) -> str:
    """JS that fetches `path` synchronously (answered from the browser's cache after the first visit) and runs it as an inline script
    (the page's CSP allows inline scripts, not eval); `guard` is a global the script defines. A failed request leaves it undefined."""
    return ("(function(){ if(window." + guard + ") return; try{ var x=new XMLHttpRequest(); x.open('GET'," + _json.dumps(path) + ",false); x.send(null);"
            " if(x.status===200 && x.responseText){ var s=document.createElement('script'); s.text=x.responseText;"
            " (document.head||document.documentElement).appendChild(s); if(s.parentNode) s.parentNode.removeChild(s); } }catch(e){} })();")
