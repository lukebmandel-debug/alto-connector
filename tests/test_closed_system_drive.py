"""Closed system: a Drive chip is a reference to a file in the owner's Drive. Alto never reads the file, so Claude cannot: a Drive entry is never a
readable source (no source_docs entry, no local path, no address stored, nothing handed to the offline map). Plain venv, no SDK, nothing skipped."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import detail_extras as dx  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.sanitize import source_map  # noqa: E402

ID = "1AbCdEfGhIjKlMn"
ENTRY = {"id": "gd-abc123", "kind": "drive", "drive_id": ID, "name": "Syllabus.pdf", "share": False}


def _d(*entries):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["brief"]["linked_files"] = list(entries)
    return d


def test_a_drive_entry_is_never_a_readable_source():
    b, nodes, conns = load_brief(_d(ENTRY))
    assert not [s for s in b.source_docs if s.get("id") == "gd-abc123" or s.get("kind") == "drive" or ID in json.dumps(s)]
    block, warnings = dx.local_sources(b)
    assert '"files"' not in block and "alto-local-css" not in block and not warnings        # no file on disk is offered to open; only the hidden chip's id map
    assert '"drive": {"gd-abc123": "%s"}' % ID in block
    assert source_map(b).by_id["gd-abc123"]["url"] == ""                                     # not a web source either; its address is built at render


def test_it_cannot_carry_a_path_or_an_address_or_extra_keys():
    for extra in ({"local": "/Users/x/a.pdf"}, {"url": "https://example.com/x"}, {"text": "contents"}):
        with pytest.raises(BriefError):
            build_timeline(*load_brief(_d({**ENTRY, **extra})))
    for bad in ({**ENTRY, "drive_id": "short"}, {**ENTRY, "share": "yes"}, {**ENTRY, "share": 1}, {**ENTRY, "id": "Bad Id"}):
        with pytest.raises(BriefError):
            build_timeline(*load_brief(_d(bad)))
    with pytest.raises(BriefError):
        build_timeline(*load_brief(_d(ENTRY, dict(ENTRY))))                                  # a duplicate id


def test_an_old_style_file_entry_still_works_beside_it():
    d = _d(ENTRY, {"id": "file-abcdef12", "name": "Offer.pdf", "local": "/Users/x/Offer.pdf"})
    b, nodes, conns = load_brief(d)
    assert [s["id"] for s in b.source_docs if s.get("local")] == ["file-abcdef12"]
    build_timeline(b, nodes, conns)


def test_nothing_reads_a_drive_file(monkeypatch):
    """The build opens no file and makes no request for a chip."""
    import builtins
    import socket
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    d = _d(ENTRY)
    root = next(n for n in d["nodes"] if not n.get("parent"))
    root["sections"] = [{"h": "Files", "t": 'See <a href="src:gd-abc123">the syllabus</a>.'}]

    def spy(f, *a, **k):
        opened.append(str(f))
        return real_open(f, *a, **k)
    monkeypatch.setattr(builtins, "open", spy)
    html, _ = build_timeline(*load_brief(d))
    assert "the syllabus" in html and not [p for p in opened if ID in p or "Syllabus" in p]


def test_the_stored_entry_names_only_what_a_reference_needs():
    from alto.edits import drives_in
    chip = ('<a data-gdrive="gd-abc123" data-gdrive-id="%s" data-file-name="Syllabus.pdf" data-gdrive-share="0" href="https://drive.google.com/file/d/%s/view">x</a>' % (ID, ID))
    assert drives_in(chip) == [ENTRY] and set(drives_in(chip)[0]) == {"id", "kind", "drive_id", "name", "share"}
