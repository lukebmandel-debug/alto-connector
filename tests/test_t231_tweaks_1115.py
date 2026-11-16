"""v1.9.232 small fixes, static checks (no browser): terms denied copy, Holo chip, phone corners, no Bass words in the default build."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "alto/cloud/alto-cloud.js").read_text("utf-8")


def test_terms_denied_says_invite_only_with_a_sign_out_and_the_rules_are_unchanged():
    assert "This feature is invite-only during the beta, and this account isn't on the list." in JS
    assert "termsDenied = !!(e && e.code === 'permission-denied')" in JS
    assert JS.count("TERMS_DENIED") >= 3 and "Please try again" in JS            # the generic failure keeps its text for every other error
    assert "id=\"alto-terms-no\">Sign out</button>" in JS
    rules = (ROOT / "firestore.rules").read_text("utf-8")
    assert rules == (ROOT / "alto/firestore.rules").read_text("utf-8")           # (the parity test pins the bytes)


def test_default_build_has_no_bass_words():
    from alto.build import pages
    for name, html in (("home", pages.build_home([])), ("reports", pages.build_reports([], "")),
                       ("home_template", (ROOT / "alto/engine/home_template.html").read_text("utf-8")),
                       ("reports_template", (ROOT / "alto/engine/reports_template.html").read_text("utf-8")),
                       ("timeline_template", (ROOT / "alto/engine/timeline_template.html").read_text("utf-8"))):
        assert not re.search(r"bass", html, re.I), (name, re.search(r".{40}bass.{40}", html, re.I | re.S).group(0))
    src = (ROOT / "alto/build/home_look.py").read_text("utf-8")
    assert "_altoStudyPlanMake" in src and "Bass" not in src[src.index("SP_CARD_JS"):src.index("SP_CARD_JS") + 6000]


def test_holo_today_chip_has_no_halo():
    from alto.build import holo
    flat = holo.css().replace("\n", "")
    assert ".sp-card b{text-shadow:none !important;}" in flat
    assert flat.index(".sp-card b{text-shadow:none") > flat.index(".sp-card *){text-shadow:1px 0px 0")      # after the halo rule, so it wins


def test_phone_corner_buttons_are_44_in_both_template_copies():
    for root in ("alto/engine", "engine"):
        for f in ("home", "reports"):
            s = (ROOT / root / f"{f}_template.html").read_text("utf-8")
            a = s.index("C1 (batch 3)")
            blk = s[a:a + 9000]
            assert "width:44px !important; height:44px !important; max-height:44px !important" in blk and "34px !important" not in blk, (root, f)
    assert (ROOT / "engine/home_template.html").read_bytes() == (ROOT / "alto/engine/home_template.html").read_bytes()
    assert (ROOT / "engine/reports_template.html").read_bytes() == (ROOT / "alto/engine/reports_template.html").read_bytes()
