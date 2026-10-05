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


def _jdump(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _shown(obj):
    """The object's sections a page carries, by own index (subtree.prepare
    gives a tree section a slot, so it shows even with no words of its own)."""
    return [j for j, s in enumerate(obj.sections) if s.t or s.tree]


def order_sig(obj) -> str:
    """The signature the page computes (MANUAL_JS ownPairs) for an object's
    own sections as built: [[heading, text], …] of those it shows."""
    from .build.manual_edit import jhash
    return jhash(_jdump([[obj.sections[j].h or "", obj.sections[j].t or ""] for j in _shown(obj)]))


def tree_list(sec):
    """A sanitized tree section's steps as the page carries them."""
    from .build.subtree import _compact
    return _compact(sec.tree)["n"] if sec.tree and sec.tree.get("nodes") else None


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
    if kind in ("n", "c", "env", "theme") and len(p) == 3:
        ok = {"n": ("title", "tag", "desc"), "c": ("name", "role"),
              "env": ("name", "role"), "theme": ("name", "role")}[kind]
        o = _owner(kind, p[1], brief, by_id)
        if o is None:
            return None
        if p[2] == "order":
            return o, "sections", "order"
        return (o, p[2], "plain") if p[2] in ok else None
    if kind in ("n", "c", "env", "theme") and len(p) == 5 and p[2] == "s":
        if p[3].startswith("new-") and p[4] in ("h", "t"):
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
    if kind == "p" and len(p) == 3 and p[2] == "shift" and p[1] in by_id:
        return brief.setdefault("placement", {}), p[1], "shift"
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

def fold(store, uid, tid) -> "dict | None":
    """Write the page's edits into the draft. Returns a report, or None when
    there is nothing to fold."""
    from .build.manual_edit import jhash
    from .build.sanitize import plain_text
    from .build.brief import BriefError
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
    written, already, conflicts, missing = [], [], [], []
    touched = {"nodes": set(), "brief": False, "conns": False}

    def touch(key):
        p = key.split("|")
        m = DT_KEY.match(p[1]) if p[0] == "dt" else None
        if p[0] == "n":
            touched["nodes"].add(p[1])
        elif m and m.group(1) == "n":
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

    # 2. single fields, oldest first (sections by their original place)
    for k in by_time([k for k in live if kinds[k] not in ("tree", "order", "newsec")]):
        o = live[k]
        t = _target(k, brief, by_id, conns)
        if t is None:
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
        elif kind == "shift":
            cur = (holder.get(f) or {}).get("shift")
            if _same(cur, v):
                already.append(k)
                continue
            if not _same(cur, b):
                conflicts.append(k)
                continue
            h = dict(holder.get(f) or {})
            if v and (v[0] or v[1]):
                h["shift"] = [round(float(v[0]), 1), round(float(v[1]), 1)]
            else:
                h.pop("shift", None)
            if h:
                holder[f] = h
            else:
                holder.pop(f, None)
        else:                                  # html, cx, ovhtml
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

    # 3. the order of sections (by their original places), new ones with their words
    for k in by_time([k for k in live if kinds[k] == "order"]):
        p = k.split("|")
        obj = _owner(p[0], p[1], brief, by_id)
        pv = pristine.owner(p[0], p[1])
        shown = _shown(pv)
        v = [str(x) for x in (live[k].get("v") or [])]
        if v == [str(j) for j in shown]:
            already.append(k)
            continue
        if order_sig(pv) != live[k].get("b"):
            conflicts.append(k)
            continue
        secs = obj.setdefault("sections", [])
        hidden = [s for j, s in enumerate(secs) if j not in shown]
        out = []
        for x in v:
            if x.isdigit() and int(x) in shown:
                out.append(secs[int(x)])
            elif x.startswith("new-"):
                hk, tk = f"{p[0]}|{p[1]}|s|{x}|h", f"{p[0]}|{p[1]}|s|{x}|t"
                h = (live.get(hk) or {}).get("v") or ""
                tx = (live.get(tk) or {}).get("v") or ""
                written.extend(nk for nk in (hk, tk) if nk in live)
                if tx.strip():
                    out.append({"h": plain_text(h), "t": page_to_source(tx)})
        obj["sections"] = out + hidden
        written.append(k)
        touch(k)
    # words of a new section whose place was never recorded have nowhere to go
    missing += [k for k in live if kinds[k] == "newsec" and k not in written]

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
        store.put_nodes(uid, tid, [by_id[i] for i in touched["nodes"] if i in by_id])
    if touched["brief"]:
        doc["brief"] = brief
        store.put_timeline(uid, tid, doc)
    if touched["conns"]:
        store.put_connections(uid, tid, conns)
    _mark(store, uid, tid, {k: live[k].get("t") for k in written + already})
    return {"folded": len(written), "already_in_draft": len(already),
            "conflicts": conflicts, "gone": missing,
            "note": ("The owner's manual edits from the page are now in the draft"
                     + (" — rebuild and publish to put them in the page itself."
                        if written else ".")
                     + (" Conflicts: those fields were changed in the draft after the "
                        "page edit was made, so the draft's version was kept — tell "
                        "the user which, in plain words." if conflicts else ""))}


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
    n = 0
    for k in live:
        o = ops[k]
        done = bool(o.get("f"))
        if not done:
            t = _target(k, copy.deepcopy(doc.get("brief") or {}), by_id, conns)
            if t is None:
                done = True                    # its field is gone
            elif t[2] in ("plain", "para"):
                done = plain_text(t[0].get(t[1]) or "") == (o.get("v") or "")
            elif t[2] == "shift":
                done = _same((t[0].get(t[1]) or {}).get("shift"), o.get("v"))
        if done:
            ops[k] = {"t": o.get("t") or int(time.time() * 1000), "done": True}
            n += 1
    if n:
        store.put_edits(uid, tid, {"v": 1, "ops": ops})
    return n
