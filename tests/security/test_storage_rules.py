"""Firebase Storage: Alto stores nothing there, so no client gets in."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _rules():
    return (ROOT / "storage.rules").read_text(encoding="utf-8")


def test_both_copies_are_identical():
    assert (ROOT / "alto" / "storage.rules").read_bytes() == (ROOT / "storage.rules").read_bytes()


def test_every_client_request_is_denied():
    body = re.sub(r"//[^\n]*", "", _rules())
    allows = re.findall(r"allow\s+([^:]+):\s*if\s+([^;]+);", body)
    assert allows == [("read, write", "false")]
    assert "match /{allPaths=**}" in body


def test_the_rules_travel_with_every_install():
    assert '"storage.rules"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"storage.rules")' in (ROOT / "packaging" / "build_mcpb.py").read_text(encoding="utf-8")
