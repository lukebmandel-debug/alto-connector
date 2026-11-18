"""The hosted function bundle keeps everything the function's page builder hashes (the Holographic clips included: the hashed /holo/ script name covers them, STAMP-242)
and pins its web stack to the live 238 bundle (cleanup-241 item 3, corrected)."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_bundle", ROOT / "deploy" / "bass-proxy" / "build_bundle.py")
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)

_CODE = "import sys; sys.path.insert(0, sys.argv[1]); from alto.build import holo; print(holo.PATH)"


def _path(root):
    r = subprocess.run([sys.executable, "-I", "-B", "-c", _CODE, str(root)], capture_output=True, text=True, env={"ALTO_NO_NETWORK": "1", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout.strip()


def test_the_holo_script_path_built_inside_the_bundle_equals_the_repos():
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "b"
        bb.firebase_bundle(out, "x-altoext@alto-proj1.iam.gserviceaccount.com")      # check_pin raises if the pinned bundle drifted
        assert (out / "functions" / "alto" / "assets" / "holo_video").is_dir()
        assert _path(out / "functions") == _path(ROOT) and _path(ROOT).startswith("/holo/alto-holo-")


def test_web_stack_pinned_and_functions_framework_aligned():
    reqs = bb.merged_requirements().splitlines()
    for name in ("mcp", "fastapi", "uvicorn", "itsdangerous", "starlette", "pydantic"):
        assert any(l.startswith(name + "==") for l in reqs), name
    assert not any(l.strip() in ("fastapi", "uvicorn", "itsdangerous") for l in reqs)
    assert "functions-framework==3.10.2" in reqs                                      # as in the live 238 bundle's venv
