"""Folding the owner's manual edits (alto/build/manual_edit.py) into the draft.

The page keeps each edit as {b: what the field showed, v: what it shows now,
t: when} under a field key, in users/{uid}/edits/{tid}. Values are the PAGE's
form of the field — plain text for titles and headings, the cleaned markup the
page renders for a section's text. The draft keeps the AUTHORED form, so the
two are compared through the same cleaning the build does (sanitize), and
markup is turned back into authored markup (page_to_source) before it is
stored — so that building it again gives the page's text.

Structural edits — the order of an object's sections (with new ones, by
`new-…` keys), a decision tree's whole step list — and the authored Overview
carry, as `b`, a signature (manual_edit.jhash) of what they were made against;
they are written only into a draft that still matches it.

  fold(store, uid, tid)          write every edit whose `b` still matches the
                                 draft into it; an edit the draft already holds
                                 is left alone; one whose field has changed
                                 since (Claude edited it too) is a conflict and
                                 is reported, never written. Folded edits are
                                 marked `f` in the edits document.
  published(store, uid, tid)     after a publish: every folded edit is marked
                                 done, so pages stop laying it over themselves.
"""
from __future__ import annotations

import copy
import html as _html
import json
import re
import time
from html.parser import HTMLParser

DT_KEY = re.compile(r"^(n|c|a[01]|x[01])-(.+?)(?:-(\d+))?$")
# What the page makes: a card (`nn|card-…`), a tree in a section it added
# (`dt|<owner>-new-…|tree`), a link to a file on the owner's computer.
NEW_CARD = re.compile(r"^card-[a-z0-9]{4,12}$")
NEW_UNIT = re.compile(r"^unit-[a-z0-9]{4,12}$")
CHIP_ATTR = {"chars": "entity_ids", "envs": "axis1_values", "themes": "axis2_values"}
NEW_TREE = re.compile(r"^(n|c|a0|a1)-(.+)-(new-[a-z0-9]+)$")
FILE_ID = re.compile(r"^file-[a-z0-9]{6,12}$")
PROV_KEYS = ("quoted", "notes", "summary")
_OWNER = {"n": "n", "c": "c", "a0": "env", "a1": "theme"}
_DETAIL = re.compile(r"^\s*showDetail\(\s*'node'\s*,\s*'([a-z0-9][a-z0-9-]{0,47})'\s*\)\s*;?\s*$")


# ── page markup → authored markup ───────────────────────────────────────────

