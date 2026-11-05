"""The Memory Atlas's country flags (Luke 2026-11-04: "please have country flags pop up with nodes"): one small SVG per country, hosted OFF the page.

Data: alto/assets/flags/flags.json.gz ({ISO3: minified SVG}; docs/world-palace/build_world_flags.py makes it from the flag-icons package, MIT, see
alto/assets/flags/LICENSE). Each flag is hosted in the Atlas's own /world/ folder as flag-<ISO3>-<hash>.svg and the renderer (palace_world.py)
fetches only the one a card's country needs, the first time it is shown (an <img>; the browser keeps it for a year). The page carries nothing.

NEUTRAL: the places that get the neutral pennant and no flag. Antarctica; the disputed or contested (Northern Cyprus, Siachen Glacier, Somaliland,
Western Sahara); and the territories whose ISO code is another state's (Ashmore and Cartier, Indian Ocean Territories, Heard and McDonald: Australia's;
Saint Helena: the set draws the United Kingdom's) so that none shows another state's flag. A flag the set lacks, or a page whose hosted file is missing, shows the same pennant.
"""
from __future__ import annotations

import functools
import gzip
import hashlib
import json
import os

from .world_geo import DIR as _WORLD_DIR, FOLDER

DIR = os.path.join(os.path.dirname(_WORLD_DIR), "flags")
NEUTRAL = ("ATA", "ATC", "CYN", "HMD", "IOA", "KAS", "SAH", "SHN", "SOL")


@functools.lru_cache(maxsize=1)
def flags() -> dict:
    """{ISO3: SVG text} of every flag in the set."""
    with gzip.open(os.path.join(DIR, "flags.json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def hosted() -> tuple:
    """((file name under /world/, SVG text), ...): flag-<ISO3>-<10 hex of the SVG's hash>.svg."""
    return tuple(("flag-%s-%s.svg" % (iso, hashlib.sha256(svg.encode("utf-8")).hexdigest()[:10]), svg) for iso, svg in sorted(flags().items()))


def manifest() -> dict:
    """{ISO3: url} of the hosted flags (palace_world.py builds it into its script as GEO.flag)."""
    return {n[5:8]: "/" + FOLDER + "/" + n for n, _ in hosted()}
