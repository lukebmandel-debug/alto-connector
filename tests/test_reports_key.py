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
