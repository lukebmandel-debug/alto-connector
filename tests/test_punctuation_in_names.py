"""Names with an apostrophe, a quote, a backslash, an ampersand... ("People’s
Bank v. O'Brien", "Hadley's Case") must never break a page: they sit inside JS
string literals, template literals, attributes and JSON in the built page.
Pure-Python checks on the escaping, then the same names in a real browser
(skipped without Playwright)."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.blocks import js_str, jsq  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.sanitize import js_json  # noqa: E402

# straight and typographic apostrophes, double quote, backslash, a closing
# script tag, an ampersand, a template-literal opener, a line separator
NAME = "O'Brien ’s \"q\" \\ </script> & `z` ${w}   end"
TEXT_KEYS = {"name", "label", "short", "singular", "title", "desc", "tag", "role", "h", "t",
             "summary", "subject", "node_noun", "period_noun", "entity_axis_label",
             "entity_axis_singular", "index_label", "nav_label"}


def _walk(o):
    if isinstance(o, dict):
        for k, v in list(o.items()):
            if k in TEXT_KEYS and isinstance(v, str):
                o[k] = v + " " + NAME
            else:
                _walk(v)
    elif isinstance(o, list):
        for x in o:
            _walk(x)


def nasty(shown_axis=True):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b = d["brief"]
    if shown_axis:
        b["axes"][0].pop("hide_nav", None)             # its names reach the nav and drawer
    _walk(d)
    b["filters"][1:] = []
    b["filters"].append({"id": "kind", "label": "Kind " + NAME, "source": "custom",
                         "values": [{"id": "a", "name": "A " + NAME}, {"id": "b", "name": "B " + NAME}]})
    b["flags"] = [{"id": "piv", "name": "Pivotal " + NAME}]
    b["source_docs"] = [{"id": "doc1", "name": "Doc " + NAME, "url": "https://example.com/a?x=1&y=2"}]
    for i, n in enumerate(d["nodes"][:6]):
        n["filters"] = {"kind": "a" if i % 2 else "b"}
        n["flags"] = ["piv"]
        n["sources"] = ["doc1"]
    return d


@pytest.fixture(scope="module", params=[True, False], ids=["axis-in-nav", "axis-hidden"])
def html(request):
    return build_timeline(*load_brief(nasty(request.param)))[0]


# ── the escapers ─────────────────────────────────────────────────────────────

def test_js_str_quotes_what_would_end_or_confuse_a_literal():
    assert js_str("O'Brien") == "'O\\'Brien'"
    assert js_str("a\\b") == "'a\\\\b'"
    assert js_str('say "hi"') == "'say \"hi\"'"
    assert js_str("a\\'b") == "'a\\\\\\'b'"                # backslash then apostrophe
    assert "</" not in js_str("</script>")
    assert " " not in js_str("a b") and " " not in js_str("a b")


def test_jsq_is_also_safe_inside_a_template_literal():
    q = jsq("a`b${c}'d\\e")
    assert "`" not in q and "$" not in q and "'" not in q.replace("\\'", "")
    assert jsq(None) == ""


def test_js_json_keeps_the_text_and_hides_what_ends_a_script():
    s = js_json({"n": "Hadley's </script><!--     \"x\" \\"})
    assert "</" not in s and "<!--" not in s and " " not in s and " " not in s
    assert "Hadley's" in s                                  # the apostrophe is not touched
    back = json.loads(s.replace("<\\/", "</").replace("<\\!--", "<!--"))
    assert back["n"] == "Hadley's </script><!--     \"x\" \\"


# ── the built page ──────────────────────────────────────────────────────────

def test_the_page_builds_and_keeps_the_apostrophes(html):
    # build_timeline syntax-checks every script (when node or QuickJS is there)
    assert "O'Brien" in html and "O\\'Brien" in html
    assert "’s" in html


def test_a_name_in_a_js_literal_never_closes_it(html):
    for line in html.splitlines():
        if "O\\\\'Brien" in line or "O\\'Brien" in line:
            continue
        # a raw apostrophe inside a single-quoted drawer / print / share line
        if ("drawer-label" in line or "nav-drawer-title" in line or "print-tl-title" in line) \
                and line.lstrip().startswith("'") and "O'Brien" in line:
            pytest.fail("unescaped apostrophe in a JS string: " + line[:160])


def test_nothing_closes_a_script_early(html):
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", html, re.S):
        assert "</script" not in m.group(1).lower()


def test_the_homepage_reads_names_as_text():
    from alto.build.pages import build_home
    h = build_home([{"name": "P " + NAME, "pid": "p", "courses": [
        {"title": "T " + NAME, "href": "t.html", "sub": "1 unit", "courseId": "c", "units": []}]}])
    assert "cssq(" in h and ".tile-title').textContent = c.title" in h
    assert "</script> &" not in h.split("const PROJECTS")[1].split(";\n")[0]


# ── in a browser ─────────────────────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")

EDITS = {   # what manual edit mode keeps for a card, a unit, chips and a filter made on the page
    "nn|card-aaaa11": {"b": None, "t": 1, "v": {"p": "", "a": 0, "t": "New " + NAME, "g": "Tag " + NAME,
                                                 "d": "Desc " + NAME, "c": "var(--accent)"}},
    "nu|unit-bbbb22": {"b": None, "t": 2, "v": {"n": 9, "c": "#e0654a", "l": "Unit " + NAME}},
    "ne|env|hadley-case": {"b": None, "t": 3, "v": {"name": "Case " + NAME, "color": "#e0654a",
                           "cite": "Cite " + NAME, "h": "Note " + NAME, "t": "Body " + NAME,
                           "link": "https://example.com/x?a=1&b=\"2\"", "grp": ""}},
    "ne|c|my-doctrine": {"b": None, "t": 4, "v": {"name": "Doctrine " + NAME, "color": "#2fb380"}},
    "fl|list": {"b": [], "t": 5, "v": [{"id": "f-aaaa", "name": "Flag " + NAME}]},
}


def _browse(page_file, vp, mobile, bt):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, bt).launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no {bt}: {e}")
        ctx = b.new_context(**(p.devices["iPhone 13"] if mobile else {"viewport": vp}))
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:300]))
        key = json.dumps(json.dumps({"v": 1, "ops": EDITS}))
        pg.add_init_script(f"try{{localStorage.setItem('alto-ed-contracts-outline', {key})}}catch(e){{}}")
        pg.goto(page_file.as_uri())
        pg.wait_for_timeout(1000)
        ids = pg.evaluate("({env:Object.keys(ENVS),char:Object.keys(CHARS),node:Object.keys(NODE_DETAILS)})")
        for kind, lst in ids.items():
            for i in lst:
                pg.evaluate(f"showDetail('{kind}','{i}')")
        pg.evaluate("showTimeline()")
        pg.evaluate("document.querySelectorAll('button').forEach(b=>{try{ if(!b.disabled && /nav-btn|drawer-btn/.test(b.className)) b.click() }catch(e){}})")
        for sel in ("#info-icon", "#search-glyph"):
            try:
                pg.click(sel, timeout=800)
            except Exception:
                pass
        try:
            pg.fill("#search-input", "Brien")
        except Exception:
            pass
        pg.wait_for_timeout(500)
        out = {"errs": errs,
               "nav": pg.evaluate("document.getElementById('nav').innerText"),
               "card": pg.evaluate("(document.querySelector('#node-card-aaaa11 .node-title')||{}).textContent"),
               "env": pg.evaluate("(function(){var d=document.createElement('div');"
                                  "d.innerHTML=ENVS['hadley-case'].name;return d.textContent})()"),
               "drawer": pg.evaluate("(document.getElementById('nav-drawer')||{}).textContent||''")}
        b.close()
        return out


@pytest.mark.parametrize("bt,vp,mobile", [("chromium", {"width": 1400, "height": 900}, False),
                                          ("chromium", {"width": 390, "height": 844}, True),
                                          ("webkit", {"width": 1400, "height": 900}, False)])
def test_a_page_full_of_punctuated_names_runs_without_errors(tmp_path, bt, vp, mobile):
    f = tmp_path / "page.html"
    f.write_text(build_timeline(*load_brief(nasty(True)))[0], encoding="utf-8")
    r = _browse(f, vp, mobile, bt)
    errs = [e for e in r["errs"] if "alto-cloud" not in e]
    assert errs == []
    # the name reads as typed, wherever this width shows it
    assert "O'Brien ’s \"q\" \\" in (r["drawer"] if mobile else r["nav"])
    assert r["card"] and r["card"].startswith("New O'Brien")
    assert r["env"] and "O'Brien" in r["env"]
