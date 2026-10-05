"""Folding the owner's manual edits (alto/build/manual_edit.py) into the draft.

The page keeps each edit as {b: what the field showed, v: what it shows now,
t: when} under a field key, in users/{uid}/edits/{tid}. Values are the PAGE's
form of the field — plain text for titles and headings, the cleaned markup the
page renders for a section's text. The draft keeps the AUTHORED form, so the
two are compared through the same cleaning the build does (sanitize), and a
section's text is turned back into authored markup (page_to_source) before it
is stored — so that building it again gives exactly the page's text.

  fold(store, uid, tid)          write every edit whose `b` still matches the
                                 draft into it; an edit the draft already holds
                                 is left alone; one whose field has changed
                                 since (Claude edited it too) is a conflict and
                                 is reported, never written.
  published(store, uid, tid)     after a publish: every edit the published draft
                                 now carries is marked done, so pages stop
                                 laying it over themselves.
"""
from __future__ import annotations

import copy
import html as _html
import re
import time
from html.parser import HTMLParser

DT_KEY = re.compile(r"^(n|c|a[01]|x[01])-(.+?)(?:-(\d+))?$")


# ── page markup → authored markup ───────────────────────────────────────────

class _Back(HTMLParser):
    """The page's link forms back to the ones an author writes: an alto-link
    span → <a onclick="showDetail(…)">, a new-tab link → a plain <a href>, a
    source's local-copy icon (which the build adds again) → nothing."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []          # (tag as written in the page, tag written out | None)

    @staticmethod
    def _attrs(attrs):
        return "".join(f' {k}="{_html.escape(v or "", quote=True)}"' for k, v in attrs)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "span" and "alto-link" in cls and a.get("data-sd-type") and a.get("data-sd-id"):
            self.out.append(f"<a href=\"#\" onclick=\"showDetail('{a['data-sd-type']}',"
                            f"'{a['data-sd-id']}')\">")
            self.stack.append(("span", "a"))
        elif tag == "a" and "alto-src-local" in cls:
            self.stack.append(("a", None))
        elif tag == "a":
            href = a.get("href") or ""
            if href == "#" and a.get("data-src"):
                href = "src:" + a["data-src"]
            keep = [("href", href)] + ([("title", a["title"])] if a.get("title") else [])
            self.out.append(f"<a{self._attrs(keep)}>")
            self.stack.append(("a", "a"))
        elif tag in ("br", "hr"):
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
        else:
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
            self.stack.append((tag, tag))

    def handle_startendtag(self, tag, attrs):
        if tag == "a" and "alto-src-local" in (dict(attrs).get("class") or ""):
            return
        self.out.append(f"<{tag}{self._attrs(attrs)}/>")

    def handle_endtag(self, tag):
        idx = next((i for i in range(len(self.stack) - 1, -1, -1)
                    if self.stack[i][0] == tag), None)
        if idx is None:
            return
        for _, out in reversed(self.stack[idx:]):
            if out:
                self.out.append(f"</{out}>")
        del self.stack[idx:]

    def handle_data(self, data):
        self.out.append(_html.escape(data, quote=False))

    def result(self):
        for _, out in reversed(self.stack):
            if out:
                self.out.append(f"</{out}>")
        self.stack = []
        return "".join(self.out)


def page_to_source(markup: str) -> str:
    """See _Back. sanitize(page_to_source(x)) == x for any x sanitize made."""
    p = _Back()
    p.feed(markup or "")
    p.close()
    return p.result()


# ── where each key lives in a stored draft ──────────────────────────────────

def _target(key, brief, nodes_by_id):
    """(holder dict, field, kind) for a key, or None. kind: plain | html | shift."""
    p = key.split("|")
    kind = p[0]

    def owner(k, i):
        if k == "n":
            return nodes_by_id.get(i)
        if k == "c":
            return next((e for e in brief.get("entities") or [] if e.get("id") == i), None)
        ax = (brief.get("axes") or [])
        j = {"env": 0, "theme": 1}.get(k)
        if j is None or j >= len(ax):
            return None
        return next((v for v in ax[j].get("values") or [] if v.get("id") == i), None)

    if kind in ("n", "c", "env", "theme") and len(p) == 3:
        ok = {"n": ("title", "tag", "desc"), "c": ("name", "role"),
              "env": ("name", "role"), "theme": ("name", "role")}[kind]
        o = owner(kind, p[1])
        return (o, p[2], "plain") if o is not None and p[2] in ok else None
    if kind in ("n", "c", "env", "theme") and len(p) == 5 and p[2] == "s" and p[3].isdigit():
        o = owner(kind, p[1])
        secs = (o or {}).get("sections") or []
        i = int(p[3])
        if i >= len(secs) or p[4] not in ("h", "t"):
            return None
        return secs[i], p[4], "plain" if p[4] == "h" else "html"
    if kind == "u" and len(p) == 3 and p[1].isdigit() and p[2] == "label":
        acts = brief.get("acts") or []
        i = int(p[1])
        return (acts[i], "label", "plain") if i < len(acts) else None
    if kind == "dt" and len(p) == 4 and p[3] in ("title", "text", "edge"):
        m = DT_KEY.match(p[1])
        if not m or m.group(3) is None:
            return None
        pre, oid, si = m.group(1), m.group(2), int(m.group(3))
        if pre == "n":
            o = nodes_by_id.get(oid)
            secs = (o or {}).get("sections") or []
        elif pre == "c":
            o = owner("c", oid)
            secs = (o or {}).get("sections") or []
        elif pre in ("a0", "a1"):
            o = owner("env" if pre == "a0" else "theme", oid)
            secs = (o or {}).get("sections") or []
        else:
            return None
        if si >= len(secs):
            return None
        steps = ((secs[si].get("tree") or {}).get("nodes")) or []
        st = next((s for s in steps if s.get("id") == p[2]), None)
        return (st, p[3], "plain") if st is not None else None
    if kind == "p" and len(p) == 3 and p[2] == "shift" and p[1] in nodes_by_id:
        pl = brief.setdefault("placement", {})
        return pl, p[1], "shift"
    return None


def _page_value(key, doc, nodes):
    """What the page built from this draft shows for `key` (its page form)."""
    from .build.builder import load_brief, stored_brief
    from .build.sanitize import sanitize_brief, plain_text
    d = {"brief": copy.deepcopy(stored_brief(doc)), "nodes": copy.deepcopy(nodes)}
    t = _target(key, d["brief"], {n["id"]: n for n in d["nodes"]})
    if t is None:
        return None, False
    holder, f, kind = t
    if kind == "shift":
        return ((holder.get(f) or {}).get("shift")), True
    if kind == "plain":
        return plain_text(holder.get(f) or ""), True
    b, ns, _ = load_brief(d)
    sanitize_brief(b, ns)
    p = key.split("|")
    if p[0] == "n":
        o = next(n for n in ns if n.id == p[1])
    elif p[0] == "c":
        o = next(e for e in b.entities if e.id == p[1])
    else:
        ax = b.axes[0 if p[0] == "env" else 1]
        o = next(v for v in ax.values if v.id == p[1])
    return o.sections[int(p[3])].t, True


def _same(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(float(x) == float(y) for x, y in zip(a, b))
    return a == b


def fold(store, uid, tid) -> "dict | None":
    """Write the page's edits into the draft. Returns a report, or None when
    there is nothing to fold."""
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
    by_id = {n["id"]: n for n in nodes}
    brief = doc["brief"]
    written, already, conflicts, missing = [], [], [], []
    changed_nodes, brief_changed = set(), False
    for key in sorted(live, key=lambda k: live[k].get("t") or 0):
        o = live[key]
        cur, found = _page_value(key, doc, nodes)
        if not found:
            missing.append(key)
            continue
        if _same(cur, o.get("v")):
            already.append(key)
            continue
        if not _same(cur, o.get("b")):
            conflicts.append(key)
            continue
        holder, f, kind = _target(key, brief, by_id)
        v = o.get("v")
        if kind == "shift":
            h = dict(holder.get(f) or {})
            if v and (v[0] or v[1]):
                h["shift"] = [round(float(v[0]), 1), round(float(v[1]), 1)]
            else:
                h.pop("shift", None)
            if h:
                holder[f] = h
            else:
                holder.pop(f, None)
        elif kind == "html":
            holder[f] = page_to_source(v or "")
        else:
            holder[f] = v or ""
        written.append(key)
        if key.split("|")[0] == "n" or (key.startswith("dt|n-")):
            nid = key.split("|")[1] if not key.startswith("dt|") else DT_KEY.match(key.split("|")[1]).group(2)
            changed_nodes.add(nid)
        else:
            brief_changed = True
    if changed_nodes:
        store.put_nodes(uid, tid, [by_id[i] for i in changed_nodes])
    if brief_changed:
        doc["brief"] = brief
        store.put_timeline(uid, tid, doc)
    return {"folded": len(written), "already_in_draft": len(already),
            "conflicts": conflicts, "gone": missing,
            "note": ("The owner's manual edits from the page are now in the draft"
                     + (" — rebuild and publish to put them in the page itself."
                        if written else ".")
                     + (" Conflicts: those fields were changed in the draft after the "
                        "page edit was made, so the draft's version was kept — tell "
                        "the user which, in plain words." if conflicts else ""))}


def published(store, uid, tid) -> int:
    """After a publish: mark done every edit the draft (now the page) carries."""
    data = store.get_edits(uid, tid)
    ops = (data or {}).get("ops") or {}
    live = [k for k, o in ops.items() if isinstance(o, dict) and not o.get("done")]
    if not live:
        return 0
    doc = copy.deepcopy(store.get_timeline(uid, tid))
    nodes = [copy.deepcopy({k: v for k, v in n.items() if not k.startswith("_")})
             for n in store.list_nodes(uid, tid)]
    n = 0
    for k in live:
        cur, found = _page_value(k, doc, nodes)
        if not found or _same(cur, ops[k].get("v")):
            ops[k] = {"t": ops[k].get("t") or int(time.time() * 1000), "done": True}
            n += 1
    if n:
        store.put_edits(uid, tid, {"v": 1, "ops": ops})
    return n