class _Back(HTMLParser):
    """The page's link forms back to the ones an author writes: an alto-link
    span or an Overview chip → <a onclick="showDetail(…)">, a new-tab link → a
    plain <a href>, a source's local-copy icon (which the build adds again) →
    nothing."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        # [tag as written in the page, tag written out | None, (chip: its place in out)]
        self.stack = []

    @staticmethod
    def _attrs(attrs):
        return "".join(f' {k}="{_html.escape(v or "", quote=True)}"' for k, v in attrs)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "span" and "ov-node-link" in cls:
            # the chip's node is on its button, which may come before or after
            # the words: hold a place for the <a> until it is known
            self.out.append(None)
            self.stack.append(["span", None, len(self.out) - 1])
        elif tag == "button":
            m = _DETAIL.match(a.get("onclick") or "")
            chip = next((e for e in reversed(self.stack) if len(e) > 2), None)
            if m and chip is not None and chip[1] is None:
                self.out[chip[2]] = f"<a href=\"#\" onclick=\"showDetail('node','{m.group(1)}')\">"
                chip[1] = "a"
            self.stack.append(["button", None])
        elif tag == "span" and "alto-link" in cls and a.get("data-sd-type") and a.get("data-sd-id"):
            self.out.append(f"<a href=\"#\" onclick=\"showDetail('{a['data-sd-type']}',"
                            f"'{a['data-sd-id']}')\">")
            self.stack.append(["span", "a"])
        elif tag == "a" and "alto-src-local" in cls:
            self.stack.append(["a", None])
        elif tag == "a":
            href = a.get("href") or ""
            if href == "#" and a.get("data-src"):
                href = "src:" + a["data-src"]
            if FILE_ID.match(a.get("data-file") or ""):
                href = "src:" + a["data-file"]
            keep = [("href", href)] + ([("title", a["title"])] if a.get("title") else [])
            self.out.append(f"<a{self._attrs(keep)}>")
            self.stack.append(["a", "a"])
        elif tag in ("br", "hr"):
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
        else:
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
            self.stack.append([tag, tag])

    def handle_startendtag(self, tag, attrs):
        if tag == "button" or (tag == "a" and "alto-src-local" in (dict(attrs).get("class") or "")):
            return
        self.out.append(f"<{tag}{self._attrs(attrs)}/>")

    def handle_endtag(self, tag):
        idx = next((i for i in range(len(self.stack) - 1, -1, -1)
                    if self.stack[i][0] == tag), None)
        if idx is None:
            return
        for e in reversed(self.stack[idx:]):
            if e[1]:
                self.out.append(f"</{e[1]}>")
        del self.stack[idx:]

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == "button":
            return
        self.out.append(_html.escape(data, quote=False))

    def result(self):
        for e in reversed(self.stack):
            if e[1]:
                self.out.append(f"</{e[1]}>")
        self.stack = []
        return "".join(x for x in self.out if x is not None)


def page_to_source(markup: str) -> str:
    """See _Back. Building page_to_source(x) again gives x back for any x the
    build made (detail text, a connection's reason, the Overview)."""
    p = _Back()
    p.feed(markup or "")
    p.close()
    return p.result()


class _Files(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and FILE_ID.match(a.get("data-file") or ""):
            def num(x):
                return int(x) if x and str(x).isdigit() else None
            self.out.setdefault(a["data-file"], {
                "id": a["data-file"], "name": (a.get("data-file-name") or "").strip(),
                "size": num(a.get("data-file-size")), "mod": num(a.get("data-file-mod"))})


def files_in(markup) -> list:
    """The files on the owner's computer a page value links to (MANUAL_JS
    linkFile): [{id, name, size, mod}]."""
    p = _Files()
    p.feed(markup or "")
    p.close()
    return list(p.out.values())


# Where a linked file is looked for: the page knows its name, size and date,
# never its path (a browser does not tell a page where a file is).
FILE_ROOTS = ("Downloads", "Desktop", "Documents")
_FILE_DEPTH = 6
_FILE_SCAN_LIMIT = 80000


def find_file(name: str, size=None, mod=None, home=None) -> "str | None":
    """The file the owner linked: one called `name` under Downloads, Desktop
    or Documents — of that size when there are several, then the one whose
    date is nearest the one the page saw. None when there is none."""
    import os
    from pathlib import Path
    if not name or "/" in name or "\\" in name:
        return None
    base0, want, hits, seen = Path(home) if home else Path.home(), name.casefold(), [], 0
    for r in FILE_ROOTS:
        base = base0 / r
        if not base.is_dir():
            continue
        for d, dirs, files in os.walk(base):
            depth = len(Path(d).relative_to(base).parts)
            dirs[:] = [x for x in dirs if not x.startswith(".") and depth < _FILE_DEPTH]
            seen += len(dirs) + len(files)
            hits += [os.path.join(d, f) for f in files if f.casefold() == want]
            if seen > _FILE_SCAN_LIMIT:
                break
    hits = [h for h in dict.fromkeys(hits) if os.path.isfile(h)]
    if size is not None and len(hits) > 1:
        same = [h for h in hits if os.path.getsize(h) == size]
        hits = same or hits
    if not hits:
        return None
    if mod:
        hits.sort(key=lambda h: abs(os.path.getmtime(h) * 1000 - mod))
    else:
        hits.sort(key=lambda h: -os.path.getmtime(h))
    return hits[0]


# ── a draft as the page sees it ─────────────────────────────────────────────

class _View:
    """The draft's page form: brief, nodes and connections through the
    build's own cleaning, and the link tables that cleaning used."""

    def __init__(self, doc, nodes, conns):
        from .build.builder import load_brief, stored_brief
        from .build.sanitize import sanitize_brief, sanitize_connections
        self.b, self.ns, _ = load_brief({"brief": copy.deepcopy(stored_brief(doc)),
                                         "nodes": copy.deepcopy(nodes)})
        sanitize_brief(self.b, self.ns)
        self.conns, _ = sanitize_connections(self.b, self.ns, copy.deepcopy(conns))
        self.link_types = {}
        for slot, ax in zip(("env", "theme"), self.b.axes[:2]):
            self.link_types.update({v.id: slot for v in ax.values})
        self.link_types.update({e.id: "char" for e in self.b.entities})
        self.link_types.update({n.id: "node" for n in self.ns})
        self.node_ids = {n.id for n in self.ns}

    def sources(self):
        from .build.sanitize import SourceMap
        return SourceMap(self.b.source_docs)

    def owner(self, kind, oid):
        if kind == "n":
            return next((n for n in self.ns if n.id == oid), None)
        if kind == "c":
            return next((e for e in self.b.entities if e.id == oid), None)
        j = {"env": 0, "theme": 1}.get(kind)
        if j is None or j >= len(self.b.axes):
            return None
        return next((v for v in self.b.axes[j].values if v.id == oid), None)

    def norm(self, x):
        from .build.sanitize import clean_linked_markup
        out, _ = clean_linked_markup(page_to_source(x or ""), self.link_types, self.sources())
        return out.replace("&nbsp;", "\xa0")

    def norm_ov(self, x):
        from .build.sanitize import clean_overview
        out, _ = clean_overview(page_to_source(x or ""), self.node_ids, self.sources())
        return out.replace("&nbsp;", "\xa0")


_LINK_OK = re.compile(r"^https?://[^\s<>\"']{3,2000}$")


def _authority_fields(v) -> dict:
    """What a case / statute / Restatement section made on the page carries
    beyond its name: its citation (cite.note, the page's "Citation" section and
    the index row's tail), its note under the heading the axis's other entries
    use, a link, and the list (group) it sits in. The words are the owner's;
    nothing is added to them."""
    from .build.sanitize import plain_text
    out: dict = {}
    cite = plain_text(v.get("cite") or "").strip()[:300]
    if cite:
        out["cite"] = {"note": cite, "short": cite}
    secs = []
    note = plain_text(v.get("t") or "").strip()[:5000]
    if note:
        secs.append({"h": plain_text(v.get("h") or "").strip()[:300] or "Notes",
                     "t": _html.escape(note, quote=False)})
    link = str(v.get("link") or "").strip()
    if _LINK_OK.match(link):
        secs.append({"h": "Link", "t": f'<a href="{_html.escape(link, quote=True)}">'
                                       f'{_html.escape(link, quote=False)}</a>'})
    if secs:
        out["sections"] = secs
    grp = plain_text(v.get("grp") or "").strip()[:300]
    if grp:
        out["group"] = grp
    return out


def _jdump(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _shown(obj):
    """The object's sections a page carries, by own index (subtree.prepare
    gives a tree section a slot, so it shows even with no words of its own)."""
    return [j for j, s in enumerate(obj.sections) if s.t or s.tree or s.cards or s.quiz]


def order_sig(obj) -> str:
    """The signature the page computes (MANUAL_JS ownPairs) for an object's
    own sections as built: [[heading, text], …] of those it shows."""
    from .build.manual_edit import jhash
    return jhash(_jdump([[obj.sections[j].h or "", obj.sections[j].t or ""] for j in _shown(obj)]))


def tree_list(sec):
    """A sanitized tree section's steps as the page carries them."""
    from .build.subtree import _compact
    return _compact(sec.tree)["n"] if sec.tree and sec.tree.get("nodes") else None


def study_list(sec):
    """A sanitized flash-card / quiz section as the page carries it (study.compact)."""
    from .build.study import compact
    return compact(sec)


# ── where each key lives in a stored draft ──────────────────────────────────

def _owner(kind, oid, brief, by_id):
    if kind == "n":
        return by_id.get(oid)
    if kind == "c":
        return next((e for e in brief.get("entities") or [] if e.get("id") == oid), None)
    ax = brief.get("axes") or []
    j = {"env": 0, "theme": 1}.get(kind)
    if j is None or j >= len(ax):
        return None
    return next((v for v in ax[j].get("values") or [] if v.get("id") == oid), None)


def _dt_section(key, brief, by_id):
    """(stored section dict, owner kind, owner id, section index) of a tree key."""
    m = DT_KEY.match(key)
    if not m or m.group(3) is None:
        return None
    pre, oid, si = m.group(1), m.group(2), int(m.group(3))
    kind = {"n": "n", "c": "c", "a0": "env", "a1": "theme"}.get(pre)
    if kind is None:
        return None
    o = _owner(kind, oid, brief, by_id)
    secs = (o or {}).get("sections") or []
    return (secs[si], kind, oid, si) if si < len(secs) else None


def _target(key, brief, by_id, conns):
    """(holder, field, kind) for a key, or None. kinds: plain, para, html, cx,
    ovhtml, shift, order, tree, newsec."""
    p = key.split("|")
    kind = p[0]
    if kind == "nn" and len(p) == 2 and NEW_CARD.match(p[1]):
        return None, None, "newnode"
    if kind == "nu" and len(p) == 2 and NEW_UNIT.match(p[1]):
        return None, None, "newunit"
    if kind == "nl" and len(p) == 2 and NEW_UNIT.match(p[1]):
        return None, None, "unitname"
    if kind == "ne" and len(p) == 3 and p[1] in ("c", "env", "theme"):
        return None, None, "newchip"
    if kind == "rp" and len(p) == 2:
        return (by_id[p[1]], "parent", "reparent") if p[1] in by_id else None
    if kind == "ua" and len(p) == 2:
        return (by_id[p[1]], "act", "unitmove") if p[1] in by_id else None
    if kind == "so" and len(p) == 2:
        return (by_id[p[1]], None, "kidorder") if p[1] in by_id else None
    if kind == "sx" and len(p) == 2:
        return (by_id[p[1]], "parent", "parentswap") if p[1] in by_id else None
    if kind == "ud" and len(p) == 2 and p[1].isdigit():
        return None, None, "unitdel"
    if kind in ("na", "xa") and len(p) == 2 and p[1] in ("axis1", "axis2"):
        return None, None, "newaxis" if kind == "na" else "axisdel"
    if kind == "sz" and len(p) == 2:
        return (None, None, "cardsize") if p[1] in by_id or NEW_CARD.match(p[1]) else None
    if kind == "xe" and len(p) == 3 and p[1] in ("c", "env", "theme"):
        return None, None, "chipdel"
    if kind == "ch" and len(p) == 3 and p[2] in CHIP_ATTR:
        if p[1] in by_id:
            return by_id[p[1]], CHIP_ATTR[p[2]], "list"
        return (None, None, "pending") if NEW_CARD.match(p[1]) else None
    if kind == "ln" and len(p) == 2 and re.match(r"^[a-z0-9][a-z0-9_-]{0,40}$", p[1]) and p[1] != "main":
        return brief, p[1], "lane"
    if kind == "nd" and len(p) == 2:
        return (by_id[p[1]], None, "delnode") if p[1] in by_id else None
    if key == "fl|list":
        return brief, "flags", "flags"
    if key == "fx|off":
        return brief, "filters_off", "list"
    if kind == "fn" and len(p) == 2:
        if p[1] in by_id:
            return by_id[p[1]], "flags", "list"
        return (None, None, "pending") if NEW_CARD.match(p[1]) else None
    if kind == "sd" and len(p) == 3 and p[2] == "study":
        m = NEW_TREE.match(p[1])
        if m:
            return (None, None, "newstudy") if _owner(_OWNER[m.group(1)], m.group(2), brief, by_id) is not None else None
        t = _dt_section(p[1], brief, by_id)
        return (t[0], "study", "study") if t and (t[0].get("cards") or t[0].get("quiz")) else None
    if kind == "dt" and len(p) in (3, 4) and NEW_TREE.match(p[1]):
        m = NEW_TREE.match(p[1])
        if _owner(_OWNER[m.group(1)], m.group(2), brief, by_id) is None:
            return None
        return None, None, "newtree" if len(p) == 3 and p[2] == "tree" else "newtreef"
    if kind in ("n", "c", "env", "theme") and len(p) == 3:
        ok = {"n": ("title", "tag", "desc", "when", "line"), "c": ("name", "role"),
              "env": ("name", "role"), "theme": ("name", "role")}[kind]
        o = _owner(kind, p[1], brief, by_id)
        if o is None:
            return None
        if p[2] == "order":
            return o, "sections", "order"
        return (o, p[2], "plain") if p[2] in ok else None
    if kind in ("n", "c", "env", "theme") and len(p) == 5 and p[2] == "s":
        if p[3].startswith("new-") and p[4] in ("h", "t", "p"):
            return (None, None, "newsec") if _owner(kind, p[1], brief, by_id) is not None else None
        if not p[3].isdigit() or p[4] not in ("h", "t"):
            return None
        o = _owner(kind, p[1], brief, by_id)
        secs = (o or {}).get("sections") or []
        i = int(p[3])
        if i >= len(secs):
            return None
        return secs[i], p[4], "plain" if p[4] == "h" else "html"
    if kind == "u" and len(p) == 3 and p[1].isdigit() and p[2] in ("label", "summary", "short"):
        acts = brief.get("acts") or []
        i = int(p[1])
        if i >= len(acts):
            return None
        return acts[i], p[2], "para" if p[2] == "summary" else "plain"
    if key == "ov|html":
        return brief, "overview_html", "ovhtml"
    if key == "bt|title":
        return brief, "title", "plain"
    if kind == "dt" and len(p) == 3 and p[2] == "tree":
        t = _dt_section(p[1], brief, by_id)
        return (t[0], "tree", "tree") if t and (t[0].get("tree") or {}).get("nodes") else None
    if kind == "dt" and len(p) == 4 and p[3] in ("title", "text", "edge", "tag"):
        t = _dt_section(p[1], brief, by_id)
        if not t:
            return None
        steps = ((t[0].get("tree") or {}).get("nodes")) or []
        st = next((s for s in steps if s.get("id") == p[2]), None)
        return (st, p[3], "plain") if st is not None else None
    if kind == "p" and len(p) == 3 and p[2] in ("shift", "slide") and p[1] in by_id:
        return brief.setdefault("placement", {}), p[1], p[2]
    if kind == "cx" and len(p) == 4 and p[3].isdigit():
        j, n = int(p[3]), 0
        for c in conns:
            if len(c) >= 3 and c[0] == p[1] and c[1] == p[2]:
                if n == j:
                    return c, 3, "cx"
                n += 1
        return None
    return None


def _view_value(key, kind, view):
    """What the page built from this draft shows for a markup key."""
    p = key.split("|")
    if kind == "html":
        return view.owner(p[0], p[1]).sections[int(p[3])].t
    if kind == "cx":
        j, n = int(p[3]), 0
        for c in view.conns:
            if len(c) >= 3 and c[0] == p[1] and c[1] == p[2]:
                if n == j:
                    return c[3] if len(c) > 3 else ""
                n += 1
        return ""
    return view.b.overview_html or ""                # ovhtml


def _same(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        try:
            return len(a) == len(b) and all(float(x) == float(y) for x, y in zip(a, b))
        except (TypeError, ValueError):
            return a == b
    return a == b


def _tree_from_list(v, old):
    """A tree's page step list → stored steps (keeping what the page list does
    not carry: the tree's own settings, a step section's provenance)."""
    steps_old = {s.get("id"): s for s in (old.get("nodes") or [])}
    out = []
    for c in v or []:
        n = {"id": c["i"], "title": c.get("t") or ""}
        if c.get("p"):
            n["parent"] = c["p"]
        for src, dst in (("x", "text"), ("g", "tag"), ("e", "edge"), ("c", "tone")):
            if c.get(src):
                n[dst] = c[src]
        if c.get("l"):
            n["link"] = c["l"][-1] if isinstance(c["l"], list) else c["l"]
        if c.get("s"):
            was = (steps_old.get(c["i"]) or {}).get("sections") or []
            secs = []
            for k, s in enumerate(c["s"]):
                d = {"h": s.get("h") or "", "t": page_to_source(s.get("t") or "")}
                if k < len(was) and was[k].get("prov"):
                    d["prov"] = was[k]["prov"]
                secs.append(d)
            n["sections"] = secs
        out.append(n)
    tree = {k: v2 for k, v2 in old.items() if k != "nodes"}
    tree["nodes"] = out
    return tree


# ── fold ────────────────────────────────────────────────────────────────────

def _flag_list(v) -> list:
    """A filters' list as the page keeps it: [{id, name, color?}]."""
    out = []
    for f in v or []:
        if isinstance(f, dict) and f.get("id"):
            d = {"id": f["id"], "name": f.get("name") or f["id"]}
            if f.get("color"):
                d["color"] = f["color"]
            out.append(d)
    return out


def kids_in_order(nodes, brief, pid) -> list:
    """A card's children as the build orders them: the material's order,
    except a child with a placement `order` n sits n-th (layout._siblings_in_order)."""
    from .build.layout import _siblings_in_order

    class _N:
        def __init__(self, i):
            self.id = i
    ks = [_N(n["id"]) for n in nodes if (n.get("parent") or "") == pid]
    return [k.id for k in _siblings_in_order(ks, brief.get("placement") or {})]


def in_order(have: list, want: list) -> list:
    """`have` with the cards `want` names in want's order, in the turns they
    hold now; the rest keep theirs (one swapped in since keeps the turn of
    the one it replaced). MANUAL_JS orderOne is the same."""
    q = [x for x in want if x in have]
    return [q.pop(0) if x in want else x for x in have]


def fold(store, uid, tid) -> "dict | None":
    """Write the page's edits into the draft. Returns a report, or None when
    there is nothing to fold."""
    from .build.manual_edit import jhash
    from .build.sanitize import plain_text
    from .build.brief import BriefError
    from .build.builder import consent_source_docs
    from .build.brief import ID_RE
    data = store.get_edits(uid, tid)
    ops = (data or {}).get("ops") or {}
    live = {k: o for k, o in ops.items() if isinstance(o, dict) and not o.get("done")}
    if not live:
        return None
    # Copies: a store may hand back the objects it caches for the rest of the
    # call, and nothing here may change those except through put_*.
    doc = copy.deepcopy(store.get_timeline(uid, tid))
    if not doc:
        return None
    nodes = [copy.deepcopy({k: v for k, v in n.items() if not k.startswith("_")})
             for n in store.list_nodes(uid, tid)]
    conns = copy.deepcopy(store.get_connections(uid, tid) or [])
    by_id = {n["id"]: n for n in nodes}
    brief = doc["brief"]
    written, already, conflicts, missing, no_file = [], [], [], [], []
    touched = {"nodes": set(), "brief": False, "conns": False}
    created, removed, units_made, moved, chips_made, reordered = [], [], [], [], [], []
    units_gone, to_unit, chips_gone, axes_made, axes_gone, sized = [], [], [], [], [], []

    def touch(key):
        p = key.split("|")
        m = DT_KEY.match(p[1]) if p[0] in ("dt", "sd") else None
        mn = NEW_TREE.match(p[1]) if p[0] in ("dt", "sd") else None
        if p[0] in ("n", "fn", "ch"):
            touched["nodes"].add(p[1])
        elif mn and mn.group(1) == "n":
            touched["nodes"].add(mn.group(2))
        elif m and m.group(1) == "n" and not mn:
            touched["nodes"].add(m.group(2))
        elif p[0] == "cx":
            touched["conns"] = True
        else:
            touched["brief"] = True

    def by_time(keys):
        return sorted(keys, key=lambda k: live[k].get("t") or 0)

    # Structural edits are checked against the draft as it was before anything
    # here changed it: that is what the page was built from.
    pristine = _View(doc, nodes, conns)

    def known_sources():
        have = {d.get("id") for d in brief.get("source_docs") or consent_source_docs(doc)
                if isinstance(d, dict)}
        return have | {f.get("id") for f in brief.get("linked_files") or [] if isinstance(f, dict)}

    def files_ok(v) -> bool:
        """Every file the value links to is known, or found on this computer
        and added to linked_files. False: one could not be found (the edit
        waits, still shown on the page that made it)."""
        need = [f for f in files_in(v) if f["id"] not in known_sources()]
        found = []
        for f in need:
            path = find_file(f["name"], f["size"], f["mod"])
            if not path:
                no_file.append(f["name"] or f["id"])
                return False
            found.append({"id": f["id"], "name": (f["name"] or f["id"])[:200], "local": path})
        if found:
            brief["linked_files"] = list(brief.get("linked_files") or []) + found
            touched["brief"] = True
        return True

    # 0. a category of chips made on the page (an axis, empty until chips join it)
    for k in sorted([k for k in live if k.startswith("na|")]):
        j = 0 if k.endswith("axis1") else 1
        v = live[k].get("v")
        ax = brief.setdefault("axes", [])
        if not v:
            already.append(k)
            continue
        if len(ax) > j and plain_text(ax[j].get("label") or "") == plain_text(v.get("l") or ""):
            already.append(k)
            continue
        if len(ax) != j:
            conflicts.append(k)
            continue
        label = plain_text(v.get("l") or "") or "Chips"
        ax.append({"label": label, "singular": plain_text(v.get("one") or "") or label, "values": []})
        axes_made.append(label)
        touched["brief"] = True
        written.append(k)

    # 0a. chips made on the page: an entity, or a value of an axis
    for k in by_time([k for k in live if k.startswith("ne|")]):
        _, rk, cid = k.split("|")
        v = live[k].get("v")
        if rk == "c":
            holder = brief.setdefault("entities", [])
        else:
            ax = brief.get("axes") or []
            j = {"env": 0, "theme": 1}[rk]
            if j >= len(ax):
                missing.append(k)
                continue
            holder = ax[j].setdefault("values", [])
        have = next((e for e in holder if e.get("id") == cid), None)
        if not v:
            already.append(k)           # taken out again: cards that carry it drop it below
            continue
        if have is not None:
            already.append(k)
            continue
        taken = ({e.get("id") for e in brief.get("entities") or []}
                 | {x.get("id") for a_ in brief.get("axes") or [] for x in a_.get("values") or []})
        if cid in taken or not ID_RE.match(cid) or (rk == "c" and len(holder) >= 12):
            conflicts.append(k)
            continue
        e = {"id": cid, "name": plain_text(v.get("name") or "") or cid}
        if re.fullmatch(r"#[0-9a-fA-F]{6}", v.get("color") or ""):
            e["color"] = v["color"]
        from .build.glyphs import from_library
        if from_library(v.get("svg")):           # one of the library's, never page markup
            e["symbol_svg"] = v["svg"]
        if rk != "c":
            e.update(_authority_fields(v))
        holder.append(e)
        touched["brief"] = True
        written.append(k)
        chips_made.append(e["name"])

    # 0b. units added on the page, in the order they were made, with their names
    units = {}
    nus = [k for k in live if k.startswith("nu|") and NEW_UNIT.match(k.split("|")[1])]
    for k in sorted(nus, key=lambda k: ((live[k].get("v") or {}).get("n") or 0, k)):
        uid_, v = k.split("|")[1], live[k].get("v")
        acts = brief.setdefault("acts", [])
        at = next((i for i, a in enumerate(acts) if a.get("id") == uid_), None)
        if at is not None:
            units[uid_] = at
            already.append(k)
            continue
        if not v:
            already.append(k)
            continue
        nl = live.get(f"nl|{uid_}") or {}
        label = plain_text(nl.get("v") or v.get("l") or "") or "New unit"
        a = {"label": label, "short": label, "id": uid_}
        if re.fullmatch(r"#[0-9a-fA-F]{6}", v.get("color") or v.get("c") or ""):
            a["color"] = v.get("color") or v.get("c")
        acts.append(a)
        units_made.append(label)
        units[uid_] = len(acts) - 1
        touched["brief"] = True
        written.append(k)
        if nl:
            written.append(f"nl|{uid_}")
    for k in [k for k in live if k.startswith("nl|") and k not in written]:
        uid_ = k.split("|")[1]
        acts = brief.get("acts") or []
        at = next((i for i, a in enumerate(acts) if a.get("id") == uid_), None)
        if at is None:
            missing.append(k)
            continue
        label = plain_text(live[k].get("v") or "")
        if label and acts[at].get("label") != label:
            acts[at]["label"] = acts[at]["short"] = label
            touched["brief"] = True
            written.append(k)
        else:
            already.append(k)

    # 0. new cards, oldest first (a card added under a new card comes after it)
    for k in by_time([k for k in live if k.startswith("nn|")]):
        cid, v = k.split("|")[1], live[k].get("v")
        if not NEW_CARD.match(cid):
            missing.append(k)
            continue
        if not v:
            if cid in by_id:                           # folded before, then taken out
                removed.append(cid)
                written.append(k)
            else:
                already.append(k)
            continue
        if cid in by_id:
            already.append(k)
            continue
        par = v.get("p") or ""
        if par and par not in by_id:
            conflicts.append(k)
            continue
        act = by_id[par]["act"] if par else v.get("a")
        if isinstance(act, str):
            act = units.get(act, next((i for i, a in enumerate(brief.get("acts") or [])
                                       if a.get("id") == act), None))
        if not isinstance(act, int) or not 0 <= act < len(brief.get("acts") or []):
            conflicts.append(k)
            continue
        n = {"id": cid, "act": act, "tag": plain_text(v.get("g") or ""),
             "title": plain_text(v.get("t") or "") or "New card", "desc": plain_text(v.get("d") or "")}
        if par:
            n["parent"] = par
        if v.get("col") and brief.get("mode") != "outline":
            n["col"] = v["col"]
        nodes.append(n)
        by_id[cid] = n
        created.append(cid)
        touched["nodes"].add(cid)
        written.append(k)

    # 0c. cards moved under another card: the card and everything under it
    #     join the new parent's unit, after its last card
    def _on(key):
        return bool((live.get(key) or {}).get("v"))
    for k in by_time([k for k in live if k.startswith("rp|")]):
        cid, v, b = k.split("|")[1], live[k].get("v"), live[k].get("b")
        n = by_id.get(cid)
        if n is None or (v and v not in by_id):
            missing.append(k)
            continue
        if (n.get("parent") or "") == (v or ""):
            already.append(k)
            continue
        if (n.get("parent") or "") != (b or ""):
            conflicts.append(k)
            continue
        going = _on(f"ud|{n['act']}")
        if not v:
            # the top of its unit, in place of its parent — only when that
            # parent was the top card and is being taken out
            par = by_id.get(n.get("parent") or "")
            if not par or par.get("parent") or not _on(f"nd|{par['id']}"):
                conflicts.append(k)
                continue
            n.pop("parent", None)
            pl = brief.get("placement") or {}
            if cid in pl:
                h = {kk: vv for kk, vv in pl[cid].items()
                     if kk not in ("shift", "slide", "x", "dx", "y", "dy", "tier", "float", "order")}
                brief["placement"] = {**pl, cid: h}
                touched["brief"] = True
            touched["nodes"].add(cid)
            written.append(k)
            moved.append({"id": cid, "under": None})
            continue
        # a unit's top card moves only out of a unit being deleted
        if not n.get("parent") and not going:
            conflicts.append(k)
            continue
        kid_of: dict = {}
        for x in nodes:
            if x.get("parent"):
                kid_of.setdefault(x["parent"], []).append(x["id"])
        sub, q = [], [cid]
        while q:
            c = q.pop(0)
            sub.append(c)
            q += kid_of.get(c, [])
        if v in sub or (not going and not any(x["act"] == n["act"] and x["id"] not in sub for x in nodes)):
            conflicts.append(k)
            continue
        n["parent"] = v
        for c in sub:
            by_id[c]["act"] = by_id[v]["act"]
            touched["nodes"].add(c)
        # last among its new siblings, as the page shows it; where it was
        # dragged to, or set by hand, belonged to its old place
        pl = brief.get("placement") or {}
        h = {kk: vv for kk, vv in (pl.get(cid) or {}).items()
             if kk not in ("shift", "slide", "x", "dx", "y", "dy", "tier", "float", "order")}
        h["order"] = len(kid_of.get(v, [])) + 1
        brief["placement"] = {**pl, cid: h}
        touched["brief"] = True
        written.append(k)
        moved.append({"id": cid, "under": v})

    # 0d. a unit's top card (and all under it) or a timeline's card, moved
    #     into another unit — a unit being deleted, its cards kept
    for k in by_time([k for k in live if k.startswith("ua|")]):
        cid, v, b = k.split("|")[1], live[k].get("v"), live[k].get("b")
        n = by_id.get(cid)
        if n is None:
            missing.append(k)
            continue
        acts = brief.get("acts") or []
        t = v if isinstance(v, int) and not isinstance(v, bool) else (
            units.get(v, next((i for i, a in enumerate(acts) if a.get("id") == v), None))
            if isinstance(v, str) else None)
        if not isinstance(t, int) or not 0 <= t < len(acts):
            conflicts.append(k)
            continue
        if n["act"] == t:
            already.append(k)
            continue
        # made against the card's unit as the page had it: its number and name
        if isinstance(b, list) and len(b) == 2:
            at, nm = b
            if (n["act"] != at or at >= len(acts)
                    or _html.unescape(plain_text(acts[at].get("label") or "")).strip()
                    != _html.unescape(plain_text(str(nm or ""))).strip()):
                conflicts.append(k)
                continue
        elif isinstance(b, int) and n["act"] != b:
            conflicts.append(k)
            continue
        if n.get("parent"):
            conflicts.append(k)
            continue
        kid_of = {}
        for x in nodes:
            if x.get("parent"):
                kid_of.setdefault(x["parent"], []).append(x["id"])
        sub, q = [], [cid]
        while q:
            c = q.pop(0)
            sub.append(c)
            q += kid_of.get(c, [])
        for c in sub:
            by_id[c]["act"] = t
            touched["nodes"].add(c)
        pl = brief.get("placement") or {}
        if cid in pl:
            brief["placement"] = {**pl, cid: {kk: vv for kk, vv in pl[cid].items()
                                              if kk not in ("shift", "slide", "x", "dx", "y", "dy", "tier", "float", "order")}}
            touched["brief"] = True
        written.append(k)
        to_unit.append({"id": cid, "unit": t})

    # 0e. a card that traded places with its parent: it takes the parent's
    #     place, the parent and its other children go under it, and its own
    #     children under the parent (each keeping its turn)
    swapped = []

    def _swap(k):
        cid, v, b = k.split("|")[1], live[k].get("v"), live[k].get("b")
        n, pn = by_id.get(cid), by_id.get(v or "")
        if n is None or (v and pn is None):
            return missing.append(k)
        if not v or (pn.get("parent") or "") == cid:
            return already.append(k)
        if (n.get("parent") or "") != v or v != b or n["act"] != pn["act"]:
            return conflicts.append(k)
        g = pn.get("parent") or ""
        sib, mine = kids_in_order(nodes, brief, v), kids_in_order(nodes, brief, cid)
        up = kids_in_order(nodes, brief, g) if g else []
        if g:
            n["parent"] = g
        else:
            n.pop("parent", None)
        pn["parent"] = cid
        for x in sib:
            if x != cid:
                by_id[x]["parent"] = cid
        for x in mine:
            by_id[x]["parent"] = v
        pl = dict(brief.get("placement") or {})
        hc, hp = dict(pl.get(cid) or {}), dict(pl.get(v) or {})
        for kk in ("arrange", "child_w"):                     # how its children are arranged: the place's
            hc.pop(kk, None), hp.pop(kk, None)
            if (pl.get(v) or {}).get(kk) is not None:
                hc[kk] = pl[v][kk]
            if (pl.get(cid) or {}).get(kk) is not None:
                hp[kk] = pl[cid][kk]
        for hh in (hc, hp):
            for kk in ("shift", "slide", "x", "dx", "y", "dy", "tier", "float", "order"):
                hh.pop(kk, None)
        pl[cid], pl[v] = hc, hp
        for lst in ([x if x != v else cid for x in up], [x if x != cid else v for x in sib], mine):
            for j, x in enumerate(lst):
                pl[x] = {**(pl.get(x) or {}), "order": j + 1}
        brief["placement"] = {i: h for i, h in pl.items() if h}
        for x in [cid, v] + sib + mine:
            touched["nodes"].add(x)
        touched["brief"] = True
        written.append(k)
        swapped.append({"id": cid, "with": v})

    # 0f. a card's children in the order set on the page
    def _order(k):
        pid, v, b = k.split("|")[1], live[k].get("v"), live[k].get("b")
        if pid not in by_id or not isinstance(v, list):
            return missing.append(k)
        have = kids_in_order(nodes, brief, pid)
        want = in_order(have, v)
        if want == have:
            return already.append(k)
        if [x for x in (b or []) if x in have] != [x for x in have if x in (b or [])]:
            return conflicts.append(k)
        pl = dict(brief.get("placement") or {})
        for j, x in enumerate(want):
            pl[x] = {**(pl.get(x) or {}), "order": j + 1}
        brief["placement"] = pl
        touched["brief"] = True
        written.append(k)
        reordered.append(pid)

    # in the order they were made: a swap moves what an order named, and the other way round
    for k in by_time([k for k in live if k.startswith(("sx|", "so|"))]):
        (_swap if k.startswith("sx|") else _order)(k)

    kinds = {k: (_target(k, brief, by_id, conns) or (None, None, None))[2] for k in live}

    # 1. whole trees (a step's own words may change after, by step id)
    for k in by_time([k for k in live if kinds[k] == "tree"]):
        sec = _dt_section(k.split("|")[1], brief, by_id)
        pv = pristine.owner(sec[1], sec[2])
        lst = tree_list(pv.sections[sec[3]]) if pv else None
        if lst is not None and _jdump(lst) == _jdump(live[k].get("v")):
            already.append(k)
            continue
        if lst is None or jhash(_jdump(lst)) != live[k].get("b"):
            conflicts.append(k)
            continue
        from .build.subtree import check_tree
        new = _tree_from_list(live[k].get("v"), sec[0].get("tree") or {})
        try:
            check_tree(new, k)
        except BriefError:
            conflicts.append(k)
            continue
        sec[0]["tree"] = new
        written.append(k)
        touch(k)

    # 2. single fields, oldest first (sections by their original place; the
    #    filters' list before which cards are in each)
    # 1b. whole flash-card / quiz lists, the same way
    for k in by_time([k for k in live if kinds[k] == "study"]):
        sec = _dt_section(k.split("|")[1], brief, by_id)
        pv = pristine.owner(sec[1], sec[2])
        lst = study_list(pv.sections[sec[3]]) if pv and sec[3] < len(pv.sections) else None
        if lst is not None and _jdump(lst) == _jdump(live[k].get("v")):
            already.append(k)
            continue
        if lst is None or jhash(_jdump(lst)) != live[k].get("b"):
            conflicts.append(k)
            continue
        from .build.study import from_compact
        try:
            which, new = from_compact(live[k].get("v"))
        except BriefError:
            conflicts.append(k)
            continue
        if (which == "cards") != bool(sec[0].get("cards")):
            conflicts.append(k)                  # a quiz cannot become cards: another section
            continue
        sec[0][which] = new
        written.append(k)
        touch(k)

    singles = [k for k in live if kinds[k] not in ("tree", "study", "newstudy", "order", "newsec", "newnode", "delnode",
                                                    "newtree", "newtreef", "newunit", "unitname",
                                                    "newchip", "reparent", "unitmove", "unitdel",
                                                    "newaxis", "axisdel", "chipdel", "cardsize")
               and not k.startswith(("nn|", "nu|", "nl|", "ne|", "rp|", "so|", "sx|", "ua|", "ud|", "na|", "xa|", "xe|", "sz|"))]
    for k in sorted(singles, key=lambda k: (0 if kinds[k] == "flags" else 1, live[k].get("t") or 0)):
        o = live[k]
        t = _target(k, brief, by_id, conns)
        if t is None or t[2] == "pending":
            missing.append(k)
            continue
        holder, f, kind = t
        v, b = o.get("v"), o.get("b")
        if kind in ("plain", "para"):
            cur = plain_text(holder.get(f) or "")
            if cur == (v or ""):
                already.append(k)
                continue
            if cur != (b or ""):
                conflicts.append(k)
                continue
            holder[f] = v or ""
        elif kind in ("flags", "list"):
            norm = _flag_list if kind == "flags" else (lambda x: [str(y) for y in (x or [])])
            cur = norm(holder.get(f))
            if cur == norm(v):
                already.append(k)
                continue
            if cur != norm(b):
                conflicts.append(k)
                continue
            if norm(v):
                holder[f] = norm(v)
            else:
                holder.pop(f, None)
        elif kind == "lane":
            # a line of a horizontal timeline (lanes.py): the whole line, or None to remove it
            from .build.lanes import norm_line
            lines = holder.setdefault("lines", [])
            at = next((j for j, q in enumerate(lines) if q.get("id") == f), None)
            cur = norm_line(lines[at], at) if at is not None else None
            nb = norm_line(dict(b, id=f), 0) if isinstance(b, dict) else None
            nv = norm_line(dict(v, id=f), 0) if isinstance(v, dict) else None
            if _same(cur, nv):
                already.append(k)
                continue
            if not _same(cur, nb):
                conflicts.append(k)
                continue
            if nv is None:
                lines.pop(at)
            else:
                keep = {kk: nv[kk] for kk in ("id", "label", "color", "side", "from", "to") if nv[kk]}
                if at is None:
                    lines.append(keep)
                else:
                    lines[at] = keep
        elif kind in ("shift", "slide"):
            cur = (holder.get(f) or {}).get(kind)
            if _same(cur, v):
                already.append(k)
                continue
            if not _same(cur, b):
                conflicts.append(k)
                continue
            h = dict(holder.get(f) or {})
            if v and (v[0] or v[1]):
                h[kind] = [round(float(v[0]), 1), round(float(v[1]), 1)]
            else:
                h.pop(kind, None)
            if h:
                holder[f] = h
            else:
                holder.pop(f, None)
        else:                                  # html, cx, ovhtml
            if not files_ok(v):
                continue
            view = _View(doc, nodes, conns)
            cur = _view_value(k, kind, view)
            n = view.norm_ov if kind == "ovhtml" else view.norm
            if n(cur) == n(v):
                already.append(k)
                continue
            base_ok = (jhash(cur) == b) if kind == "ovhtml" else (n(cur) == n(b))
            if not base_ok:
                conflicts.append(k)
                continue
            src = page_to_source(v or "")
            if kind == "cx":
                if src:
                    holder[3:] = [src]
                else:
                    del holder[3:]
            else:
                holder[f] = src
        written.append(k)
        touch(k)

    # 3. the order of sections (by their original places), new ones with their
    #    words, their kind and their tree
    for k in by_time([k for k in live if kinds[k] == "order"]):
        p = k.split("|")
        obj = _owner(p[0], p[1], brief, by_id)
        pv = pristine.owner(p[0], p[1])
        # an owner made on the page (a case added there) has its sections only
        # in the draft the fold is writing: they are what the page showed
        fresh = pv is None and obj is not None and p[0] != "n"
        shown = _shown(pv) if pv is not None else (
            [j for j, s_ in enumerate(obj.get("sections") or []) if s_.get("t")] if fresh else [])
        sig = order_sig(pv) if pv is not None else jhash("[]")
        v = [str(x) for x in (live[k].get("v") or [])]
        if v == [str(j) for j in shown]:
            already.append(k)
            continue
        if sig != live[k].get("b") and not fresh:
            conflicts.append(k)
            continue
        secs = obj.setdefault("sections", [])
        hidden = [s_ for j, s_ in enumerate(secs) if j not in shown]
        out, mine, waiting = [], [], False
        for x in v:
            if x.isdigit() and int(x) in shown:
                out.append(secs[int(x)])
            elif x.startswith("new-"):
                hk, tk, pk = (f"{p[0]}|{p[1]}|s|{x}|{f}" for f in ("h", "t", "p"))
                h = (live.get(hk) or {}).get("v") or ""
                tx = (live.get(tk) or {}).get("v") or ""
                if tx and not files_ok(tx):
                    waiting = True
                    break
                d = {"h": plain_text(h), "t": page_to_source(tx)}
                pr = (live.get(pk) or {}).get("v") or ""
                if pr in PROV_KEYS:
                    d["prov"] = pr
                tkey = f"dt|{DTPRE_OF[p[0]]}-{p[1]}-{x}|tree"
                steps = (live.get(tkey) or {}).get("v") or []
                if steps:
                    tree = _tree_from_list(steps, {})
                    for sk in [q for q in live if q.startswith(f"dt|{DTPRE_OF[p[0]]}-{p[1]}-{x}|")
                               and kinds.get(q) == "newtreef"]:
                        _, _, step, fld = sk.split("|")
                        st = next((n_ for n_ in tree["nodes"] if n_["id"] == step), None)
                        if st is not None:
                            val = (live[sk].get("v") or "").strip()
                            if val:
                                st[fld] = plain_text(val)
                            elif fld != "title":
                                st.pop(fld, None)
                            mine.append(sk)
                    from .build.subtree import check_tree
                    try:
                        check_tree(tree, tkey)
                        d["tree"] = tree
                        mine.append(tkey)
                    except BriefError:
                        conflicts.append(tkey)
                skey = f"sd|{DTPRE_OF[p[0]]}-{p[1]}-{x}|study"
                sv = (live.get(skey) or {}).get("v")
                if sv:
                    from .build.study import from_compact
                    try:
                        which, new = from_compact(sv)
                        d[which] = new
                        mine.append(skey)
                    except BriefError:
                        conflicts.append(skey)
                mine.extend(q for q in (hk, tk, pk) if q in live)
                if (d["t"] or "").strip() or d.get("tree") or d.get("cards") or d.get("quiz"):
                    out.append(d)
        if waiting:
            continue
        obj["sections"] = out + hidden
        written.extend(mine)
        written.append(k)
        touch(k)
    # words of a new section whose place was never recorded have nowhere to go
    missing += [k for k in live if kinds[k] in ("newsec", "newtree", "newtreef", "newstudy") and k not in written]

    # 4. cards taken out (nothing under them; their lines go with them)
    for k in by_time([k for k in live if kinds[k] == "delnode"]):
        cid = k.split("|")[1]
        if not live[k].get("v"):
            already.append(k)
            continue
        removed.append(cid)
        written.append(k)
    if removed:
        going = set(removed)
        kept = [c for c in removed if not any(n.get("parent") == c and n["id"] not in going for n in nodes)]
        for c in set(removed) - set(kept):
            conflicts.append(f"nd|{c}")
            written[:] = [w for w in written if w not in (f"nd|{c}", f"nn|{c}")]
        removed = kept
        going = set(removed)
        nodes[:] = [n for n in nodes if n["id"] not in going]
        for c in removed:
            by_id.pop(c, None)
            touched["nodes"].discard(c)
        before = len(conns)
        conns[:] = [c for c in conns if not (len(c) >= 2 and (c[0] in going or c[1] in going))]
        touched["conns"] = touched["conns"] or len(conns) != before
        pl = brief.get("placement") or {}
        if any(c in pl for c in going):
            brief["placement"] = {i: h for i, h in pl.items() if i not in going}
            touched["brief"] = True
        cs = brief.get("card_size") or {}
        if any(c in cs for c in going):
            brief["card_size"] = {i: h for i, h in cs.items() if i not in going}
            touched["brief"] = True
    # 4b. card sizes set on the page (its width; the least height it takes)
    from .build.brief import CARD_SIZE_W, CARD_SIZE_H
    for k in by_time([k for k in live if k.startswith("sz|")]):
        cid, v = k.split("|")[1], live[k].get("v")
        if cid not in by_id:
            missing.append(k)
            continue
        cs = dict(brief.get("card_size") or {})
        new = None
        if isinstance(v, dict):
            new = {}
            for key, (lo, hi) in (("w", CARD_SIZE_W), ("h", CARD_SIZE_H)):
                x = v.get(key)
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    new[key] = round(min(max(x, lo), hi))
            new = new or None
        if cs.get(cid) == new:
            already.append(k)
            continue
        if new:
            cs[cid] = new
        else:
            cs.pop(cid, None)
        brief["card_size"] = cs
        touched["brief"] = True
        written.append(k)
        sized.append(cid)
    # 5. units deleted on the page, once their cards are elsewhere or gone
    #    (last first, so the numbers of the others hold)
    uds = sorted(((int(k.split("|")[1]), k) for k in live
                  if k.startswith("ud|") and k.split("|")[1].isdigit()), reverse=True)
    for i, k in uds:
        if not live[k].get("v"):
            already.append(k)
            continue
        acts = brief.get("acts") or []
        def _nm(x):
            return _html.unescape(plain_text(str(x or ""))).strip()
        if i >= len(acts) or _nm(acts[i].get("label")) != _nm(live[k].get("b")):
            conflicts.append(k)
            continue
        if any(n["act"] == i for n in nodes) or len(acts) <= 2:
            conflicts.append(k)
            continue
        units_gone.append(_nm(acts[i].get("label")))
        del acts[i]
        for n in nodes:
            if n["act"] > i:
                n["act"] -= 1
                touched["nodes"].add(n["id"])
        for m in to_unit:
            if m["unit"] > i:
                m["unit"] -= 1
        touched["brief"] = True
        written.append(k)
    # 6. chips taken out of the timeline (the cards drop them just below)
    for k in by_time([k for k in live if k.startswith("xe|")]):
        _, rk, cid = k.split("|")
        if not live[k].get("v"):
            already.append(k)
            continue
        if rk == "c":
            holder = brief.get("entities") or []
        else:
            ax = brief.get("axes") or []
            j = {"env": 0, "theme": 1}[rk]
            holder = (ax[j].get("values") or []) if j < len(ax) else []
        hit = next((e for e in holder if e.get("id") == cid), None)
        if hit is None:
            already.append(k)
            continue
        holder.remove(hit)
        chips_gone.append(hit.get("name") or cid)
        touched["brief"] = True
        written.append(k)
    # 7. categories taken out: the axis and every card's chips of it; the one
    #    after it (axis2) becomes axis1, its filters with it
    for k in sorted([k for k in live if k.startswith("xa|")], reverse=True):
        j = 0 if k.endswith("axis1") else 1
        ax = brief.get("axes") or []
        if not live[k].get("v"):
            already.append(k)
            continue
        if j >= len(ax) or plain_text(ax[j].get("label") or "") != plain_text(live[k].get("b") or ""):
            conflicts.append(k)
            continue
        axes_gone.append(ax[j].get("label"))
        del ax[j]
        src = f"axis{j + 1}"
        fl = [f for f in brief.get("filters") or [] if not (isinstance(f, dict) and f.get("source") == src)]
        off = [o for o in brief.get("filters_off") or [] if o != src]
        if j == 0:
            for f in fl:
                if isinstance(f, dict) and f.get("source") == "axis2":
                    f["source"] = "axis1"
            off = ["axis1" if o == "axis2" else o for o in off]
        if "filters" in brief:
            brief["filters"] = fl
        if "filters_off" in brief:
            brief["filters_off"] = off
        for n in nodes:
            a1, a2 = n.get("axis1_values"), n.get("axis2_values")
            if j == 0:
                if a1 or a2:
                    n["axis1_values"] = list(a2 or [])
                    n.pop("axis2_values", None)
                    touched["nodes"].add(n["id"])
            elif a2:
                n.pop("axis2_values", None)
                touched["nodes"].add(n["id"])
        touched["brief"] = True
        written.append(k)
    # a card's chips name only chips the timeline has
    have = {"entity_ids": {e.get("id") for e in brief.get("entities") or []}}
    for j, attr in enumerate(("axis1_values", "axis2_values")):
        ax = brief.get("axes") or []
        have[attr] = {x.get("id") for x in (ax[j].get("values") or [])} if j < len(ax) else set()
    for n in nodes:
        for attr, ok in have.items():
            if n.get(attr) and any(x not in ok for x in n[attr]):
                n[attr] = [x for x in n[attr] if x in ok]
                touched["nodes"].add(n["id"])
    # a card's filters name only filters the timeline has
    fids = {f.get("id") for f in brief.get("flags") or [] if isinstance(f, dict)}
    for n in nodes:
        if n.get("flags") and any(f not in fids for f in n["flags"]):
            n["flags"] = [f for f in n["flags"] if f in fids]
            touched["nodes"].add(n["id"])

    if written:
        # the result must still build; if it does not, nothing is written
        from .build.builder import load_brief, stored_brief
        from .build.brief import validate_brief, validate_nodes
        try:
            b2, n2, _ = load_brief({"brief": copy.deepcopy(stored_brief(doc)),
                                    "nodes": copy.deepcopy(nodes)})
            validate_brief(b2)
            validate_nodes(b2, n2)
        except (BriefError, TypeError, ValueError) as e:
            return {"error": "fold_invalid", "message": str(e)[:300],
                    "note": "The page's edits were NOT written: together they would "
                            "not build. Tell the user which edit is the problem."}
    if touched["nodes"]:
        store.put_nodes(uid, tid, [by_id[i] for i in [n["id"] for n in nodes] if i in touched["nodes"]])
    if removed:
        store.delete_nodes(uid, tid, removed)
    if touched["brief"]:
        doc["brief"] = brief
        store.put_timeline(uid, tid, doc)
    if touched["conns"]:
        store.put_connections(uid, tid, conns)
    _mark(store, uid, tid, {k: live[k].get("t") for k in written + already})
    titles = {n["id"]: n.get("title") for n in nodes}
    rep = {"folded": len(written), "already_in_draft": len(already),
           "conflicts": conflicts, "gone": missing,
           "note": ("The owner's manual edits from the page are now in the draft"
                    + (" — rebuild and publish to put them in the page itself."
                       if written else ".")
                    + (" Conflicts: those fields were changed in the draft after the "
                       "page edit was made, so the draft's version was kept — tell "
                       "the user which, in plain words." if conflicts else ""))}
    if created:
        rep["cards_added"] = [{"id": c, "title": titles.get(c)} for c in created]
        rep["note"] += (" The owner added cards on the page (cards_added): they are in "
                        "the draft with what the owner wrote; their place on the page "
                        "is decided by the next build.")
    if units_made:
        rep["units_added"] = units_made
        rep["note"] += (" The owner added units on the page (units_added), each with "
                        "its first card.")
    if moved:
        for m in moved:
            m["title"], m["under_title"] = titles.get(m["id"]), titles.get(m["under"])
        rep["cards_moved"] = moved
        rep["note"] += (" The owner moved cards (and everything under them) under "
                        "other cards (cards_moved).")
    if to_unit:
        acts = brief.get("acts") or []
        rep["cards_moved_to_unit"] = [{"id": m["id"], "title": titles.get(m["id"]),
                                       "unit": (acts[m["unit"]].get("label") if m["unit"] < len(acts) else "")}
                                      for m in to_unit]
        rep["note"] += (" The owner moved cards into another unit (cards_moved_to_unit).")
    if swapped:
        for m in swapped:
            m["title"], m["with_title"] = titles.get(m["id"]), titles.get(m["with"])
        rep["cards_swapped_with_parent"] = swapped
        rep["note"] += (" The owner had cards trade places with the card they sat under "
                        "(cards_swapped_with_parent): the parent and its other children now "
                        "hang under the card, and the card's own children under the parent.")
    if reordered:
        rep["children_reordered"] = [{"id": i, "title": titles.get(i)} for i in reordered]
        rep["note"] += (" The owner put some cards' children in another order "
                        "(children_reordered, placement order) — keep it.")
    if units_gone:
        rep["units_deleted"] = units_gone
        rep["note"] += (" The owner deleted units on the page (units_deleted); their "
                        "cards were moved or deleted first.")
    if sized:
        rep["cards_resized"] = [{"id": c, "title": titles.get(c)} for c in sized]
        rep["note"] += (" The owner set the size of some cards on the page (cards_resized, "
                        "brief.card_size) — keep it.")
    if axes_made:
        rep["categories_added"] = axes_made
        rep["note"] += (" The owner added categories of chips (categories_added): only "
                        "the name, and the chips they made in it.")
    if chips_gone or axes_gone:
        rep["chips_removed"] = chips_gone
        rep["categories_removed"] = axes_gone
        rep["note"] += (" The owner took chips (chips_removed) or whole categories "
                        "(categories_removed) out of the timeline: gone from every card "
                        "and from the top bar, their pages with them.")
    if chips_made:
        rep["chips_added"] = chips_made
        rep["note"] += (" The owner made new chips (chips_added): each has its name and a page of "
                        "its own — for a case, statute or Restatement section, the citation, note "
                        "and link the owner typed, nothing more. Do not add to them.")
    if removed:
        rep["cards_removed"] = removed
        rep["note"] += (" The owner removed cards on the page (cards_removed); they and "
                        "their lines are gone from the draft.")
    if no_file:
        rep["files_not_found"] = sorted(set(no_file))
        rep["note"] += (" Some text links to a file on the owner's computer that is not "
                        "in their Desktop, Documents or Downloads (files_not_found), so "
                        "that text waits on the page that made it — tell the user in one "
                        "line which file, and that moving it into one of those folders "
                        "lets the next build pick it up.")
    return rep


DTPRE_OF = {"n": "n", "c": "c", "env": "a0", "theme": "a1"}


def _mark(store, uid, tid, keys_t: dict) -> None:
    """Mark folded edits `f` in the edits document (read again just before, so
    an edit made meanwhile is kept; one changed since gets no mark)."""
    if not keys_t:
        return
    data = store.get_edits(uid, tid) or {"v": 1, "ops": {}}
    ops = data.setdefault("ops", {})
    n = 0
    for k, t in keys_t.items():
        o = ops.get(k)
        if isinstance(o, dict) and o.get("t") == t and not o.get("done") and not o.get("f"):
            o["f"] = 1
            n += 1
    if n:
        store.put_edits(uid, tid, data)


def published(store, uid, tid) -> int:
    """After a publish: mark done every edit the published draft carries, so
    pages stop laying it over themselves. Folded edits are marked `f`; an edit
    from before marks existed counts when the draft shows its value."""
    from .build.sanitize import plain_text
    data = store.get_edits(uid, tid)
    ops = (data or {}).get("ops") or {}
    live = [k for k, o in ops.items() if isinstance(o, dict) and not o.get("done")]
    if not live:
        return 0
    doc = store.get_timeline(uid, tid) or {"brief": {}}
    nodes = [copy.deepcopy(n) for n in store.list_nodes(uid, tid)]
    by_id = {n["id"]: n for n in nodes}
    conns = store.get_connections(uid, tid) or []
    # A card added on the page that is not in the draft yet: its words are
    # not gone, they are waiting for it.
    waiting = {k.split("|")[1] for k in live if k.startswith("nn|") and not ops[k].get("f")}
    n_unmark = False
    n = 0
    for k in live:
        o = ops[k]
        p = k.split("|")
        if len(p) > 1 and p[1] in waiting and not o.get("f"):
            continue
        # What the draft carries decides, folded or not: an edit marked
        # folded that the draft does not hold (a write lost after the fold)
        # stays on the page, and the next fold writes it again.
        t = _target(k, copy.deepcopy(doc.get("brief") or {}), by_id, conns)
        carried = None
        if len(p) > 2 and p[2] == "s":
            pass                 # by its ORIGINAL place: a reorder moves it, so trust the fold
        elif t is not None and t[2] in ("plain", "para"):
            carried = plain_text(t[0].get(t[1]) or "") == (o.get("v") or "")
        elif t is not None and t[2] in ("shift", "slide"):
            carried = _same((t[0].get(t[1]) or {}).get(t[2]), o.get("v"))
        elif t is not None and t[2] == "parentswap":
            pn = by_id.get(o.get("v") or "")
            carried = bool(pn) and (pn.get("parent") or "") == p[1]
        elif t is not None and t[2] == "kidorder":
            have = kids_in_order(nodes, doc.get("brief") or {}, p[1])
            carried = in_order(have, o.get("v") or []) == have
        elif t is not None and t[2] == "flags":
            carried = _flag_list(t[0].get(t[1])) == _flag_list(o.get("v"))
        elif t is not None and t[2] == "list":
            carried = [str(x) for x in (t[0].get(t[1]) or [])] == [str(x) for x in (o.get("v") or [])]
        if carried is False:
            if o.get("f"):
                ops[k] = {key: val for key, val in o.items() if key != "f"}
                n_unmark = True
            continue
        done = bool(o.get("f")) or carried is True
        if not done:
            if t is None and not (len(p) > 1 and p[1] in waiting):
                done = True                    # its field is gone
        if done:
            ops[k] = {"t": o.get("t") or int(time.time() * 1000), "done": True}
            n += 1
    if n or n_unmark:
        store.put_edits(uid, tid, {"v": 1, "ops": ops})
    return n
