"""alto/drive_common.py: the neutral module Bass "Add from Drive" and manual edit's Drive chip share. Plain venv, no SDK, nothing skipped."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import drive_common as DC  # noqa: E402

NAMES = ("ALTO_DRIVE_CLIENT_ID", "ALTO_DRIVE_API_KEY", "ALTO_DRIVE_APP_ID")


def test_any_missing_variable_turns_it_off():
    assert DC.DriveConfig.ENV == NAMES
    full = {NAMES[0]: "cid", NAMES[1]: "key", NAMES[2]: "app"}
    assert DC.enabled(full) is True
    for n in NAMES:
        part = {k: v for k, v in full.items() if k != n}
        assert DC.enabled(part) is False
        assert DC.DriveConfig.from_env(part).partial is True
        assert DC.DriveConfig.from_env(part).missing() == [n]
        assert DC.DriveConfig.from_env(part).public() == {"ok": True, "status": "ok", "available": False}
    assert DC.enabled({}) is False and DC.DriveConfig.from_env({}).partial is False
    assert DC.enabled({NAMES[0]: " ", NAMES[1]: "k", NAMES[2]: "a"}) is False            # blank is absent


def test_the_scope_is_drive_file_in_every_place_that_names_it():
    from alto.bass import drive as bass_drive
    from alto.build import drive_picker_page as pk
    assert DC.SCOPE == "https://www.googleapis.com/auth/drive.file"
    assert bass_drive.SCOPE is DC.SCOPE and pk.SCOPE is DC.SCOPE                          # one constant, not three copies
    assert bass_drive.DriveConfig is DC.DriveConfig and bass_drive._ID is DC._ID
    for mode in ("bass", "ref"):                                                          # the picker JS hard-codes it; a mode cannot widen it
        js = pk.picker_js()
        assert "SCOPE='%s'" % DC.SCOPE in js and js.count("auth/drive") == 1, mode
    assert DC.DriveConfig("a", "b", "c").public()["scope"] == DC.SCOPE


def test_it_imports_nothing_from_bass_or_the_sdk():
    code = ("import sys, alto.drive_common as d\n"
            "bad=[m for m in sys.modules if m.split('.')[0] in ('anthropic','httpx2','httpx') or m.startswith('alto.bass')]\n"
            "print(__import__('json').dumps(bad))")
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=str(ROOT), capture_output=True, text=True, timeout=60,
                         env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []
    src = (ROOT / "alto" / "drive_common.py").read_text(encoding="utf-8")
    imports = [ln for ln in src.splitlines() if ln.startswith(("import ", "from ")) and " import " in ln or ln.startswith("import ")]
    assert imports == ["from __future__ import annotations", "import os", "import re"]


def test_the_id_and_key_checks_are_exact_a_trailing_newline_is_refused():
    from alto import drive_common as DC
    good = "1AbCdEfGhIjKlMn"
    assert DC._ID.match(good) and DC.drive_url(good) == "https://drive.google.com/file/d/%s/view" % good
    for bad in (good + "\n", good + "\r\n", "\n" + good, good + "\n/x"):
        assert not DC._ID.match(bad) and DC.drive_url(bad) is None, repr(bad)
    assert DC.GD_KEY.match("gd-abc123") and not DC.GD_KEY.match("gd-abc123\n")
