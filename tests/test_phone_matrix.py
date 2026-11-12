"""The phone shot matrix as a test (chunk 1 of ORG/phone-ui-audit-1111.md, section 5).

tools/phone_matrix.py shoots 10 pages (timeline card + whole, outline card + whole, lanes, System, home, Atlas, city map, Blueprint) x Classic,
Retro, Holo x four phone sizes in headless WebKit and measures each. This file turns the measurements into one verdict per ROW of the audit's
section 3 table (E1 .. H3): is the fault present (any cell shows it) or absent?

tests/phone_matrix_known.json holds what each row IS today ("fail" = the fault is present, "pass" = it is not), one line per row id. The run fails on
BOTH kinds of surprise: a row that was "fail" and now passes (a chunk fixed it: flip that one line to "pass"), and a row that was "pass" and now
fails (a regression). Rows WebKit cannot see are listed under "not_covered" with the reason; they stay Simulator rows.

To flip a row after a fix:   edit its line in phone_matrix_known.json, run this file, commit both.
To see the faulty cells:     PHONE_MATRIX_VERBOSE=1 pytest tests/test_phone_matrix.py -s
To keep the metrics/shots:   PHONE_MATRIX_OUT=/some/dir [PHONE_MATRIX_SHOTS=1]
Silent, offline: no cloud env, no account, no network, no audio (nothing is tapped, so nothing plays). Skipped when Playwright cannot be found."""
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

KNOWN = json.loads((Path(__file__).parent / "phone_matrix_known.json").read_text(encoding="utf-8"))
ROW_IDS = ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "C1", "C2", "C3", "C4", "C5", "C6", "W1", "W2", "W3", "W4", "W5",
           "F1", "F2", "F3", "F4", "F5", "F6", "F7", "H1", "H2", "H3"]
CLASSIC_GROUND = {"#ffc59e", "rgb(255,201,138)"}
BARS = 0.62          # in landscape Safari's bars leave about this share of the height (the audit: 250 pt of 402)
PORTRAIT, LAND = ("p402", "p375"), ("l874", "l812")
BAR = ("b874", "b812")      # a phone on its side with Safari's bars up: the page's visible box, 250 pt tall (chunk 5)


def _rgb(c):
    c = c.strip().lower()
    if c.startswith("#"):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(x) for x in re.findall(r"\d+", c)[:3])


def _html_bg(m):
    return m["bodybg"].split("/ html")[1].strip()


def _cells(res, pages=None, styles=None, sizes=None):
    for key, m in sorted(res.items()):
        page, style, size = key.rsplit("-", 2)
        if (pages is None or page in pages) and (styles is None or style in styles) and (sizes is None or size in sizes) and "fail" not in m:
            yield key, m


# row id -> function(results) -> list of faulty cell keys (empty = the row passes today in WebKit)
def e1(res):      # strips behind the status bar and Safari's bar must be the page's ground, not Classic's peach, and match each other
    out = []
    for k, m in _cells(res, ("tl-card", "ol-card", "lanes", "system", "atlas"), ("retro", "holo")):
        t, h = _rgb(m["theme"]), _rgb(_html_bg(m))
        if t != h or t in (_rgb("#ffc59e"), (255, 201, 138)) or h in (_rgb("#ffc59e"), (255, 201, 138)):
            out.append(k)
    return out


def e5(res):      # viewport-fit=cover with no safe-area-inset-left/right anywhere in the page's CSS
    return [k for k, m in _cells(res, sizes=LAND) if m["safeLR"] == 0]


def c1(res):      # the open card runs below what Safari's landscape bars leave (the 250 pt box: the card's last row is inside it, 8 pt clear of the foot, and under the header row)
    return [k for k, m in _cells(res, ("tl-card", "ol-card"), sizes=BAR) if not m.get("cardLow") or m["cardLow"] > m["vh"] - 8 or m["cardBox"][1] < m["hdrBottom"]]


def c2(res):      # a long unit label cut with an ellipsis on the card
    return [k for k, m in _cells(res, ("ol-card",)) if any("node-unit" in c[0] for c in m["clip"])]


def c3(res):      # the focus button on top of another control
    return [k for k, m in _cells(res, ("tl-card", "ol-card"), sizes=LAND + BAR) if any("#af-btn" in o[:2] for o in m["overlap"])]


