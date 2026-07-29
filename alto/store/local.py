"""Local JSON-file store for development and tests.

Ids reaching this layer are already slug-checked at the MCP tool boundary, but
they are re-checked here: this class turns caller-supplied strings into
filesystem paths, so it is the last place a `../` can be stopped before it
escapes the store root. Both checks are deliberate — the boundary one gives a
good error message, this one is the guarantee.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .base import Store

# One path component: no separators, no NUL, no leading dot (so `..` and dotted
# hidden files are both impossible), single trailing extension allowed.
_COMPONENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,95}(?:\.[A-Za-z0-9]{1,8})?$")


class StorePathError(ValueError):
    pass


def check_component(value, what: str = "path component") -> str:
    s = "" if value is None else str(value)
    if not _COMPONENT.match(s):
        raise StorePathError(
            f"unsafe {what} {s!r}: expected letters, digits, '_' or '-' "
            "(optionally one extension) and no path separators")
    return s


class LocalStore(Store):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _p(self, *parts, mkdir: bool = True) -> Path:
        p = self.root.joinpath(*(check_component(x) for x in parts))
        # Belt and braces: even if the component check were ever loosened, the
        # resolved path must still land inside the store root.
        root = self.root.resolve()
        if not p.resolve().is_relative_to(root):
            raise StorePathError(f"path escapes the store root: {p}")
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _read(p: Path):
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write(p: Path, doc):
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    # ── projects ─────────────────────────────────────────────────────────────
    def list_projects(self, uid):
        d = self._p(uid, "projects", mkdir=False)
        if not d.exists():
            return []
        return sorted((self._read(f) for f in d.glob("*.json")),
                      key=lambda x: x.get("created", ""))

    def get_project(self, uid, pid):
        return self._read(self._p(uid, "projects", f"{pid}.json"))

    def put_project(self, uid, pid, doc):
        self._write(self._p(uid, "projects", f"{pid}.json"), doc)

    # ── timelines ────────────────────────────────────────────────────────────
    def list_timelines(self, uid):
        d = self._p(uid, "timelines", mkdir=False)
        if not d.exists():
            return []
        return sorted((self._read(f / "doc.json")
                       for f in d.iterdir() if (f / "doc.json").exists()),
                      key=lambda x: x.get("created", ""))

    def get_timeline(self, uid, tid):
        return self._read(self._p(uid, "timelines", tid, "doc.json"))

    def put_timeline(self, uid, tid, doc):
        self._write(self._p(uid, "timelines", tid, "doc.json"), doc)

    # ── nodes / connections ──────────────────────────────────────────────────
    def list_nodes(self, uid, tid):
        d = self._p(uid, "timelines", tid, "nodes", mkdir=False)
        if not d.exists():
            return []
        nodes = [self._read(f) for f in d.glob("*.json")]
        return sorted(nodes, key=lambda n: n.get("_seq", 0))

    def put_nodes(self, uid, tid, nodes):
        existing = {n["id"]: n for n in self.list_nodes(uid, tid)}
        seq = max((n.get("_seq", 0) for n in existing.values()), default=0)
        for n in nodes:
            if n["id"] in existing:
                n["_seq"] = existing[n["id"]]["_seq"]     # keep narrative order
            else:
                seq += 1
                n["_seq"] = seq
            self._write(self._p(uid, "timelines", tid, "nodes", f"{n['id']}.json"), n)

    def delete_nodes(self, uid, tid, node_ids):
        for nid in node_ids:
            p = self._p(uid, "timelines", tid, "nodes", f"{nid}.json", mkdir=False)
            if p.exists():
                p.unlink()

    def get_connections(self, uid, tid):
        return self._read(self._p(uid, "timelines", tid, "connections.json")) or []

    def put_connections(self, uid, tid, connections):
        self._write(self._p(uid, "timelines", tid, "connections.json"), connections)

    # ── artifacts / shares ───────────────────────────────────────────────────
    def put_artifact(self, uid, tid, name, content):
        p = self._p(uid, "timelines", tid, "artifacts", name)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def get_artifact(self, uid, tid, name):
        p = self._p(uid, "timelines", tid, "artifacts", name, mkdir=False)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def get_share(self, tid):
        return self._read(self._p("_shares", f"{tid}.json"))

    def put_share(self, tid, doc):
        self._write(self._p("_shares", f"{tid}.json"), doc)
