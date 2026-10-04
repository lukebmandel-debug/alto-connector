"""The report repository must read the key the timelines save reports under;
it read 'alto-reports-<id>' while every timeline wrote 'alto-rp-<id>', so a
generated report never showed up there."""
from alto.build.blocks import ID_PATTERNS
from alto.build.pages import build_reports


def test_repository_reads_the_key_timelines_write():
    html = build_reports([{"title": "X", "href": "x", "sub": "", "courseId": "torts", "reports": True, "units": []}], "torts")
    prefix = ID_PATTERNS["rp_key"].split("{tid}")[0]
    assert f"const KEY = '{prefix}' + courseId;" in html
    assert "const KEY = 'alto-reports-'" not in html


def test_a_built_timeline_saves_reports_under_the_key_the_repository_reads():
    """Both ends from real output, so neither can drift without this failing."""
    import json
    import re
    from pathlib import Path
    from alto.build.builder import build_timeline, load_brief
    d = json.loads((Path(__file__).resolve().parent.parent / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    page = build_timeline(*load_brief(d))[0]
    saved = re.search(r"const _rk = '([^']+)';", page).group(1)                  # what Generate Report writes
    tid = saved[len(ID_PATTERNS["rp_key"].split("{tid}")[0]):]
    assert saved == ID_PATTERNS["rp_key"].format(tid=tid)
    repo = build_reports([{"title": "X", "href": "x", "sub": "", "courseId": tid, "reports": True, "units": []}], tid)
    read = re.search(r"const KEY = '([^']+)' \+ courseId;", repo).group(1)       # what the repository reads
    assert read + tid == saved
