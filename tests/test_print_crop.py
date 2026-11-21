"""Chrome print cuts off the right side of a detail page (Board B-1121-LOOK282A).
Chrome's desktop body is 125% of the viewport; the print CSS must undo it.
Skipped without Playwright's Chromium."""
import json, sys, threading
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402


def test_the_patch_is_registered_and_anchored():
    p = {x["name"]: x for x in PATCHES}["print-crop-body-width"]
    assert p["count"] == 1 and "html.printing.is-blink:not(.mobile) body" in p["new"]


def _measure(tmp_path, prep):
    pw = pytest.importorskip("playwright.sync_api")
    b = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    long = " ".join(["A holding whose reasoning runs on across many lines and words."] * 40)
    b["nodes"][1]["sections"] = [{"h": "Long text", "t": long}]
    html, _ = build_timeline(*load_brief(b))
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    out = {}

    def run():                                   # own thread: a sync Playwright cannot share another's loop
        with pw.sync_playwright() as p:
            try:
                c = p.chromium.launch()
            except Exception as e:
                out["skip"] = str(e)
                return
            pg = c.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(f.as_uri())
            pg.wait_for_timeout(500)
            prep(pg, b)
            pg.emulate_media(media="print")
            pg.set_viewport_size({"width": 720, "height": 900})          # Letter less 11 mm margins, ~96 dpi
            pg.wait_for_timeout(200)
            out.update(pg.evaluate("""()=>{let w=[0,''];for(const e of document.querySelectorAll('body *')){const cs=getComputedStyle(e);if(cs.display=='none'||cs.position=='fixed'||e.closest('#summary-wrap,#canvas')||cs.visibility=='hidden')continue;const r=e.getBoundingClientRect().right;if(r>w[0])w=[r,e.tagName+'#'+e.id]}return ({blink:document.documentElement.classList.contains('is-blink'),
              body:document.body.getBoundingClientRect().width,
              who:w[1],widest:w[0]})}"""))
            c.close()
    t = threading.Thread(target=run)
    t.start()
    t.join()
    if "skip" in out:
        pytest.skip(out["skip"])
    return out


def test_a_chromium_letter_page_of_a_detail_page_is_not_cut_off(tmp_path):
    def prep(pg, b):
        pg.evaluate(f"showDetail('node','{b['nodes'][1]['id']}')")
        pg.evaluate("document.documentElement.classList.add('printing','print-current')")
    r = _measure(tmp_path, prep)
    assert r["blink"] and r["body"] <= 720 and r["widest"] <= 721, r


def test_the_ink_print_fits_too(tmp_path):
    r = _measure(tmp_path, lambda pg, b: pg.evaluate("window._altoInkStage()"))
    assert r["blink"] and r["body"] <= 720, r          # (the staged outline itself is judged in the Letter PDF shots)
