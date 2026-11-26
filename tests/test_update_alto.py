"""Updating the connector from inside Claude (alto/update_install.py, and the update note every editing tool leads with, mcp_server.py).

Nothing here downloads, opens or installs anything: GitHub, the download and the open command are all stubbed."""
import hashlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv, update_check, update_install as ui   # noqa: E402

GOOD = b"the newest alto"
DIGEST = "sha256:" + hashlib.sha256(GOOD).hexdigest()
NAME = ui.asset_name("darwin", "arm64")
REL = {"tag_name": "v9.9.9", "assets": [{"name": NAME, "digest": DIGEST, "browser_download_url": ui.DOWNLOAD_PREFIX + "v9.9.9/" + NAME}]}


class _Reg:
    """A stand-in for FastMCP: what the registration hook sees."""
    def __init__(self):
        self.tools = {}

    def tool(self, *a, **k):
        def reg(fn):
            self.tools[fn.__name__] = fn
            return fn
        return reg


def _hooked():
    r = _Reg()
    srv._lead_with_update_note(r)

    @r.tool(annotations=srv.RW)
    def add_nodes():
        return {"ok": 1}

    @r.tool(annotations=srv.DESTRUCTIVE)
    def delete_nodes():
        return {"ok": 2}

    @r.tool(annotations=srv.RO)
    def list_projects():
        return {"ok": 3}

    @r.tool(annotations=srv.RO)
    def get_timeline():
        return {"ok": 4}

    @r.tool(annotations=srv.RW)
    def sign_in():
        return {"ok": 5}
    return r.tools


