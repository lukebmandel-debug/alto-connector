#!/usr/bin/env python3
"""Run one shard of the Alto test files. Used by .github/workflows/shard-tests.yml (copy to .github/shard_run.py in the repo).

Files are balanced by size (largest first onto the lightest shard), so shard N of M is the same on every run.
--only-webkit keeps just the files that mention webkit (the macOS shards: the closest thing to Safari a hosted runner has).
Left out on purpose (cannot or must not run on a hosted runner): network-bound Overpass tests, sound/fleet files,
the security-emulator files (own workflow), and anything that needs the owner's private fixtures (those skip themselves).
"""
import argparse, glob, os, subprocess, sys

SKIP = {
    "tests/test_overpass_mirrors.py",
    "tests/test_palace_1997_sound.py", "tests/test_palace_1997_panic.py", "tests/test_palace_1999_fleet.py", "tests/test_mute_audio.py",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--of", type=int, required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only-webkit", action="store_true")
    a = ap.parse_args()
    files = [f for f in sorted(glob.glob("tests/test_*.py")) if f not in SKIP and not f.startswith("tests/security/")]
    if a.only_webkit:
        files = [f for f in files if "webkit" in open(f, encoding="utf-8", errors="ignore").read().lower()]
    bins = [[0, []] for _ in range(a.of)]
    for f in sorted(files, key=lambda f: -os.path.getsize(f)):
        b = min(bins, key=lambda x: x[0])
        b[0] += os.path.getsize(f)
        b[1].append(f)
    mine = sorted(bins[a.shard][1])
    print("shard %d/%d: %d of %d files" % (a.shard, a.of, len(mine), len(files)), flush=True)
    if not mine:
        return 0
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ALTO_", "FIREBASE", "GOOGLE", "GCLOUD"))}
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", str(a.workers), "--dist", "loadfile",
           "--junitxml=junit.xml"] + mine
    rc = subprocess.call(cmd, env=env)
    return 0 if rc == 5 else rc


sys.exit(main())
