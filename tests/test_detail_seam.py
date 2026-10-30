"""The seam between the chips and a detail page's back / forward bar is a normal thin dividing line (Luke, 2026-10-30:
"You see the tiny black line sitting above forward/back navigation labels, you can have a normal thin dividing line,
but this is not that"): one visual px in a hairline of the theme, never 2px of --border (near-black in the dark theme)."""
import json
from pathlib import Path

from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent


def _html():
    b, nodes, conns = load_brief(json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8")))
    return build_timeline(b, nodes, conns)[0]


def test_the_detail_seam_is_a_hairline_not_a_rule():
    h = _html()
    assert "0 -2px 0 var(--border)" not in h
    assert "box-shadow: 0 -1.25px 0 var(--nav-seam) !important;" in h
    assert "html.dark:not(.mobile){ --nav-seam:rgba(255,255,255,.12); }" in h
