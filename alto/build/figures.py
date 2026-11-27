"""Key figures: a section the owner names and fills with rows, each a big figure ("21 days", "$75,000", "3 years", "12") over a label, with an
optional detail line, quote and citation. It draws exactly like the Deadlines box on a statute's page (detail_extras.DEADLINES_CSS: the
same .dl-box rows, so Classic, Retro, Holographic, the phone and the ink-saver print all come from that one sheet) but it is a section kind,
so any page can carry one and the owner adds it by hand in edit mode ("Add a section" → Key figures) or Claude writes it with add_nodes.

  Section.figures = {"items": [{id?, figure, label?, detail?, quote?, cite?}, ...]}    one of tree / cards / quiz / photos / figures
  (the section's own heading `h` is the block's name: "Key figures", "Deadlines", anything)

Every word is the owner's (nothing is filled in); the checks are shape and size only — unlike an axis value's `deadlines`, a figure is not
tied to a quote, since a count or an amount ("12 jurors", "$75,000") is not always a time limit.

Build path: brief._check_sections → check_figures; sanitize → sanitize_items; builder → prepare (a hidden .afg-slot at the end of the section's
text holding the words, so search finds them; the data) → block (data + the small drawing script, + DEADLINES_CSS when the page has no
deadlines of its own). Manual edit mode changes a section's whole list as one change (`fg|<section key>|figs`); alto/edits.py folds it.
"""
from __future__ import annotations

import re

from .sanitize import js_json

