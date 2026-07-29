"""XSS and injection regressions for the build path.

The engine renders detail sections with `${s.h}`/`${s.t}` straight into
innerHTML (frozen Terrarium behaviour), so the only place user content can be
made inert is alto/build/sanitize.py. These tests build a real timeline whose
every text field is an attack payload and assert nothing executable survives.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.sanitize import (  # noqa: E402
    clean_markup, clean_svg, css_color, esc, sanitize_brief, unescape_text)

SAMPLE = ROOT / "samples" / "contracts_brief.json"

PAYLOADS = [
    '<script>window.__pwned=1</script>',
    '<img src=x onerror="window.__pwned=1">',
    '<svg><animate onbegin="window.__pwned=1"></svg>',
    '<a href="javascript:window.__pwned=1">click</a>',
    '<iframe src="https://evil.test"></iframe>',
    "</script><script>window.__pwned=1</script>",
    "'; window.__pwned=1; //",
    '<div style="background:url(javascript:alert(1))">x</div>',
]


# ── unit level ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload", PAYLOADS)
def test_clean_markup_drops_executables(payload):
    out = clean_markup(payload)
    assert "<script" not in out.lower()
    assert "<iframe" not in out.lower()
    assert "onerror" not in out.lower()
    assert "onbegin" not in out.lower()
    assert "javascript:" not in out.lower()


def test_clean_markup_keeps_legitimate_formatting():
    out = clean_markup('<p>A <strong>holding</strong> and <em>dicta</em>.</p>')
    assert "<strong>holding</strong>" in out
    assert "<em>dicta</em>" in out


def test_clean_markup_keeps_safe_links_and_text_of_dropped_tags():
    assert 'href="https://example.test/x"' in clean_markup(
        '<a href="https://example.test/x">src</a>')
    # prose inside a disallowed wrapper survives; the wrapper does not
    out = clean_markup("<marquee>important text</marquee>")
    assert "important text" in out and "marquee" not in out.lower()


def test_clean_markup_balances_stray_end_tags():
    assert clean_markup("</div></div>text").count("</div>") == 0


def test_clean_svg_allows_glyphs_but_not_script():
    ok = clean_svg('<svg viewBox="0 0 10 10"><path d="M0 0 L10 10" '
                   'stroke="currentColor"/></svg>')
    assert "<path" in ok and 'd="M0 0 L10 10"' in ok
    bad = clean_svg('<svg onload="window.__pwned=1"><script>x()</script>'
                    '<path d="M0 0"/></svg>')
    assert "onload" not in bad.lower() and "<script" not in bad.lower()


def test_css_color_rejects_breakout():
    assert css_color("#a78bfa", "fallback") == "#a78bfa"
    assert css_color("var(--lucy)", "fallback") == "var(--lucy)"
    assert css_color("red'; window.__pwned=1; x='", "fallback") == "fallback"
    assert css_color("url(javascript:alert(1))", "fallback") == "fallback"


def test_esc_roundtrips_through_unescape():
    assert unescape_text(esc("Hart & Sacks <the> \"legal process\"")) == \
        'Hart & Sacks <the> "legal process"'


def test_ordinary_titles_are_not_mangled():
    """The reason we strip rather than escape: the engine escapes a node title
    on the card but interpolates it raw on the detail page, so an escaped value
    would render as `Smith &amp; Jones` in one of the two places."""
    d = json.loads(SAMPLE.read_text())
    d["brief"]["title"] = "Contracts & Remedies"
    d["nodes"][0]["title"] = "Smith & Jones v. O'Brien"
    brief, nodes, _ = load_brief(d)
    sanitize_brief(brief, nodes)
    assert brief.title == "Contracts & Remedies"
    assert nodes[0].title == "Smith & Jones v. O'Brien"


def test_sanitize_brief_is_idempotent():
    d = json.loads(SAMPLE.read_text())
    d["brief"]["title"] = "Contracts & <b>Remedies</b>"
    brief, nodes, _ = load_brief(d)
    sanitize_brief(brief, nodes)
    once = brief.title
    sanitize_brief(brief, nodes)
    assert brief.title == once == "Contracts & Remedies"


@pytest.mark.parametrize("nested", [
    "<scr<b>ipt>window.__pwned=1</scr</b>ipt>",
    "<<a>script>window.__pwned=1<</a>/script>",
    "<img src=x onerror=alert(1)",          # unterminated tag
])
def test_plain_text_cannot_reassemble_a_tag(nested):
    """The invariant is the absence of `<`: with no tag opener, no element or
    attribute can be created. A stray `>` may survive and is deliberately left
    alone — it is literal text in element content, and stripping every `>`
    would mangle ordinary prose like "A > B"."""
    from alto.build.sanitize import plain_text
    assert "<" not in plain_text(nested)


# ── end to end ───────────────────────────────────────────────────────────────

def _poisoned_build():
    d = json.loads(SAMPLE.read_text())
    p = PAYLOADS[0] + PAYLOADS[1] + PAYLOADS[3]
    short = PAYLOADS[1]          # node_noun/singular have tight length caps
    d["brief"]["title"] = p
    d["brief"]["overview_html"] = "".join(PAYLOADS)
    d["brief"]["node_noun"] = "<b onclick=x>Case</b>"
    d["brief"]["entity_axis_label"] = p
    d["brief"]["entity_axis_singular"] = short
    d["brief"]["owner_name"] = "'; window.__pwned=1; //"
    d["brief"]["owner_email"] = "'; window.__pwned=1; //"
    for e in d["brief"].get("entities", []):
        e["name"] = p
        e["symbol_svg"] = '<svg onload="window.__pwned=1"><path d="M0 0"/></svg>'
    for a in d["brief"].get("acts", []):
        a["label"] = p
    for n in d["nodes"]:
        n["title"], n["tag"], n["desc"] = p, p, "".join(PAYLOADS)
        n["color"] = "red'; window.__pwned=1; x='"
        for s in n.get("sections", []):
            s["h"], s["t"] = p, "".join(PAYLOADS)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


def test_payloads_do_not_survive_a_real_build():
    """The canary may appear as *escaped text* — that's the sanitizer working.
    What must never appear is the canary in an executable position."""
    body = _poisoned_build()
    lowered = body.lower()

    executable = [
        "<script>window.__pwned",      # a real script element
        "<img src=x onerror",          # a live event-handler attribute
        'onerror="window.__pwned',
        "onload=\"window.__pwned",
        '<a href="javascript:',        # a live javascript: URL
        "<iframe",
        "<marquee",
    ]
    for form in executable:
        assert form not in lowered, f"executable payload survived: {form!r}"

    # The canary text itself may remain — stripping a tag leaves its contents
    # behind as prose, which is the intended, inert outcome.
    assert "window.__pwned" in body

    # We removed markup, not code — the engine's own scripts are untouched.
    assert "function initLayout(" in body


def test_payloads_do_not_break_js_syntax():
    """A payload that closed a JS literal would leave unbalanced quotes; the
    build's own verifier plus a token scan is the cheap proxy for that."""
    html = _poisoned_build()
    assert "__ALTO_TOK_" not in html and "ALTO:" not in html
    # every generated data literal still parses as one statement per const
    for name in ("NODES_SRC", "CHARS", "NODE_DETAILS"):
        assert re.search(rf"const {name}\s*=", html), f"{name} missing"
