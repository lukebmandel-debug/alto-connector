"""Firebase Storage: nothing of Alto's is there except Bass Documents originals, which only their owner reaches."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _rules():
    return (ROOT / "storage.rules").read_text(encoding="utf-8")


def test_both_copies_are_identical():
    assert (ROOT / "alto" / "storage.rules").read_bytes() == (ROOT / "storage.rules").read_bytes()


def test_every_client_request_is_denied_except_a_bass_documents_owner():
    """One storage.rules for both trees (B5): the ONLY open path is users/{uid}/bass/{fid}, the Bass Documents original, and only to
    its owner, only when the proxy listed it (tests/security/bass_documents_storage.test.mjs runs it on the emulator). No other match
    means every other path is denied."""
    body = re.sub(r"//[^\n]*", "", _rules())
    assert re.findall(r"match\s+(\S+)\s*\{", body) == ["/b/{bucket}/o", "/users/{uid}/bass/{fid}"]
    allows = re.findall(r"allow\s+([^:]+):\s*if\s+([^;]+);", body)
    assert [a for a, _ in allows] == ["get", "list", "create", "update, delete"]
    cond = dict((a, " ".join(c.split())) for a, c in allows)
    assert cond["list"] == "false" and cond["update, delete"] == "false"
    assert cond["get"] == "owner() && listed()"
    assert cond["create"].startswith("owner() && listed() && resource == null")
    assert "request.auth != null && request.auth.uid == uid" in body


def test_the_rules_travel_with_every_install():
    assert '"storage.rules"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"storage.rules",' in (ROOT / "packaging" / "build_mcpb.py").read_text(encoding="utf-8")
