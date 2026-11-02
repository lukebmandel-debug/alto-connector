"""The first-person view as a hosted file (no browser): registered beside the blueprint, content-hashed, small, fetched lazily, never in the page."""
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs, palace_assets, palace_building_asset as pba, palace_building_fpv as fpv  # noqa: E402
from tests.building_fpv_plans import stress_plan  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402


def test_the_view_is_a_hosted_hashed_asset_in_the_bldg_folder():
    assert ("bldg", "palace_building_fpv", "fpv_asset") in palace_assets.ASSETS
    name, text = fpv.fpv_asset()
    assert re.fullmatch(r"palace-building-fpv-[0-9a-f]{10}\.js", name) and text == fpv.FPV_ASSET
    assert palace_assets.find("/bldg/" + name)[0].startswith("text/javascript")
    assert fpv.FPV_V in name and fpv.FPV_PATH == "/bldg/" + name


def test_the_renderer_stays_under_120_kb_gzipped():
    gz = len(gzip.compress(fpv.FPV_ASSET.encode("utf-8"), 9))
    assert gz < 120_000, gz


def test_the_blueprint_knows_where_to_fetch_it_and_the_page_carries_none_of_it():
    assert ("var FPV_URL=\"" + (fpv.FPV_PATH if pba.BLUEPRINT_FPV else "") + "\"") in pba.BUILDING_ASSET   # off: no URL, so nothing is ever fetched
    html = built()[0]
    assert "AltoBuildingFPV" not in html and "palace-building-fpv" not in html          # only the blueprint's own ~350 byte loader is inline
    assert "registerFPV" in fpv.FPV_ASSET and "window.AltoBuildingFPV" in fpv.FPV_ASSET


def test_shaders_are_spliced_as_strings_and_every_glsl_block_is_present():
    js = fpv.FPV_ASSET
    for key in ("__TEXGEN__", "__QUADVS__", "__SKYFS__", "__WVS__", "__WFS__"):
        assert key not in js
    assert "void gen(vec2 u" in js and "uniform vec4 uSpP[NS]" in js and "#version 300 es" in js


def test_the_stress_plan_is_a_valid_200_room_building():
    p = stress_plan()
    assert len(p["rm"]) >= 200 and len(p["st"]) >= 3
    bs.validate_plan(p)
    assert bs.summary(p)["bytes_gzip"] < 60_000