def w3(res):      # card titles split mid-word on the whole view
    return [k for k, m in _cells(res, ("tl-whole", "ol-whole")) if m["split"]]


def w4(res):      # card titles drawn under 6 px at fit-to-width
    return [k for k, m in _cells(res, ("tl-whole", "ol-whole"), sizes=PORTRAIT) if 0 < m["titlePx"] < 6]


def f1(res):      # lanes opens with a card running off the screen's side
    return [k for k, m in _cells(res, ("lanes",), sizes=PORTRAIT) if m["cards"]]


def f2(res):      # the step bar's Next sits under the MENU tile or off the screen
    return [k for k, m in _cells(res, ("lanes",), sizes=PORTRAIT)
            if any("button.lnv-next" in o[:2] for o in m["overlap"]) or any("lnv-next" in c[0] for c in m["cut"])]


def f6(res):      # Atlas pins under 32 pt
    return [k for k, m in _cells(res, ("atlas",)) if m["pins"] and min(m["pins"]) < 32]


def h1(res):      # tiles show through where the header's clef, tag and wordmark sit (no backing)
    return [k for k, m in _cells(res, ("home",), sizes=LAND + BAR) if "tile" in m["topAt"]]


def w2(res):      # a unit chip, card or label cut by the header row's foot, or under the clef / wordmark, on the whole view held sideways
    return [k for k, m in _cells(res, ("ol-whole",), sizes=LAND + BAR) if m["cutByHeader"]]


def f5(res):      # the Atlas held sideways: a label, tag or pin under the header, or under the Tour bar
    return [k for k, m in _cells(res, ("atlas",), sizes=LAND + BAR) if m["cutByHeader"] or m["tourHits"]]


def h2(res):      # tile action buttons under the 44 pt touch size
    return [k for k, m in _cells(res, ("home",)) if 0 < m["tileBtn"] < 44]


CHECKS = {"E1": e1, "E5": e5, "C1": c1, "C2": c2, "C3": c3, "W2": w2, "W3": w3, "W4": w4, "F1": f1, "F2": f2, "F5": f5, "F6": f6, "H1": h1, "H2": h2}


@pytest.fixture(scope="module")
def matrix():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    out = os.environ.get("PHONE_MATRIX_OUT")
    t = time.time()
    try:
        res = pm.measure(out, None, bool(os.environ.get("PHONE_MATRIX_SHOTS")) and bool(out))
    except Exception as e:                      # WebKit not installed for this Playwright
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    res["_seconds"] = round(time.time() - t)
    return res


def test_every_audit_row_is_accounted_for():
    rows, nc = set(KNOWN["rows"]), set(KNOWN["not_covered"])
    assert rows | nc == set(ROW_IDS) and not rows & nc, (sorted(set(ROW_IDS) - rows - nc), sorted(rows & nc))
    assert rows == set(CHECKS), "known.json rows and the checks must be the same set"
    assert all(v in ("fail", "pass") for v in KNOWN["rows"].values())
    assert all(KNOWN["not_covered"].values()), "a not-covered row needs its reason"


def test_every_cell_of_the_matrix_loaded(matrix):
    bad = {k: m["fail"] for k, m in matrix.items() if k != "_seconds" and "fail" in m}
    assert not bad, bad
    assert len([k for k in matrix if k != "_seconds"]) == 10 * 3 * 4 + 5 * 3 * 2      # + the pages the landscape rows measure at the two bar-box sizes
    assert not {k: m["errs"] for k, m in matrix.items() if k != "_seconds" and m.get("errs")}, "page errors in the matrix"


def test_the_matrix_runs_in_under_15_minutes(matrix):
    assert matrix["_seconds"] < 15 * 60


@pytest.mark.parametrize("row", sorted(CHECKS))
def test_row(matrix, row):
    res = {k: v for k, v in matrix.items() if k != "_seconds"}
    cells = CHECKS[row](res)
    now = "fail" if cells else "pass"
    if os.environ.get("PHONE_MATRIX_VERBOSE"):
        print(f"\n{row} {now} {len(cells)} cells: {cells[:6]}")
    want = KNOWN["rows"][row]
    if want == "fail" and now == "pass":
        pytest.fail(f"{row} now PASSES (unexpected pass): flip its line in tests/phone_matrix_known.json to \"pass\"")
    if want == "pass" and now == "fail":
        pytest.fail(f"{row} now FAILS (regression) in {len(cells)} cells, e.g. {cells[:4]}")