@pytest.fixture
def behind(monkeypatch):
    monkeypatch.delenv("ALTO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(update_check, "start", lambda: None)
    monkeypatch.setattr(update_check, "running_version", lambda: "1.0.0")
    monkeypatch.setattr(update_check, "latest_version", lambda: "9.9.9")


def test_every_write_tool_and_the_two_session_starters_lead_with_the_note_when_behind(behind):
    t = _hooked()
    for name in ("add_nodes", "delete_nodes", "get_timeline"):
        out = t[name]()
        assert list(out)[0] == "update_alto" and "update_alto tool" in out["update_alto_instruction"] and "1.0.0" in out["update_alto"], name
    assert t["list_projects"]() == {"ok": 3} and t["sign_in"]() == {"ok": 5}           # a read, and a sign-in: untouched


def test_no_note_when_current_or_when_the_check_could_not_be_made(monkeypatch):
    monkeypatch.setattr(update_check, "start", lambda: None)
    monkeypatch.setattr(update_check, "running_version", lambda: "9.9.9")
    monkeypatch.setattr(update_check, "latest_version", lambda: "9.9.9")
    t = _hooked()
    assert t["add_nodes"]() == {"ok": 1}                                   # current
    monkeypatch.setattr(update_check, "running_version", lambda: "1.0.0")
    monkeypatch.setattr(update_check, "latest_version", lambda: "")        # offline / rate-limited: the answer is empty, the tool still runs
    assert t["add_nodes"]() == {"ok": 1}
    monkeypatch.setattr(update_check, "latest_version", lambda: "9.9.9")
    monkeypatch.setenv("ALTO_UPDATE_CHECK", "off")
    assert t["add_nodes"]() == {"ok": 1}


def test_a_failing_check_never_blocks_a_tool(monkeypatch):
    monkeypatch.setattr(update_check, "start", lambda: None)

    def boom():
        raise RuntimeError("no network")
    monkeypatch.setattr(update_check, "latest_version", boom)
    assert _hooked()["add_nodes"]() == {"ok": 1}


def test_the_real_registry_marks_the_write_tools_and_not_the_reads():
    tools = srv.mcp._tool_manager._tools
    for n in ("add_nodes", "set_flags", "delete_nodes", "place_nodes", "set_overview", "build_timeline", "publish_timeline", "get_timeline", "get_interview_guide"):
        assert getattr(tools[n].fn, "_update_noted", False), n
    for n in ("list_projects", "update_alto", "sign_in", "connect_account", "set_up_site", "run_layout_preview"):
        assert not getattr(tools[n].fn, "_update_noted", False), n
    assert len(tools) == 36


@pytest.fixture
def installer(monkeypatch, tmp_path):
    monkeypatch.setattr(update_check, "_TEST_ALLOW_OFFLINE", True)
    monkeypatch.setattr(ui, "running_version", lambda: "1.0.0")
    monkeypatch.setattr(ui, "asset_name", lambda *a: NAME)
    monkeypatch.setattr(ui, "_fetch_release", lambda: REL)
    monkeypatch.setattr(ui.tempfile, "mkdtemp", lambda prefix="": str(tmp_path / "fresh") if os.makedirs(tmp_path / "fresh", exist_ok=True) is None else "")
    ran = []

    def popen(cmd, **k):
        ran.append(cmd)

        class P:
            pass
        return P()
    monkeypatch.setattr(ui.subprocess, "Popen", popen)
    return ran


def test_a_matching_download_is_opened_with_claude_and_nothing_else(monkeypatch, installer, tmp_path):
    monkeypatch.setattr(ui, "_download", lambda url, dest: (Path(dest).write_bytes(GOOD), hashlib.sha256(GOOD).hexdigest())[1])
    out = ui.update_alto()
    assert out["ok"] and out["updated"] and out["to"] == "9.9.9" and "Install" in out["message"]
    assert Path(out["file"]).parent == tmp_path / "fresh" and Path(out["file"]).read_bytes() == GOOD       # a fresh temp folder
    assert installer == [["open", "-a", "Claude", out["file"]]] or installer[0][0] in ("open", "cmd")


def test_a_digest_mismatch_stops_deletes_and_never_opens(monkeypatch, installer, tmp_path):
    monkeypatch.setattr(ui, "_download", lambda url, dest: (Path(dest).write_bytes(b"tampered"), hashlib.sha256(b"tampered").hexdigest())[1])
    out = ui.update_alto()
    assert not out["ok"] and "does not match" in out["message"] and installer == []
    assert not (tmp_path / "fresh").exists()


def test_a_release_without_a_digest_or_with_a_foreign_address_is_refused(monkeypatch, installer):
    bad = {"tag_name": "v9.9.9", "assets": [{"name": NAME, "browser_download_url": ui.DOWNLOAD_PREFIX + "x"}]}
    monkeypatch.setattr(ui, "_fetch_release", lambda: bad)
    assert "no SHA-256" in ui.update_alto()["message"] and installer == []
    foreign = {"tag_name": "v9.9.9", "assets": [{"name": NAME, "digest": DIGEST, "browser_download_url": "https://evil.example/x.mcpb"}]}
    monkeypatch.setattr(ui, "_fetch_release", lambda: foreign)
    out = ui.update_alto()
    assert not out["ok"] and "not the Alto repository's" in out["message"] and installer == []


def test_already_newest_downloads_nothing(monkeypatch, installer):
    monkeypatch.setattr(ui, "running_version", lambda: "9.9.9")
    monkeypatch.setattr(ui, "_download", lambda *a: pytest.fail("downloaded"))
    out = ui.update_alto()
    assert out["ok"] and not out["updated"]


def test_offline_says_so_and_touches_nothing(monkeypatch):
    monkeypatch.setattr(update_check, "_TEST_ALLOW_OFFLINE", False)
    monkeypatch.setattr(ui, "_fetch_release", lambda: pytest.fail("fetched"))
    from alto.cloud import offline
    monkeypatch.setattr(offline, "reason", lambda: "ALTO_NO_NETWORK")
    out = ui.update_alto()
    assert not out["ok"] and out["error"] == "offline"


def test_the_file_and_the_open_command_are_chosen_per_os_and_chip():
    assert ui.asset_name("darwin", "arm64") == "Alto-macos-arm64.mcpb" and ui.asset_name("darwin", "x86_64") == "Alto-macos-x64.mcpb"
    assert ui.asset_name("win32", "AMD64") == "Alto-windows-x64.mcpb"
    with pytest.raises(ui.UpdateError):
        ui.asset_name("linux", "x86_64")
    assert ui.open_command("/t/a.mcpb", "darwin") == ["open", "-a", "Claude", "/t/a.mcpb"]
    assert ui.open_command("C:\\t\\a.mcpb", "win32") == ["cmd", "/c", "start", "", "C:\\t\\a.mcpb"]
    with pytest.raises(ui.UpdateError):
        ui.open_command("/t/a", "linux")
