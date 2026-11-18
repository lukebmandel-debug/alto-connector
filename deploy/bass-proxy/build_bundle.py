#!/usr/bin/env python3
"""Copies the whole alto package (the build tools need it, and tested == deployed) and the function files into a clean folder,
without tests or caches, and writes the bundle's requirements.txt = this folder's pins + the connector's own requirements.
Prints the folder. Deploys nothing."""
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "deploy" / "bass-proxy"


def _name(line: str) -> str:
    return re.split(r"[<>=!~\[; ]", line.strip(), 1)[0].lower().replace("_", "-")


def merged_requirements() -> str:
    pins = [l for l in (HERE / "requirements.txt").read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")]
    have = {_name(l) for l in pins}
    extra = [l for l in (ROOT / "requirements.txt").read_text("utf-8").splitlines()
             if l.strip() and not l.startswith("#") and _name(l) not in have]
    return "\n".join(pins + ["# from the connector's requirements.txt"] + extra) + "\n"


FIREBASE_JSON = '{\n  "functions": [{"source": "functions", "codebase": "altoext", "runtime": "python312"}]\n}\n'
SA_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$")


def firebase_bundle(out: Path, service_account=None) -> Path:
    """The hosted Bass function for the Firebase CLI: out/firebase.json + out/functions/{main.py, proxy_main.py, firestore_store.py,
    alto/, requirements.txt}. Deploys nothing; the operator makes functions/venv and runs `firebase deploy` (HOSTED-BUILD.md)."""
    if not service_account or not SA_RE.match(service_account):        # never the default compute account (Editor): STAMP-hosted F2
        raise SystemExit("refused: --service-account <name>@<project>.iam.gserviceaccount.com is required (the function's own least-privilege account)")
    fn = out / "functions"
    fn.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "alto", fn / "alto", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy(HERE / "main.py", fn / "proxy_main.py")
    shutil.copy(HERE / "firestore_store.py", fn / "firestore_store.py")
    src = (HERE / "fb_main.py").read_text("utf-8")
    src = src.replace("SERVICE_ACCOUNT = None", f"SERVICE_ACCOUNT = {service_account!r}", 1)
    if f"SERVICE_ACCOUNT = {service_account!r}" not in src:
        raise SystemExit("refused: fb_main.py changed shape; the service account could not be written")
    (fn / "main.py").write_text(src, "utf-8")
    reqs = "".join(l + "\n" for l in merged_requirements().splitlines() if not l.startswith("functions-framework=="))   # (the Firebase CLI brings its own)
    (fn / "requirements.txt").write_text("firebase-functions==" + FIREBASE_FUNCTIONS_PIN + "\n" + reqs, "utf-8")
    (out / "firebase.json").write_text(FIREBASE_JSON, "utf-8")
    check_pin(fn)
    return out


def check_pin(fn: Path) -> str:
    """The pin is derived from the bundle THIS folder will serve: computed in a fresh interpreter from the COPIED alto package and compared
    with the copied alto/cloud/ext_pin.txt (what luke-alto's hook pins). A drift stops the build."""
    import subprocess
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from alto.build import bass_hosted_ext as e; from alto.cloud import ext_hook as h; "
            "got = e.pin(); want = ' '.join(str(x) for x in h.pin()); print(got); sys.exit(0 if got == want else 3)")
    r = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(fn)], capture_output=True, text=True, env={"ALTO_NO_NETWORK": "1", "PATH": "/usr/bin:/bin"})
    if r.returncode != 0:
        raise SystemExit("refused: the bundle this folder serves does not match alto/cloud/ext_pin.txt (" + (r.stdout.strip() or r.stderr.strip()[-200:]) + ")")
    return r.stdout.strip()


# The Firebase Functions Python SDK. NOT verified offline (no network on the build seat): the deploy seat checks this version exists on
# PyPI, runs `pip install` into functions/venv, and records the resolved hashes in HOSTED-BUILD.md before the deploy.
FIREBASE_FUNCTIONS_PIN = "0.4.3"


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--pin"]:                       # print the pin of the current bundle (a re-pin writes it to alto/cloud/ext_pin.txt, then re-stamp)
        sys.path.insert(0, str(ROOT))
        from alto.build import bass_hosted_ext
        print(bass_hosted_ext.pin())
        return 0
    if args[:1] == ["--firebase"]:
        sa = None
        if "--service-account" in args:
            sa = args[args.index("--service-account") + 1]
            args = [a for a in args if a not in ("--service-account", sa)]
        out = Path(args[1]) if len(args) > 1 else Path(tempfile.mkdtemp(prefix="altoext-"))
        print(firebase_bundle(out, sa))
        return 0
    out = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="bass-proxy-"))
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "alto", out / "alto", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for n in ("main.py", "firestore_store.py", "gcs_object_store.py"):
        shutil.copy(HERE / n, out / n)
    (out / "requirements.txt").write_text(merged_requirements(), "utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
