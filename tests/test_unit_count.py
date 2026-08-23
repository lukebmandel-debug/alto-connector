"""Timelines are not capped at seven units.

The old limit lived only in Python: `validate_brief` rejected >7 acts and the
numerals were a seven-entry table. The engine never had the limit — it builds
bands in a runtime loop over PHASE_META and takes each band's colour from its
own entry (`actBands.forEach(({startY,endY},i) => { const pm = PHASE_META[i]; ... })`),
so it renders as many bands as the brief carries.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.brief import roman, validate_brief, BriefError  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(units, per_unit=2):
    """Build a brief with `units` bands, each carrying `per_unit` nodes.
    Every band needs at least one node — verify_data rejects an empty band."""
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["acts"] = [{"label": f"UNIT {i+1} — FAMILY {i+1}",
                           "short": f"Unit {i+1}"} for i in range(units)]
    entity = d["brief"]["entities"][0]["id"]
    d["nodes"] = [{"id": f"n{a}-{j}", "act": a, "tag": f"F{a+1}",
                   "title": f"Concept {a+1}.{j+1}",
                   "desc": "Placeholder text for layout only.",
                   "entity_ids": [entity]}
                  for a in range(units) for j in range(per_unit)]
    d["connections"] = [[f"n{a}-0", f"n{a}-1", "spine"] for a in range(units)]
    return build_timeline(*load_brief(d))


def _numerals(html):
    meta = html.split("const PHASE_META = [")[1].split("];")[0]
    return [chunk.split("'")[1] for chunk in meta.split("numeral:")[1:]]


def test_roman_matches_the_old_table_then_keeps_going():
    assert [roman(n) for n in range(1, 8)] == \
        ["I", "II", "III", "IV", "V", "VI", "VII"]
    assert roman(8) == "VIII"
    assert roman(9) == "IX"
    assert roman(12) == "XII"
    assert roman(20) == "XX"
    assert roman(49) == "XLIX"


def test_roman_rejects_a_zeroth_band():
    with pytest.raises(BriefError):
        roman(0)


@pytest.mark.parametrize("units", [8, 9, 12, 20])
def test_builds_past_the_old_seven_cap(units):
    html, report = _build(units)
    numerals = _numerals(html)
    assert len(numerals) == units
    assert numerals[-1] == roman(units)
    assert report["nodes"] == units * 2


@pytest.mark.parametrize("units", [8, 12, 20])
def test_every_band_gets_a_phase_var(units):
    """Bands 1-5 land in the :root block, 6+ in their own <style>. Both slabs
    have to cover the whole set, or the tail bands emit nothing."""
    html, _ = _build(units)
    emitted = sorted({int(n) for n in re.findall(r"--phase(\d+):", html)})
    assert emitted == list(range(1, units + 1))


def test_seven_units_still_builds():
    """The old boundary case — guard against an off-by-one in the new slice."""
    html, _ = _build(7)
    assert _numerals(html)[-1] == "VII"


def test_canvas_grows_with_more_units():
    _, few = _build(4)
    _, many = _build(16)
    assert many["layout"]["world_height"] > few["layout"]["world_height"]


def test_one_band_is_still_rejected():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["acts"] = [d["brief"]["acts"][0]]
    with pytest.raises(BriefError, match="at least 2"):
        validate_brief(load_brief(d)[0])
