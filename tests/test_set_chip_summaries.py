"""set_chip_summaries: sets ONLY the one-line summary of existing chips. Unknown id / too long writes nothing, "" clears, get_timeline returns it,
the rest of the chip is untouched; and a page with no summary is byte-identical to one built without the feature."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alto import mcp_server as M  # noqa: E402
from alto.build import chip_summaries, print_views as PV  # noqa: E402
from test_set_chip_labels import tid, _brief  # noqa: E402,F401


def test_it_sets_only_the_summary_and_get_timeline_returns_it(tid):
    before = _brief(tid)
    r = M.set_chip_summaries(tid, {"erie": "Diversity case, state law governs; Brandeis: no federal general common law.", "erie-doc": "  Erie\n doctrine "})
    assert not r.get("error") and r["summarised"] == 2, r
    after = _brief(tid)
    assert after["axes"][0]["values"][0]["summary"].startswith("Diversity case")
    assert after["entities"][0]["summary"] == "Erie doctrine"
    for b in (before, after):
        for o in b["entities"] + b["axes"][0]["values"]:
            o.pop("summary", None)
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)


def test_unknown_id_or_too_long_writes_nothing_and_empty_clears(tid):
    before = json.dumps(_brief(tid), sort_keys=True)
    assert M.set_chip_summaries(tid, {"erie": "x", "nope": "y"}).get("error") == "unknown_chip"
    assert M.set_chip_summaries(tid, {"erie": "x" * 241}).get("error") == "invalid_summaries"
    assert json.dumps(_brief(tid), sort_keys=True) == before
    M.set_chip_summaries(tid, {"erie": "one"})
    r = M.set_chip_summaries(tid, {"erie": ""})
    assert r["cleared"] == 1 and "summary" not in _brief(tid)["axes"][0]["values"][0]


def test_a_page_with_no_summary_prints_exactly_what_main_does():
    plain = PV.print_views(None)
    assert "@@INKSUM@@" not in plain and "_ALTO_CHIPSUM" not in plain and "ink-sum" not in plain
    class B:  # a brief with chips but no summary
        entities = []; axes = []
    assert PV.print_views(B()) == plain
    assert chip_summaries.splice("c", "a      @@INKSUM@@\nb", B()) == "cab"
