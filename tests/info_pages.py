"""Built pages for every format, for the Info-panel tests (one builder per format)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import starter  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402


def starter_page(kind):
    return build_timeline(*load_brief(starter.draft(kind)))[0]


def pages():
    """format name -> built html."""
    out = {k: starter_page(k) for k in starter.KINDS}
    from tests import test_world_palace as w, test_building_palace_tools as b
    out["world"] = w.built()[0]
    out["building"] = b.built()[0]
    try:
        from tests import test_palace as p
        out["city"] = build_timeline(*p.load(p.bundle()))[0]
    except Exception as e:  # noqa: BLE001
        out["city"] = None
        print("city skipped:", e)
    return out
