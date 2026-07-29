"""Golden round-trip: emit(template, originals) must reproduce FROZEN exactly.

Renames recorded in the manifest are replayed on FROZEN and on every extracted
original before comparison (see extract_templates.apply_renames docstring).
This proves the extractor and emitter are exact inverses; it is the permanent
gate for any future engine refreeze.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.emit import emit  # noqa: E402

ENG = ROOT / "engine"


def _renamed(text, renames):
    for r in renames:
        text = text.replace(r["old"], r["new"])
    return text


import pytest  # noqa: E402

PAGES = [
    ("timeline", "timeline_template.html", "terrarium_glass.html"),
    ("home", "home_template.html", "index.html"),
    ("reports", "reports_template.html", "reports.html"),
]


# The fixtures below carry the author's own Terrarium content and are not
# published (see .gitignore). This test is the author's proof that extraction
# is exact; without the fixtures there is nothing to compare against, so it
# skips rather than fails for anyone who clones the public repo.
_HAVE_FIXTURES = (ENG / "TEMPLATE_MANIFEST.json").exists() and (ENG / "FROZEN").is_dir()
pytestmark = pytest.mark.skipif(
    not _HAVE_FIXTURES,
    reason="engine/FROZEN + TEMPLATE_MANIFEST.json are private build-time proofs")


@pytest.mark.parametrize("key,template_name,frozen_name", PAGES)
def test_roundtrip(key, template_name, frozen_name):
    manifest = json.loads((ENG / "TEMPLATE_MANIFEST.json").read_text(encoding="utf-8"))
    m = manifest[key]
    template = (ENG / template_name).read_text(encoding="utf-8")
    frozen = (ENG / "FROZEN" / frozen_name).read_text(encoding="utf-8")

    renames = m.get("renames", [])
    expected = _renamed(frozen, renames)
    regions = {n: _renamed(r["original"], renames) for n, r in m["regions"].items()}
    tokens = {n: _renamed(t["original"], renames) for n, t in m["tokens"].items()}

    out = emit(template, regions, tokens)
    assert len(out) == len(expected), f"length {len(out)} != {len(expected)}"
    assert out == expected, "round-trip output differs from renamed FROZEN"
