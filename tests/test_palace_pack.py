"""The packed city (brief.palace.data_z): columns of whole-number steps under xz. Exact round trip (values and their int/float
types), far smaller than the gzip'd JSON it replaces, and an older palace (base64 gzip JSON) still unpacks."""
import base64
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace  # noqa: E402


def _city(seed=7, nb=400):
    """A city shaped like the engine's output: blocks with rows of lots, tiles, polygon tiles, polylines, records with ints."""
    rnd = random.Random(seed)
    blocks, tiles, tq, streets = [], [], [], []
    for b in range(nb):
        x, y = round(rnd.uniform(0, 20000), 1), round(rnd.uniform(0, 20000), 1)
        lots = [[round(x + 12.5 * k, 1), round(y + 4.0, 1), 93.8, 52.0, -45.0 if b % 3 == 0 else 0.0] for k in range(rnd.randint(1, 8))]
        blocks.append({"x": x, "y": y, "lots": lots, "id": b})
        tiles.append([x, y, round(x + 170, 1), round(y + 120.5, 1)])
        tq.append([x, y, round(x + 140.5, 1), y, round(x + 170, 1), round(y + 120.5, 1), x, round(y + 99.5, 1)])
    for s in range(40):
        p = [8270.0 + s * 170, 2179.5]
        for k in range(30):
            p += [p[-2], round(p[-1] + 170, 1)]
        streets.append({"n": f"{s}th Street", "k": s % 3, "p": p, **({"L": 1} if s % 5 == 0 else {})})
    m = {"W": 26812, "H": 22790, "scale": 0.4123456789, "tiles": tiles, "tq": tq, "streets": streets, "majors": ["Market Street"],
         "doms": [{"id": 0, "xg": [0, 58], "yg": [-510, 130], "clip": [[5870.0, 148.5], [6000, 1.5]], "a": 38.5}],
         "river": [{"n": "Schuylkill River", "w": 120, "p": [round(1000 + 3.3 * i, 1) for i in range(200)]}], "flag": True, "none": None}
    return {"map": m, "blocks": blocks}


def test_pack_round_trips_exactly_with_types():
    d = _city()
    back = palace.unpack(palace.pack(d))
    assert json.dumps(back, sort_keys=True) == json.dumps(d, sort_keys=True)          # ints stay ints, floats floats, order of lists kept
    assert isinstance(back["blocks"][3]["id"], int) and isinstance(back["blocks"][3]["lots"][0][0], float)


def test_a_value_off_the_grid_is_kept_as_it_is():
    d = {"map": {"p": [0.123456, 1.5, 2.25, 3.0, 4.0, 5.0, 6.0], "t": [[0.05, 1.0], [2.0, 3.0], [4.0, 5.0], [6.0, 7.5]]}, "blocks": []}
    assert json.dumps(palace.unpack(palace.pack(d))) == json.dumps(d)


def test_pack_is_far_smaller_than_the_gzip_json_it_replaces():
    d = _city(nb=1500)
    old = base64.b64encode(gzip.compress(json.dumps(d, separators=(",", ":")).encode(), 9, mtime=0)).decode()
    new = palace.pack(d)
    assert new.startswith("xz2:") and len(new) < .5 * len(old), (len(new), len(old))


def test_an_older_palace_still_unpacks():
    d = _city(nb=20)
    legacy = base64.b64encode(gzip.compress(json.dumps(d).encode(), 9, mtime=0)).decode()
    assert palace.unpack(legacy) == d