MAX_ITEMS = 24
KEYS = {"id", "figure", "label", "detail", "quote", "cite"}
LIM = {"figure": 40, "label": 200, "detail": 200, "quote": 2000, "cite": 120}
DEFAULT_HEADING = "Key figures"
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def _text(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def check_figures(fg, what: str) -> None:
    """{items: [{id?, figure, label?, detail?, quote?, cite?}]}, 1..MAX_ITEMS rows, each with a figure."""
    if not isinstance(fg, dict) or set(fg) - {"items"}:
        raise _err(f"{what}: `figures` is {{items: [{{figure, label?, detail?, quote?, cite?}}]}}")
    items = fg.get("items")
    if not isinstance(items, list) or not items:
        raise _err(f"{what}: figures needs at least one row")
    if len(items) > MAX_ITEMS:
        raise _err(f"{what}: {len(items)} rows exceeds the {MAX_ITEMS}-row limit")
    ids = set()
    for j, x in enumerate(items):
        w = f"{what} row {j + 1}"
        if not isinstance(x, dict) or set(x) - KEYS:
            raise _err(f"{w}: a row is {{figure, label?, detail?, quote?, cite?}}")
        for k, cap in LIM.items():
            v = x.get(k, "")
            if not isinstance(v, str):
                raise _err(f"{w}: {k} must be text")
            if len(v) > cap:
                raise _err(f"{w}: {k} is {len(v)} characters, over the {cap} limit")
        if not (x.get("figure") or "").strip():
            raise _err(f"{w}: figure is required")
        i = x.get("id")
        if i is not None and (not isinstance(i, str) or not _ID.match(i) or i in ids):
            raise _err(f"{w}: id must be a short unique slug")
        ids.add(i)


def sanitize_items(items) -> list:
    """Plain text everywhere (the page draws it escaped), blank rows and unknown keys dropped, slug ids kept."""
    from .sanitize import plain_text
    out = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        o = {k: re.sub(r"\s+", " ", plain_text(_text(x.get(k)))).strip() for k in LIM}
        if not o["figure"]:
            continue
        if isinstance(x.get("id"), str) and _ID.match(x["id"]):
            o["id"] = x["id"]
        out.append({k: v for k, v in o.items() if v or k == "figure"})
    return out[:MAX_ITEMS]


# the page's form: {n: [{i, f, l?, d?, q?, c?}]}
_SHORT = {"figure": "f", "label": "l", "detail": "d", "quote": "q", "cite": "c"}


def compact_items(items) -> list:
    out = []
    for j, x in enumerate(items or []):
        o = {"i": x.get("id") or f"r{j + 1}"}
        o.update({s: x[k] for k, s in _SHORT.items() if x.get(k)})
        out.append(o)
    return out


def compact(sec) -> dict | None:
    fg = getattr(sec, "figures", None) if not isinstance(sec, dict) else sec.get("figures")
    if not fg or not fg.get("items"):
        return None
    return {"n": compact_items(fg["items"])}


def from_compact(v) -> dict:
    """The page's list → the stored form. Raises BriefError when it is not one a section may carry."""
    if not isinstance(v, dict) or not isinstance(v.get("n"), list):
        raise _err("figures: not a list of rows")
    items = []
    for x in v["n"]:
        if not isinstance(x, dict):
            continue
        o = {k: _text(x.get(s)) for k, s in _SHORT.items()}
        o = sanitize_items([o])
        if o:
            if isinstance(x.get("i"), str) and _ID.match(x["i"]):
                o[0]["id"] = x["i"]
            items.append(o[0])
    out = {"items": items}
    check_figures(out, "figures")
    return out


def prepare(b, nodes) -> dict:
    """After sanitize: every section with figures gets a slot at the end of its text (the words inside it, hidden) and the data the
    page draws from, {key: compact}; the key is the section's place, as for trees and study."""
    from .sanitize import esc
    from .study import _all_sections
    reg = {}
    for owner, secs in _all_sections(b, nodes):
        for i, s in enumerate(secs or []):
            c = compact(s) if getattr(s, "figures", None) else None
            if not c:
                continue
            key = f"{owner}-{i}"
            words = " · ".join(" ".join(x.get(k, "") for k in ("f", "l", "d", "q", "c")).strip() for x in c["n"])
            s.t = (s.t or "") + f'<span class="afg-slot" data-afg="{key}" hidden>{esc(words)}</span>'
            reg[key] = c
    return reg


# the drawing: the slot becomes the same box the Deadlines block is (detail_extras.deadlines_html), from the registry
JS = r"""<script id="alto-fg-js">
(function(){
  var D = window._ALTO_FG = window._ALTO_FG || {};
  function E(c, t){ var e = document.createElement('span'); e.className = c; e.textContent = t; return e; }
  function box(key){
    var d = D[key], b = document.createElement('span'); b.className = 'dl-box afg'; b.setAttribute('data-afg-key', key);
    ((d && d.n) || []).forEach(function(x){
      if(!x.f) return;
      var r = E('dl-row', ''), tx = E('dl-tx', '');
      r.appendChild(E('dl-per', x.f)); if(x.l) tx.appendChild(E('dl-what', x.l)); if(x.d) tx.appendChild(E('dl-trg', x.d));
      if(x.q) tx.appendChild(E('dl-q', x.q)); if(x.c) tx.appendChild(E('dl-cite', x.c));
      r.appendChild(tx); b.appendChild(r); });
    return b.firstChild ? b : null;
  }
  function render(slot){
    var key = slot.getAttribute('data-afg'), b = box(key), p = slot.parentNode;
    if(!p) return;
    var host = p.tagName === 'P' ? p : null;
    if(!b){ p.removeChild(slot); return; }
    if(host && host.parentNode){
      host.parentNode.insertBefore(b, host.nextSibling); p.removeChild(slot);
      if(!host.textContent.trim() && !host.querySelector('img,svg,.aed-k')) host.parentNode.removeChild(host);
    } else p.replaceChild(b, slot);
  }
  function scan(){ var s = document.querySelectorAll('.afg-slot[data-afg]'); for(var i = 0; i < s.length; i++){ try{ render(s[i]); }catch(e){} } }
  // an edit changed a list: draw its box again where it stands
  function sync(key){
    var old = document.querySelectorAll('.dl-box[data-afg-key="' + key + '"]'), b = box(key);
    for(var i = 0; i < old.length; i++){ if(b) old[i].parentNode.replaceChild(b.cloneNode(true), old[i]); else old[i].parentNode.removeChild(old[i]); }
  }
  window._altoFigures = {scan: scan, sync: sync, box: box};
  var q = false;
  function soon(){ if(q) return; q = true; Promise.resolve().then(function(){ q = false; scan(); }); }
  function watch(){
    var mo = new MutationObserver(function(ms){ for(var i = 0; i < ms.length; i++){ var a = ms[i].addedNodes;
      for(var j = 0; j < a.length; j++){ var x = a[j]; if(x.nodeType === 1 && (x.classList.contains('afg-slot') || x.querySelector('.afg-slot'))){ soon(); return; } } } });
    var dp = document.getElementById('detail-page') || document.getElementById('detail-content');
    if(dp) mo.observe(dp, {childList: true, subtree: true});
    mo.observe(document.body, {childList: true}); scan();
  }
  if(document.body) watch(); else document.addEventListener('DOMContentLoaded', watch);
})();
</script>"""


def block(reg: dict, css: bool = True) -> str:
    """The data and the drawing script (always there: edit mode can add a section to any page; an empty registry draws nothing). The
    rows' look is the Deadlines sheet; `css` False when the page already carries it."""
    from . import detail_extras as dx
    data = js_json(reg, separators=(",", ":"))
    return (f'<script id="alto-fg-data">window._ALTO_FG={data};</script>\n'
            + (f'<style id="alto-fg-css">{dx.DEADLINES_CSS}</style>\n' if css else "") + JS + "\n")
