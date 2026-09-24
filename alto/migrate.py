"""`alto-connector migrate` — copy projects from a folder into your account.

For someone switching to ALTO_STORE=cloud: everything built so far lives in a
local store (default ~/Documents/Alto), under a uid that is a folder name. This
copies projects, timelines, nodes and connections into the signed-in account,
and the built files alongside into this computer's store under the account's
uid, so the next publish needs no rebuild. It never deletes anything, and skips
what the account already has unless --overwrite is given.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store.local import LocalStore

_ARTIFACTS = ("timeline.html", "hosted.html", "private.html", "offline.html")


def _uids(root: Path) -> list[str]:
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", "."))
                  and ((d / "projects").is_dir() or (d / "timelines").is_dir()))


def copy(src: LocalStore, from_uid: str, dst, uid: str, local: LocalStore,
         overwrite: bool = False, log=print) -> dict:
    have_p = {p["project_id"] for p in dst.list_projects(uid)}
    have_t = {t["timeline_id"] for t in dst.list_timelines(uid)}
    n = {"projects": 0, "timelines": 0, "nodes": 0, "skipped": 0}
    for p in src.list_projects(from_uid):
        if p["project_id"] in have_p and not overwrite:
            n["skipped"] += 1
            continue
        dst.put_project(uid, p["project_id"], p)
        n["projects"] += 1
        log(f"  project   {p['name']}")
    for t in src.list_timelines(from_uid):
        tid = t["timeline_id"]
        if tid in have_t and not overwrite:
            n["skipped"] += 1
            continue
        nodes = src.list_nodes(from_uid, tid)       # already in _seq order
        for x in nodes:
            x.pop("_seq", None)
        dst.put_timeline(uid, tid, t)
        if nodes:
            dst.put_nodes(uid, tid, nodes)
        dst.put_connections(uid, tid, src.get_connections(from_uid, tid))
        for a in _ARTIFACTS:
            body = src.get_artifact(from_uid, tid, a)
            if body:
                local.put_artifact(uid, tid, a, body)
        n["timelines"] += 1
        n["nodes"] += len(nodes)
        log(f"  timeline  {(t.get('brief') or {}).get('title', tid)}  ({len(nodes)} cards)")
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="alto-connector migrate")
    ap.add_argument("--from", dest="src", required=True,
                    help="the local store to copy from, e.g. ~/Documents/Alto")
    ap.add_argument("--from-uid", default="",
                    help="which user folder in it (default: every one)")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace projects/timelines the account already has")
    a = ap.parse_args(argv)

    from .cloud.session import get_session
    from .mcp_server import store_dir
    from .publish_static import firebase_configured
    from .store.cloud import CloudStore

    root = Path(a.src).expanduser()
    if not root.is_dir():
        print(f"no such folder: {root}", file=sys.stderr)
        return 2
    s = get_session()
    if not s.configured:
        print("ALTO_FIREBASE_CONFIG is not set, so there is no account to copy into.",
              file=sys.stderr)
        return 2
    if not s.signed_in:
        fc = firebase_configured()
        if not fc:
            print("Set ALTO_FIREBASE_SITE/ALTO_FIREBASE_PROJECT so sign-in has a page to open.",
                  file=sys.stderr)
            return 2
        p = s.start(f"https://{fc[1]}.web.app")
        print(f"Sign in in your browser (opened {p['url']}) …")
        if not s.wait(300):
            print("Sign-in did not finish." + (f" {p['error']}" if p.get("error") else ""),
                  file=sys.stderr)
            return 1
    uid = s.uid
    local = LocalStore(store_dir())
    dst = CloudStore(s, local)
    src = LocalStore(root)
    uids = [a.from_uid] if a.from_uid else _uids(root)
    total = {"projects": 0, "timelines": 0, "nodes": 0, "skipped": 0}
    print(f"Copying into {s.email or uid}:")
    for fu in uids:
        r = copy(src, fu, dst, uid, local, a.overwrite)
        for k in total:
            total[k] += r[k]
    print(f"Done: {total['projects']} projects, {total['timelines']} timelines, "
          f"{total['nodes']} cards copied; {total['skipped']} already there.")
    return 0
