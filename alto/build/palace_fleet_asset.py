"""The toy fleet as a hosted script (1.9.99): /fleet/palace-fleet-<hash>.js, loaded by a palace that has a warship or a military base (palace_assets.py).

It holds everything that only a battleship's, a carrier's or a base's palace needs, which used to ride in every palace page: how the boats and bases are drawn
(palace_fleet_js.py, the older boat art with them), what each toy does when armed (palace_fleet_fx.py), the synthesised sound (palace_sound.py), the crowd that runs from a
collapse (palace_panic.py), the construction rebuild (palace_construct.py) and the rules for all of it (palace_fleet_css.py). It holds no timeline content. The page keeps
a ~330 byte loader and one call (`_palFleet.draw`); a page whose script is missing draws no boats and has no toys, nothing else changes.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json

from .palace_assets import loader as _loader
from .palace_construct import CONSTRUCT_CSS, CONSTRUCT_JS
from .palace_fleet_css import FLEET_CSS
from .palace_fleet_fx import FLEET_B
from .palace_fleet_js import FLEET_A
from .palace_panic import PANIC_JS
from .palace_sound import SOUND_JS

FLEET_JS = FLEET_A + FLEET_B
FLEET_CSS_ALL = FLEET_CSS + CONSTRUCT_CSS

FLEET_ASSET = ("(function(){var s=document.createElement('style');s.id='pal-fleet-css';s.textContent=" + _json.dumps(FLEET_CSS_ALL)
               + ";(document.head||document.documentElement).appendChild(s);})();\n"
               "(function(){\nif(window._palFleet) return;\n" + CONSTRUCT_JS + SOUND_JS + PANIC_JS + FLEET_JS + "})();\n")
FLEET_V = _hashlib.sha256(FLEET_ASSET.encode("utf-8")).hexdigest()[:10]
FLEET_PATH = f"/fleet/palace-fleet-{FLEET_V}.js"
# the page's function that fetches it (the same synchronous request + inline script as the ride's loader): called only by a city with a vessel or a base
FLEET_LOADER = "\nfunction palLoadFleet(){ " + _loader(FLEET_PATH, "_palFleet") + " }\n"


def fleet_asset() -> tuple[str, str]:
    """(file name under /fleet/, the script) for the site."""
    return FLEET_PATH.rsplit("/", 1)[1], FLEET_ASSET
