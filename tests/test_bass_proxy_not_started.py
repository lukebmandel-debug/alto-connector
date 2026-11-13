"""No public entry point, build step, publish step, workflow, release script or MCP tool starts or deploys deploy/bass-proxy, or sets its
store flag (bass_beta/live_go) or its secret (alto-bass-beta-key). Until Luke says "go for the first live call", IT does that by hand.
Static scan of every place that could, plus a check of the MCP tool list and the declared entry points. The scanner is proven to bite by
feeding it a deliberately bad workflow. No network, no key, no subprocess of the scanned code."""
import ast
import io
import re
import tokenize
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# What a start/deploy/flag/secret looks like. Prose in a comment that merely says "deploy/bass-proxy" is allowed ONLY in the files listed
# in MENTION_OK below (they describe where the proxy lives; they cannot run it).
BAD = re.compile(
    r"bass[-_]proxy|deploy/bass|bass_beta/live_go|alto-bass-beta-key|bass_beta_config|functions\s+deploy[^\n]*bass|secrets\s+(?:create|versions)[^\n]*bass",
    re.I)

WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
RELEASE = [ROOT / n for n in ("deploy.sh", "setup.sh", "Dockerfile", "server.json", "pyproject.toml")]
RELEASE += sorted((ROOT / "packaging").glob("*"))
CLI_AND_PUBLISH = [ROOT / "alto" / "publish_static.py", ROOT / "alto" / "mcp_server.py", ROOT / "alto" / "update_check.py"]
# Every non-Bass tool script and every non-Bass module of the app: build steps, publish steps, cloud and store code.
TOOLS = [p for p in sorted((ROOT / "tools").glob("*.py")) if not p.name.startswith("bass_")]
APP = [p for p in sorted((ROOT / "alto").rglob("*.py")) if "bass" not in p.relative_to(ROOT / "alto").parts[0] and not p.name.startswith("bass_")]


def _scan(text: str) -> list[str]:
    return [m.group(0) for m in BAD.finditer(text)]


def _code_only(path: Path) -> str:
    return _code_only_text(path.read_text("utf-8", errors="replace"), path.suffix)


def _code_only_text(text: str, suffix: str = ".py") -> str:
    """A .py file with its comments and docstrings blanked: prose that names the proxy's folder cannot run it, code and string literals can."""
    if suffix != ".py":
        return text
    lines = text.splitlines()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                for n in range(first.lineno - 1, first.end_lineno):
                    lines[n] = ""
    out = "\n".join(lines)
    return "".join(
        "" if tok.type == tokenize.COMMENT else tok.string + (" " if tok.type != tokenize.NEWLINE else "\n")
        for tok in tokenize.generate_tokens(io.StringIO(out).readline))


def _targets():
    seen = []
    for group in (WORKFLOWS, RELEASE, CLI_AND_PUBLISH, TOOLS, APP):
        for p in group:
            if p.is_file() and p not in seen:
                seen.append(p)
    return seen


def test_there_are_four_workflows_and_they_are_the_ones_we_scan():
    assert [p.name for p in WORKFLOWS] == ["publish-pypi.yml", "release.yml", "security.yml", "verify.yml"]


@pytest.mark.parametrize("path", _targets(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_start_deploy_flag_or_secret_for_bass_proxy(path):
    rel = str(path.relative_to(ROOT))
    hits = _scan(_code_only(path))
    assert not hits, f"{rel} references the Bass proxy deploy / flag / secret: {sorted(set(hits))}"


def test_the_only_declared_cli_entry_point_is_the_mcp_server():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert meta["project"]["scripts"] == {"alto-connector": "alto.mcp_server:main"}
    assert not _scan(_code_only(ROOT / "alto" / "mcp_server.py"))


def test_no_mcp_tool_is_a_bass_or_proxy_tool():
    import asyncio
    from alto import mcp_server
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = [t.name for t in tools]
    assert names, "the tool list came back empty, so this check proved nothing"
    bad = [n for n in names if re.search(r"bass|proxy|beta_proxy|live_go", n, re.I)]
    assert not bad, bad


def test_prose_mentions_are_not_commands_but_code_is():
    prose = "# deploy/bass-proxy lives here\nx = 1\n"
    assert not _scan(_code_only_text(prose))
    assert not _scan(_code_only_text('"""docs: deploy/bass-proxy/main.py"""\nx = 1\n'))
    assert _scan(_code_only_text('import os\nos.system("python3 deploy/bass-proxy/deploy.py")\n'))


def test_the_scanner_does_bite():
    bad_workflow = "jobs:\n  d:\n    steps:\n      - run: python3 deploy/bass-proxy/deploy.py --project p\n"
    assert _scan(bad_workflow)
    assert _scan("gcloud functions deploy bass-proxy --source x")
    assert _scan("firestore set bass_beta/live_go true")
    assert _scan("gcloud secrets versions add alto-bass-beta-key --data-file=-")
    assert not _scan("name: verify\non: push\n")
