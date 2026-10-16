"""City engine v2, the one-domain guarantee (design 0 and 8.1): a city that detects as ONE grid domain and no free
domain is drawn by the fast path, byte-identical to the v1 grid() (1.9.78 with the hard-coded tilted box removed).
The hashes in fixtures/grid_snapshot.json were taken from the v1 code before the v2 pipeline was wired
(TILT_DEG = 0, i.e. today's grid() minus the TILT_BOX hack; for every case here the box did not apply anyway
except where `tilt_hack` is noted). Regenerate ONLY on purpose: ALTO_SNAPSHOT_WRITE=1 pytest tests/test_grid_snapshot.py."""
import copy
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace  # noqa: E402,F401
from alto.build import palace_grid  # noqa: E402

SNAP = ROOT / "tests" / "fixtures" / "grid_snapshot.json"


def _canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def _sha(g):
    g = {k: v for k, v in g.items() if k not in ("report", "engine")}
    return hashlib.sha256(_canon(g).encode()).hexdigest()


def _cases():
    import test_palace as tp
    import test_palace_parks as tpk
    from city_synth_e5 import grid_city
    out = {
        "city_map": lambda: palace_grid.grid(tp.city_map(), majors=["John F. Kennedy Boulevard", "Market Street", "South 16th Street"]),
        "city_map_plain": lambda: palace_grid.grid(tp.city_map()),
        "wide_city": lambda: palace_grid.grid(tp._wide_city(), majors=["Market Street"]),
        "wide_city_nobank": lambda: palace_grid.grid({**tp._wide_city(), "bank": None, "rivers": []}),
        "parks_city": lambda: palace_grid.grid(tpk._city(), majors=tpk.MAJORS, parks=("Test Square",)),
        "e5_grid_city": lambda: palace_grid.grid(copy.deepcopy(grid_city()), majors=["Row A Street"],
                                                 diagonals=["Diagonal Avenue"], landmarks=[{"name": "Town Hall"}]),
    }
    fx = ROOT / "tests" / "fixtures" / "cities" / "washington.json.gz"
    if fx.exists():
        out["washington_fixture"] = lambda: palace_grid.grid(json.loads(gzip.decompress(fx.read_bytes()).decode()))
    return out


CASES = sorted(_cases())


@pytest.mark.parametrize("name", CASES)
def test_one_domain_city_is_byte_identical_to_v1(name):
    g = _cases()[name]()
    if os.environ.get("ALTO_SNAPSHOT_WRITE"):
        data = json.loads(SNAP.read_text()) if SNAP.exists() else {}
        data[name] = _sha(g)
        SNAP.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        pytest.skip("snapshot written")
    data = json.loads(SNAP.read_text())
    assert name in data, "no snapshot for %s" % name
    assert (g.get("engine") or {}).get("path", "v1") in ("v1", "fast"), "a one-domain city must take the fast path"
    assert _sha(g) == data[name]
