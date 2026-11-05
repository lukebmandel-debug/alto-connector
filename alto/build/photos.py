"""Pictures of the owner's own: on a detail page (a Photos section), on a card, in a quiz question or a flash card,
and over a body in the System (Luke, 2026-11-02 L-1102-135455/135525/135705, picks 2026-11-05 "7, i accept your recs":
detail pages A "strip", cards A "small picture + n", System the rising hologram panel; "photos should show on phones too, and on cards and
detail pages" L-1105-101750).

THE PAGE NEVER CARRIES A PICTURE. A page names a picture by `ref` ("pic-" + 10 characters) and holds the words around it
(caption, alt text) and where it sits. The picture is the owner's own file, shrunk in their browser (a small version for the strip and
the card, a large one for the viewer) and kept where the rest of their account is (alto-cloud.js `pics`:
users/{uid}/pics/{ref} the small one, users/{uid}/picbig/{ref} the large one) and in this browser (IndexedDB 'alto-pics'), as an imported
background is (backgrounds_import.py). Everything that draws or adds one is the hosted script (/pics/alto-pics-<hash>.js, ASSET below), which a
page fetches only when it has a picture or its owner is about to add one; the page holds the data and a ~400 byte loader.

  Section.photos = {"items": [{id?, ref, caption?, alt?}, ...], "label": ""}     a Photos section (one of tree / cards / quiz / photos)
  Node.photos    = [{id?, ref, caption?, alt?}, ...]                              a card's pictures (at most MAX_CARD)
  a quiz question: "pic" {ref, caption?, alt?}; a flash card: "front_pic" / "back_pic" (study.py)

Build path: brief._check_sections / validate_nodes → check_photos / check_items (shape); sanitize.sanitize_brief → sanitize_items (plain text,
slug ids); builder → prepare (a hidden .aph-slot with the captions, so search finds them; the data) → block (data + loader). Manual edit
mode changes a section's whole list as one change (`ph|<key>|pics`) and a card's as `pc|<id>|pics`; alto/edits.py folds both.

THE LOOKS. Classic is the base; Retro (html.alto-retro) and Holographic (html.alto-holo) are separate blocks below (RETRO_CSS, HOLO_CSS), written
with the style's own tokens, so a department that changes a style's detail pages does not meet these rules.
"""
from __future__ import annotations

import hashlib as _hashlib
import json
import re

from .sanitize import js_json

FOLDER = "pics"
MAX_ITEMS = 40            # pictures in one Photos section
MAX_CARD = 12             # pictures on one card
REF = re.compile(r"^pic-[a-z0-9]{8,16}$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
ITEM_KEYS = {"id", "ref", "caption", "alt"}
LABEL_KEYS = {"items", "label"}
_LIM = {"caption": 200, "alt": 300, "label": 120}


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def _text(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def check_items(items, what: str, cap: int = MAX_ITEMS) -> None:
    """The shape of a list of pictures: [{id?, ref, caption?, alt?}], 1..cap, refs of this module's form, no ref twice in one list."""
    if not isinstance(items, list) or not items:
        raise _err(f"{what}: pictures must be a list with at least one picture")
    if len(items) > cap:
        raise _err(f"{what}: {len(items)} pictures exceeds the {cap}-picture limit")
    seen, ids = set(), set()
    for j, x in enumerate(items):
        w = f"{what} picture {j + 1}"
        if not isinstance(x, dict):
            raise _err(f"{w}: must be an object with a `ref`")
        extra = set(x) - ITEM_KEYS
        if extra:
            raise _err(f"{w}: unknown key(s) {sorted(extra)}; allowed: {sorted(ITEM_KEYS)}")
        ref = x.get("ref")
        if not isinstance(ref, str) or not REF.match(ref):
            raise _err(f"{w}: `ref` must look like pic-xxxxxxxxxx (the picture's own name in the account)")
        if ref in seen:
            raise _err(f"{w}: {ref} appears twice in the same list")
        seen.add(ref)
        if x.get("id") is not None:
            if not isinstance(x["id"], str) or not _ID.match(x["id"]):
                raise _err(f"{w}: id must be a lowercase slug")
            if x["id"] in ids:
                raise _err(f"{w}: duplicate id {x['id']!r}")
            ids.add(x["id"])
        for k in ("caption", "alt"):
            v = x.get(k)
            if v is not None and (not isinstance(v, str) or len(v) > _LIM[k]):
                raise _err(f"{w}: {k} must be text of at most {_LIM[k]} characters")


def check_photos(ph, what: str) -> None:
    """A Photos section's own record: {items: [...], label?}."""
    if not isinstance(ph, dict):
        raise _err(f"{what}: photos must be an object {{items: [...], label?}}")
    extra = set(ph) - LABEL_KEYS
    if extra:
        raise _err(f"{what}: unknown photos key(s) {sorted(extra)}; allowed: {sorted(LABEL_KEYS)}")
    check_items(ph.get("items"), what)
    lab = ph.get("label")
    if lab is not None and (not isinstance(lab, str) or len(lab) > _LIM["label"]):
        raise _err(f"{what}: photos label must be text of at most {_LIM['label']} characters")


def sanitize_items(items) -> list:
    """Plain text everywhere (the page shows it with textContent), a slug id for each (p1, p2, ...). A new list."""
    from .sanitize import plain_text
    out = []
    for x in items or []:
        if not isinstance(x, dict) or not REF.match(str(x.get("ref") or "")):
            continue
        o = {"id": x.get("id") or "", "ref": x["ref"], "caption": plain_text(_text(x.get("caption"))).strip()[:_LIM["caption"]],
             "alt": plain_text(_text(x.get("alt"))).strip()[:_LIM["alt"]]}
        out.append(o)
    used = {o["id"] for o in out if o["id"]}
    n = 0
    for o in out:
        if not o["id"]:
            n += 1
            while f"p{n}" in used:
                n += 1
            o["id"] = f"p{n}"
            used.add(o["id"])
    return out


def _c(x: dict) -> dict:
    """One picture as the page keeps it: {i, r, c?, a?}."""
    o = {"i": x["id"], "r": x["ref"]}
    if x.get("caption"):
        o["c"] = x["caption"]
    if x.get("alt"):
        o["a"] = x["alt"]
    return o


def compact(sec) -> dict | None:
    """A Photos section as the page keeps it (and edit mode changes whole): {lab, n: [{i, r, c?, a?}]}; see from_compact for the way back."""
    ph = getattr(sec, "photos", None)
    if not ph or not ph.get("items"):
        return None
    return {"lab": ph.get("label") or "", "n": [_c(x) for x in ph["items"]]}


def compact_items(items) -> list:
    return [_c(x) for x in items or []]


def items_from_compact(n) -> list:
    """The page's [{i, r, c?, a?}] → the stored [{id?, ref, caption?, alt?}]. Raises BriefError when it is not a list a section may carry."""
    from .sanitize import plain_text
    if not isinstance(n, list):
        raise _err("photos: not a list of pictures")
    out = []
    for x in n:
        if not isinstance(x, dict):
            raise _err("photos: not a picture")
        o = {"id": x.get("i") or "", "ref": x.get("r"), "caption": plain_text(_text(x.get("c"))).strip(), "alt": plain_text(_text(x.get("a"))).strip()}
        for k in ("id", "caption", "alt"):
            if not o[k]:
                del o[k]
        out.append(o)
    return out


def from_compact(v: dict) -> dict:
    """The page's section record → the stored `photos`. Raises BriefError when the shape is not one a section may carry."""
    if not isinstance(v, dict) or not isinstance(v.get("n"), list):
        raise _err("photos: not a list of pictures")
    out = {"items": items_from_compact(v["n"])}
    if v.get("lab"):
        from .sanitize import plain_text
        out["label"] = plain_text(_text(v["lab"])).strip()
    check_photos(out, "photos")
    return out


def prepare(b, nodes) -> tuple:
    """After sanitize: give every Photos section a slot at the end of its text (its captions inside, hidden, so search finds them) and
    return the data the renderer reads, ({section key: compact}, {card id: [compact items]}). A section's key is its place, as for trees."""
    from .sanitize import esc
    from .subtree import _all_sections
    reg, creg = {}, {}
    for owner, secs in _all_sections(b, nodes):
        for i, s in enumerate(secs or []):
            c = compact(s)
            if not c:
                continue
            key = f"{owner}-{i}"
            words = " · ".join(" ".join(x for x in (p.get("c"), p.get("a")) if x) for p in c["n"]).strip(" ·")
            s.t = (s.t or "") + f'<span class="aph-slot" data-aph="{key}" hidden>{esc(words)}</span>'
            reg[key] = c
    for n in nodes:
        if getattr(n, "photos", None):
            creg[n.id] = compact_items(n.photos)
    return reg, creg


def block(reg: dict, creg: dict) -> str:
    """The page's part: the data, and the loader (hosted script, fetched when there is a picture here or the owner starts adding one:
    `_altoPicsLoad()`). Always there, as the study block is: manual edit mode can add a Photos section to any page."""
    from .palace_assets import loader
    data = (f"window._ALTO_PH={js_json(reg, separators=(',', ':'))};window._ALTO_PC={js_json(creg, separators=(',', ':'))};")
    ld = ("window._altoPicsLoad=function(){" + loader(PATH, GUARD) + "return !!window." + GUARD + ";};"
          "if(" + ("true" if (reg or creg) else "false") + ")_altoPicsLoad();")
    return '<script id="alto-ph">' + data + ld + "</script>\n"


# ───────────────────────────── the hosted script ─────────────────────────────

GUARD = "_altoPics"

# Classic, the base. Every colour is the page's own token (--text, --muted, --border, --surface, --accent), so a style that re-inks
# the tokens (Retro, Holographic) re-inks this too; the two blocks after it only change shape and frame.
BASE_CSS = r"""
.aph{margin:14px 0 6px;max-width:100%;}
.aph .aph-lab{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;}
.aph .aph-row{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;}
.aph .aph-fig{flex:0 0 calc(25% - 9px);max-width:280px;min-width:0;margin:0;display:flex;flex-direction:column;gap:6px;position:relative;}
.aph .aph-img{display:block;position:relative;width:100%;aspect-ratio:4/3;padding:0;margin:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:color-mix(in srgb,var(--text) 7%,transparent);cursor:zoom-in;font:inherit;color:var(--muted);}
.aph .aph-img img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;}
.aph .aph-img:focus-visible{outline:2px solid var(--accent,#7c6cf0);outline-offset:2px;}
.aph .aph-img .aph-wait{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;padding:6px;text-align:center;}
.aph .aph-cap{font-size:12.5px;line-height:1.4;color:var(--muted);word-break:break-word;}
.aph.aph-one .aph-fig{flex-basis:min(100%,340px);max-width:340px;}
.aph.aph-few .aph-fig{flex-basis:calc(33.333% - 8px);max-width:300px;}
.aph .aph-ed{display:none;}
html.alto-editing .aph .aph-ed{display:flex;}
html.alto-editing .aph .aph-cap{display:none;}
.aph .aph-ed{flex-direction:column;gap:4px;}
.aph .aph-ed input{width:100%;box-sizing:border-box;padding:5px 7px;border-radius:6px;border:1px solid var(--border);background:var(--bg,transparent);color:var(--text);font:inherit;font-size:12px;}
.aph .aph-tools{display:none;position:absolute;top:5px;right:5px;gap:3px;z-index:2;}
html.alto-editing .aph .aph-tools{display:inline-flex;}
.aph .aph-tools button{width:24px;height:24px;padding:0;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font:inherit;font-size:12px;line-height:1;}
.aph .aph-tools button:hover{border-color:var(--muted);}
.aph .aph-tools button:last-child:hover{color:#dc2626;border-color:#dc2626;}
.aph .aph-add{display:none;flex:0 0 calc(25% - 9px);max-width:280px;aspect-ratio:4/3;box-sizing:border-box;align-items:center;justify-content:center;flex-direction:column;gap:4px;text-align:center;padding:8px;border:1.5px dashed var(--border);border-radius:8px;background:none;color:var(--muted);font:inherit;font-size:12.5px;cursor:pointer;}
html.alto-editing .aph .aph-add{display:flex;}
.aph .aph-add:hover,.aph .aph-add.over{color:var(--text);border-color:var(--muted);}
.aph .aph-add b{font-size:20px;font-weight:400;line-height:1;}
.aph .aph-err{width:100%;font-size:12.5px;color:#dc2626;}
.aph-ph .aph-ph-h{font-size:12.5px;color:var(--muted);}
@media (max-width:760px){.aph .aph-fig,.aph .aph-add,.aph.aph-few .aph-fig{flex-basis:calc(50% - 6px);}}
html.mobile .aph .aph-fig,html.mobile .aph .aph-add,html.mobile .aph.aph-few .aph-fig,html.mobile .aph.aph-one .aph-fig{flex-basis:100%;}
html.mobile .aph .aph-img{aspect-ratio:auto;max-height:70vh;}
html.mobile .aph .aph-img img{position:static;height:auto;max-height:70vh;object-fit:contain;}
/* the viewer */
#aph-lb{position:fixed;inset:0;z-index:8600;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px;padding:3vh 3vw;background:rgba(6,7,12,.88);color:#eceef5;-webkit-tap-highlight-color:transparent;}
#aph-lb img{max-width:94vw;max-height:78vh;object-fit:contain;border-radius:4px;background:#000;}
#aph-lb .lb-cap{max-width:min(760px,92vw);text-align:center;font:14px/1.45 system-ui,-apple-system,sans-serif;}
#aph-lb .lb-n{font:11px system-ui,sans-serif;letter-spacing:.12em;opacity:.7;}
#aph-lb button{position:absolute;width:44px;height:44px;border-radius:50%;border:1px solid rgba(255,255,255,.35);background:rgba(0,0,0,.45);color:#fff;font-size:20px;line-height:1;cursor:pointer;}
#aph-lb .lb-x{top:14px;right:14px;} #aph-lb .lb-p{left:14px;top:50%;} #aph-lb .lb-nx{right:14px;top:50%;}
#aph-lb button:hover{background:rgba(255,255,255,.18);}
/* a card's picture: a small square at its right with +n; enlarged, the pictures open beside it */
.node-card.aph-has{position:relative;}
.aph-thumb{position:absolute;right:9px;bottom:9px;width:38px;height:38px;padding:0;margin:0;border:1px solid var(--border);border-radius:7px;overflow:hidden;background:color-mix(in srgb,var(--text) 10%,var(--surface));cursor:pointer;z-index:3;box-shadow:0 2px 8px rgba(0,0,0,.25);}
.aph-thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;pointer-events:none;}
.aph-thumb .aph-n{position:absolute;right:0;bottom:0;padding:1px 5px;border-top-left-radius:6px;background:var(--text);color:var(--bg,#fff);font:700 10px/1.4 system-ui,sans-serif;pointer-events:none;}
.aph-tray{position:absolute;left:calc(100% + 16px);top:0;z-index:30;display:flex;flex-wrap:wrap;gap:8px;width:min(300px,26vw);padding:10px;border:1px solid var(--border);border-radius:12px;background:var(--surface);color:var(--text);box-shadow:0 14px 36px rgba(0,0,0,.35);}
.aph-tray.aph-left{left:auto;right:calc(100% + 16px);}
.aph-tray button{flex:0 0 calc(50% - 4px);min-width:0;aspect-ratio:1;padding:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;position:relative;background:color-mix(in srgb,var(--text) 8%,transparent);cursor:zoom-in;}
.aph-tray button:only-child{flex-basis:100%;aspect-ratio:4/3;}
.aph-tray img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;}
.aph-tray .aph-tc{flex:1 0 100%;font-size:12px;line-height:1.4;color:var(--muted);}
html.mobile .aph-tray{display:none;}
.aph-cardadd{position:absolute;right:9px;bottom:9px;width:34px;height:34px;display:none;align-items:center;justify-content:center;border:1.5px dashed var(--muted);border-radius:7px;background:var(--surface);color:var(--text);font-size:11px;cursor:pointer;z-index:4;padding:0;}
html.alto-editing:not(.mobile) .node-card:hover .aph-cardadd{display:flex;}
html.alto-editing .node-card.aph-has .aph-cardadd{display:none !important;}
/* a card's pictures on its detail page: beside the title (a few small squares, +n for the rest); while editing, below it with the captions */
.aph.aph-top{margin:10px 0 22px;}
.aph.aph-top .aph-fig{flex-basis:calc(20% - 10px);max-width:200px;}
.aph.aph-top .aph-add{flex-basis:calc(20% - 10px);max-width:200px;}
.aph.aph-side{margin:0 0 0 auto;flex:0 1 auto;max-width:56%;align-self:center;}
.aph.aph-side .aph-row{flex-wrap:nowrap;gap:8px;justify-content:flex-end;}
.aph.aph-side .aph-fig{flex:0 0 96px;max-width:96px;}
.aph.aph-side .aph-img{aspect-ratio:1;}
.aph.aph-side .aph-cap,.aph.aph-side .aph-ed,.aph.aph-side .aph-add{display:none !important;}
.aph.aph-side .aph-img .aph-n{position:absolute;right:0;bottom:0;padding:2px 7px;border-top-left-radius:7px;background:var(--text);color:var(--bg,#fff);font:700 12px/1.4 system-ui,sans-serif;z-index:2;}
/* in a quiz question and on a flash card */
.aph-q{margin:8px 0 10px;max-width:420px;}
.aph-q .aph-img{aspect-ratio:auto;max-height:260px;}
.aph-q .aph-img img{position:static;width:100%;height:auto;max-height:260px;object-fit:contain;}
.aph-q .aph-cap{font-size:12px;color:var(--muted);margin-top:4px;}
.aph-cf{margin:6px auto 4px;max-width:100%;}
.aph-cf .aph-img{aspect-ratio:auto;max-height:150px;}
.aph-cf .aph-img img{position:static;width:auto;max-width:100%;height:auto;max-height:150px;margin:0 auto;object-fit:contain;}
/* print: the strip prints with its captions; the ink-saver sheet leaves the pictures out and prints the captions */
@media print{
  .aph .aph-ed,.aph .aph-tools,.aph .aph-add,.aph-thumb,.aph-tray,.aph-cardadd,#aph-lb{display:none !important;}
  .aph .aph-cap{display:block !important;color:#000;}
  .aph .aph-fig{break-inside:avoid;page-break-inside:avoid;}
  .aph .aph-img{border-color:#999;cursor:default;}
  html.print-ink .aph .aph-img{display:none !important;}
  html.print-ink .aph .aph-fig{flex-basis:100%;}
  html.print-ink .aph .aph-cap::before{content:'Picture: ';font-weight:600;}
}
"""

# Retro (html.alto-retro): square gold frames on black, as everything else is (retro.py: gold #d9ae55, cream #efe6cf, black).
RETRO_CSS = r"""
html.alto-retro .aph .aph-img,html.alto-retro .aph-thumb,html.alto-retro .aph-tray,html.alto-retro .aph-tray button,html.alto-retro .aph .aph-add,html.alto-retro .aph-cardadd,html.alto-retro .aph .aph-ed input,html.alto-retro .aph .aph-tools button{border-radius:0 !important;}
html.alto-retro .aph .aph-img,html.alto-retro .aph-thumb,html.alto-retro .aph-tray button{border:1px solid rgba(217,174,85,.7);background:#000;box-shadow:0 0 0 3px #000,0 0 0 4px rgba(217,174,85,.35);}
html.alto-retro .aph .aph-cap,html.alto-retro .aph .aph-lab,html.alto-retro .aph-tray .aph-tc{color:#d9ae55;font-family:var(--rt-f,inherit);letter-spacing:.1em;text-transform:uppercase;font-size:11px;}
html.alto-retro .aph .aph-add,html.alto-retro .aph-cardadd{border:1px dashed rgba(217,174,85,.7);color:#d9ae55;background:#000;}
html.alto-retro .aph .aph-ed input{background:#000;color:#efe6cf;border:1px solid rgba(217,174,85,.55);}
html.alto-retro .aph .aph-tools button{background:#000;color:#d9ae55;border:1px solid rgba(217,174,85,.55);}
html.alto-retro .aph-thumb .aph-n{background:#d9ae55;color:#000;border-radius:0;}
html.alto-retro .aph-tray{border:1px solid rgba(217,174,85,.7);border-radius:0;background:#000;box-shadow:none;}
html.alto-retro #aph-lb img{border:1px solid rgba(217,174,85,.7);border-radius:0;box-shadow:0 0 0 4px #000,0 0 0 5px rgba(217,174,85,.4);}
html.alto-retro #aph-lb button{border-radius:0;border-color:rgba(217,174,85,.7);color:#d9ae55;background:#000;}
html.alto-retro #aph-lb .lb-cap{color:#efe6cf;font-family:var(--rt-f,inherit);}
"""

# Holographic (html.alto-holo): cyan wireframe frames with corner ticks; the tokens are holo.py's own (--ho-*).
HOLO_CSS = r"""
html.alto-holo .aph .aph-img,html.alto-holo .aph-thumb,html.alto-holo .aph-tray,html.alto-holo .aph-tray button,html.alto-holo .aph .aph-add,html.alto-holo .aph-cardadd,html.alto-holo .aph .aph-ed input,html.alto-holo .aph .aph-tools button{border-radius:0 !important;}
html.alto-holo .aph .aph-img,html.alto-holo .aph-thumb,html.alto-holo .aph-tray button{border:1px solid var(--ho-ac);background:var(--ho-bg);box-shadow:var(--ho-glow);}
html.alto-holo .aph .aph-img::after,html.alto-holo .aph-tray button::after{content:'';position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(var(--ho-rgb),.07) 0 1px,transparent 1px 3px);}
html.alto-holo .aph .aph-img img{filter:saturate(.85) contrast(1.05);}
html.alto-holo .aph .aph-cap,html.alto-holo .aph .aph-lab,html.alto-holo .aph-tray .aph-tc{color:var(--ho-mu);letter-spacing:.06em;font-size:12px;}
html.alto-holo .aph .aph-add,html.alto-holo .aph-cardadd{border:1px dashed var(--ho-ac);color:var(--ho-ac2);background:var(--ho-bg);}
html.alto-holo .aph .aph-ed input{background:var(--ho-bg);color:var(--ho-tx);border:1px solid rgba(var(--ho-rgb),.5);}
html.alto-holo .aph .aph-tools button{background:var(--ho-bg);color:var(--ho-ac2);border:1px solid rgba(var(--ho-rgb),.5);}
html.alto-holo .aph-thumb .aph-n{background:var(--ho-ac);color:var(--ho-on);border-radius:0;}
html.alto-holo .aph-tray{border:1px solid var(--ho-ac);border-radius:0;background:rgba(var(--ho-sfrgb),.97);box-shadow:var(--ho-glow);}
html.alto-holo #aph-lb{background:rgba(1,10,14,.92);}
html.alto-holo #aph-lb img{border:1px solid var(--ho-ac);border-radius:0;box-shadow:var(--ho-glow);}
html.alto-holo #aph-lb button{border-radius:0;border-color:var(--ho-ac);color:var(--ho-ac2);background:var(--ho-bg);}
html.alto-holo #aph-lb .lb-cap{color:var(--ho-tx);}
@media (prefers-reduced-motion:no-preference){html.alto-holo .aph .aph-img{transition:box-shadow .25s;} html.alto-holo .aph .aph-img:hover{box-shadow:0 0 14px rgba(var(--ho-rgb),.6);}}
"""

# the System's rising panel (solar_pics.py appends its own rules)
CSS = BASE_CSS + RETRO_CSS + HOLO_CSS

PICS_JS = r"""(function(){
  if(window.__GUARD__) return;
  var root=document.documentElement, DBN='alto-pics', EDGE_T=480, EDGE_B=1800, MAXB=__MAXB__, MAXF=__MAXF__, MAXI=__MAXI__;
  var U={}, pend={}, API={};
  function el(tag, cls, txt){ var e=document.createElement(tag); if(cls) e.className=cls; if(txt!=null) e.textContent=txt; return e; }
  function E(){ return window._altoEdit || null; }
  function editing(){ return root.classList.contains('alto-editing'); }
  function sty(){ var s=document.createElement('style'); s.id='alto-pics-css'; s.textContent=__CSS__; document.head.appendChild(s); }
  if(!document.getElementById('alto-pics-css')) sty();

  /* ── the account (alto-cloud.js `pics`); a share is a frame, whose page has it in the parent ── */
  function cloudWin(){ try{ if(window.AltoCloud) return window; if(parent!==window && parent.AltoCloud) return parent; }catch(e){} return null; }
  function AC(){ var w=cloudWin(), c=w && w.AltoCloud; return c && c.enabled && c.pics ? c : null; }
  function authed(){
    var c=AC(), w=cloudWin(); if(!c) return Promise.reject(new Error('not-configured'));
    if(c.known) return c.user ? Promise.resolve(c) : Promise.reject(new Error('signed-out'));
    return new Promise(function(res, rej){
      var to=setTimeout(function(){ rej(new Error('signed-out')); }, 15000);
      w.addEventListener('alto-auth', function f(){ w.removeEventListener('alto-auth', f); clearTimeout(to); c.user ? res(c) : rej(new Error('signed-out')); });
    });
  }

  function shareKey(){ var id=''; try{ id=String(window.COURSE_ID||''); }catch(e){} return /^s-[a-km-np-z2-9]{22}$/.test(id) ? id.slice(2) : ''; }

  /* ── this browser's copies (IndexedDB 'alto-pics'; an ArrayBuffer per picture and size: WebKit keeps no Blob in a private window) ── */
  function idb(mode, f){
    return new Promise(function(res, rej){
      var q; try{ q=indexedDB.open(DBN, 1); }catch(e){ rej(e); return; }
      q.onupgradeneeded=function(){ q.result.createObjectStore('p'); };
      q.onerror=function(){ rej(q.error); };
      q.onsuccess=function(){
        var db=q.result, tx=db.transaction('p', mode), r=f(tx.objectStore('p'));
        tx.oncomplete=function(){ db.close(); res(r && r.result); };
        tx.onerror=tx.onabort=function(){ db.close(); rej(tx.error); };
      };
    });
  }
  function ik(ref, k){ return ref + (k==='big' ? '#b' : ''); }
  function idbGet(ref, k){ return idb('readonly', function(s){ return s.get(ik(ref,k)); }).catch(function(){ return null; }); }
  function idbPut(ref, k, v){ return idb('readwrite', function(s){ return s.put(v, ik(ref,k)); }).catch(function(){}); }

  /* a picture's address (a blob: URL), which size ('th' or 'big'): this browser's copy, else the account's (kept here for next time) */
  function url(ref, k){
    k=k||'th'; var key=ik(ref,k);
    if(U[key]) return Promise.resolve(U[key]);
    if(pend[key]) return pend[key];
    pend[key]=idbGet(ref,k).then(function(v){
      if(v && v.buf) return v;
      var sk=shareKey();           // a share's reader has no account: the copy the share made beside it
      var got=sk ? (AC() ? AC().pics.shared(sk, ref, k) : Promise.reject(new Error('not-configured'))) : authed().then(function(c){ return c.pics.get(ref, k); });
      return got.then(function(r){
        if(!r) return null;
        var u8=r.bytes, v2={buf:u8.buffer.slice(u8.byteOffset, u8.byteOffset+u8.byteLength), type:r.type};
        idbPut(ref,k,v2); return v2;
      });
    }).then(function(v){
      delete pend[key];
      if(!v) throw new Error('missing');
      return (U[key]=URL.createObjectURL(new Blob([v.buf], {type:v.type||'image/jpeg'})));
    }, function(e){ delete pend[key]; throw e; });
    return pend[key];
  }
  API.url=url;

  /* ── a picture drawn: its image comes when its address does (at once if it is already here) ── */
  function paint(img, wait, ref, k){
    url(ref, k).then(function(u){ img.src=u; if(wait && wait.parentNode) wait.parentNode.removeChild(wait); },
      function(e){ if(wait) wait.textContent = /signed-out|not-configured/.test(String(e && e.message)) ? 'Sign in to see this picture' : 'Picture not found'; });
  }
  function figBtn(it, k, cls){
    var b=el('button', cls||'aph-img'); b.type='button';
    b.setAttribute('aria-label', (it.a || it.c || 'Picture') + ' — open large');
    var w=el('span','aph-wait','…'), im=el('img'); im.alt=it.a || it.c || ''; im.decoding='async'; im.draggable=false;
    b.appendChild(im); b.appendChild(w); paint(im, w, it.r, k||'th'); return b;
  }
  API.figure=function(it, cls){            // a picture in a quiz question or on a flash card: {r, c?, a?}
    var f=el('figure', 'aph '+(cls||'aph-q')); f.style.margin='0';
    var b=figBtn(it,'th'); b.addEventListener('click', function(e){ e.stopPropagation(); lightbox([it], 0); }); f.appendChild(b);
    if(it.c) f.appendChild(el('figcaption','aph-cap',it.c)); return f;
  };

  /* ── the viewer ── */
  var lb=null, lbItems=[], lbAt=0, lbBack=null;
  function lbDraw(){
    var it=lbItems[lbAt]; if(!it) return;
    var im=lb.querySelector('img'); im.alt=it.a||it.c||''; im.removeAttribute('src');
    url(it.r,'big').then(function(u){ if(lbItems[lbAt]===it) im.src=u; }, function(){ return url(it.r,'th').then(function(u){ if(lbItems[lbAt]===it) im.src=u; }); }).catch(function(){});
    lb.querySelector('.lb-cap').textContent=it.c||''; lb.querySelector('.lb-n').textContent=lbItems.length>1 ? (lbAt+1)+' / '+lbItems.length : '';
    lb.querySelector('.lb-p').style.display=lb.querySelector('.lb-nx').style.display=lbItems.length>1 ? '' : 'none';
  }
  function lbKey(e){
    if(e.key==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); lbClose(); }
    else if(e.key==='ArrowLeft' && lbItems.length>1){ e.preventDefault(); e.stopImmediatePropagation(); lbAt=(lbAt+lbItems.length-1)%lbItems.length; lbDraw(); }
    else if(e.key==='ArrowRight' && lbItems.length>1){ e.preventDefault(); e.stopImmediatePropagation(); lbAt=(lbAt+1)%lbItems.length; lbDraw(); }
  }
  function lbClose(){ if(lb && lb.parentNode) lb.parentNode.removeChild(lb); lb=null; window.removeEventListener('keydown', lbKey, true); if(lbBack && lbBack.focus){ try{ lbBack.focus(); }catch(e){} } }
  function lightbox(items, at){
    lbItems=items; lbAt=at||0; lbBack=document.activeElement;
    if(lb) lbClose();
    lb=el('div'); lb.id='aph-lb'; lb.setAttribute('role','dialog'); lb.setAttribute('aria-modal','true'); lb.setAttribute('aria-label','Picture');
    var im=el('img'); lb.appendChild(im); lb.appendChild(el('div','lb-cap')); lb.appendChild(el('div','lb-n'));
    [['lb-x','✕','Close'],['lb-p','‹','Previous picture'],['lb-nx','›','Next picture']].forEach(function(a){ var b=el('button',a[0],a[1]); b.type='button'; b.setAttribute('aria-label',a[2]); lb.appendChild(b); });
    lb.addEventListener('click', function(e){
      var c=e.target.closest('button');
      if(c && c.classList.contains('lb-p')){ lbAt=(lbAt+lbItems.length-1)%lbItems.length; lbDraw(); }
      else if(c && c.classList.contains('lb-nx')){ lbAt=(lbAt+1)%lbItems.length; lbDraw(); }
      else if(!e.target.closest('img')) lbClose();
    });
    lb.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    document.body.appendChild(lb); window.addEventListener('keydown', lbKey, true); lbDraw();
    var x=lb.querySelector('.lb-x'); if(x) x.focus();
  }
  API.lightbox=lightbox;

  /* ── adding: a file shrunk here (a small size and a large one), kept in this browser and in the account ── */
  function rid(){ var a='abcdefghijklmnopqrstuvwxyz0123456789', s='pic-', i; try{ var u=new Uint8Array(10); crypto.getRandomValues(u); for(i=0;i<10;i++) s+=a[u[i]%36]; }catch(e){ for(i=0;i<10;i++) s+=a[Math.floor(Math.random()*36)]; } return s; }
  function blobOf(cv, q){
    return new Promise(function(res){
      cv.toBlob(function(b){
        if(b && b.type==='image/webp') res(b);
        else cv.toBlob(function(j){ res(j); }, 'image/jpeg', q);
      }, 'image/webp', q);
    });
  }
  function scaled(bm, edge, q, cap){
    var w=bm.width, h=bm.height, s=Math.min(1, edge/Math.max(w,h)); w=Math.max(1,Math.round(w*s)); h=Math.max(1,Math.round(h*s));
    var cv=document.createElement('canvas'); cv.width=w; cv.height=h; var cx=cv.getContext('2d'); cx.fillStyle='#fff'; cx.fillRect(0,0,w,h); cx.drawImage(bm,0,0,w,h);
    return blobOf(cv,q).then(function(b){
      if(!b) throw new Error('encode');
      if(b.size<=cap || q<=.4) return {blob:b, w:w, h:h};
      return scaled(bm, Math.round(edge*.82), q-.1, cap);
    });
  }
  function decode(file){
    if(window.createImageBitmap) return createImageBitmap(file, {imageOrientation:'from-image'}).catch(function(){ return createImageBitmap(file); });
    return new Promise(function(res, rej){ var u=URL.createObjectURL(file), im=new Image(); im.onload=function(){ URL.revokeObjectURL(u); res(im); }; im.onerror=function(){ URL.revokeObjectURL(u); rej(new Error('decode')); }; im.src=u; });
  }
  function bytes(b){ return b.arrayBuffer().then(function(ab){ return new Uint8Array(ab); }); }
  function say(msg){ var e=E(); if(e && e.toast) e.toast(msg); }
  function oneFile(file){
    if(!file) return Promise.reject(new Error('nofile'));
    if(!/^image\//.test(file.type||'') && !/\.(jpe?g|png|gif|webp|avif|heic|heif|bmp)$/i.test(file.name||'')) return Promise.reject(new Error('type:'+(file.name||'that file')));
    if(file.size>MAXF) return Promise.reject(new Error('big:'+(file.name||'that file')));
    return decode(file).then(function(bm){
      return scaled(bm, EDGE_T, .78, 60000).then(function(t){ return scaled(bm, EDGE_B, .84, MAXB).then(function(g){ return {t:t, g:g}; }); });
    }, function(){ throw new Error('read:'+(file.name||'that file')); }).then(function(r){
      var ref=rid(), type=r.g.blob.type||'image/jpeg';
      return Promise.all([bytes(r.t.blob), bytes(r.g.blob)]).then(function(bb){
        var th={buf:bb[0].buffer.slice(bb[0].byteOffset, bb[0].byteOffset+bb[0].byteLength), type:r.t.blob.type||type};
        var big={buf:bb[1].buffer.slice(bb[1].byteOffset, bb[1].byteOffset+bb[1].byteLength), type:type};
        return Promise.all([idbPut(ref,'th',th), idbPut(ref,'big',big)]).then(function(){
          return authed().then(function(c){ return c.pics.put(ref, bb[0], bb[1], {thType:th.type, type:type, w:r.g.w, h:r.g.h}); }).then(function(){
            return {i:'p'+Math.random().toString(36).slice(2,8), r:ref, w:r.g.w, h:r.g.h};
          }, function(e){ throw new Error('save:'+(e && e.message || '')); });
        });
      });
    });
  }
  function explain(e){
    var m=String(e && e.message || e), k=m.split(':')[0], w=m.slice(k.length+1);
    if(k==='type') return w+' is not a picture. Choose a JPEG, PNG, GIF or WebP file.';
    if(k==='big') return w+' is too large to open (over '+Math.round(MAXF/1048576)+' MB). Choose a smaller picture.';
    if(k==='read') return 'Alto could not read '+w+'. If it is a HEIC photo, export it as a JPEG first.';
    if(k==='save'){ return /signed-out/.test(w) ? 'Sign in to your Alto site to add pictures.' : /not-configured/.test(w) ? 'Pictures are kept in your Alto account, which this page is not connected to.' : /too-large/.test(w) ? 'That picture would not fit in your account even shrunk. Choose a smaller one.' : 'Your account did not take that picture ('+(w||'try again')+'). It is not added.'; }
    return 'That picture could not be added.';
  }
  /* files → pictures made, one by one (an error stops nothing else): cb(items, errors) */
  function addFiles(files, max, cb){
    var list=[].slice.call(files||[]).slice(0,max), out=[], errs=[];
    (function next(i){
      if(i>=list.length){ cb(out, errs); return; }
      oneFile(list[i]).then(function(it){ out.push(it); }, function(e){ errs.push(explain(e)); }).then(function(){ next(i+1); });
    })(0);
  }
  API.addFiles=addFiles;
  function chooser(multi, cb){
    var f=el('input'); f.type='file'; f.accept='image/*'; f.multiple=!!multi; f.style.display='none'; document.body.appendChild(f);
    f.addEventListener('change', function(){ var fs=[].slice.call(f.files||[]); if(f.parentNode) f.parentNode.removeChild(f); if(fs.length) cb(fs); });
    f.click();
  }
  API.pick=function(multi, max, cb){          // choose files; cb(items, errors)
    chooser(multi, function(fs){ addFiles(fs, max, cb); });
  };

  /* ── a Photos section (or a card's pictures on its detail page): its row ── */
  function S(key){ return (window._ALTO_PH||{})[key]; }
  var MAXI_C=__MAXC__;
  // the list of pictures a row edits, and the way to change it: a section's whole record (ph|…), or a card's list (pc|…)
  function acc(key){
    var e=E(), card=key.indexOf('pc|')===0; if(!e || !e.field) return null;
    var f=e.field(card ? key+'|pics' : 'ph|'+key+'|pics'); if(!f) return null;
    return {max: card ? MAXI_C : MAXI,
      get:function(){ var v=f.get(); return card ? (v||[]) : (v && v.n || []); },
      set:function(a){ if(card) return e.change(key+'|pics', a); var v=f.get()||{lab:''}; v.n=a; return e.change('ph|'+key+'|pics', v); }};
  }
  function strip(key, data, top, side){
    var n=data.n||[], all=n, box=el('div','aph aph-'+(n.length===1?'one':n.length===2||n.length===3?'few':'many')+(top?' aph-top':'')+(side?' aph-side':''));
    box.setAttribute('data-aph-key', key); box.setAttribute('role','group'); box.setAttribute('aria-label', data.lab || 'Pictures');
    if(data.lab) box.appendChild(el('div','aph-lab',data.lab));
    var row=el('div','aph-row'); box.appendChild(row);
    function edit(fn){ var a=acc(key); if(!a) return; var l=a.get().map(function(x){ return Object.assign({}, x); }); if(fn(l, a)!==false) a.set(l); }
    (side ? n.slice(0,4) : n).forEach(function(it, j){
      var f=el('figure','aph-fig'); f.setAttribute('data-i', it.i);
      var b=figBtn(it,'th'); b.addEventListener('click', function(){ lightbox(all, j); }); f.appendChild(b);
      if(side && it.c) b.title=it.c;
      if(side && j===3 && all.length>4) b.appendChild(el('b','aph-n','+'+(all.length-4)));
      if(it.c) f.appendChild(el('figcaption','aph-cap',it.c));
      var ed=el('div','aph-ed'), ci=el('input'), ai=el('input');
      ci.type=ai.type='text'; ci.maxLength=200; ai.maxLength=300; ci.placeholder='Caption'; ai.placeholder='Alt text (what it shows, for screen readers)';
      ci.value=it.c||''; ai.value=it.a||''; ci.setAttribute('aria-label','Caption'); ai.setAttribute('aria-label','Alt text');
      function save(){ edit(function(l){ var x=l.filter(function(q){ return q.i===it.i; })[0]; if(!x) return false; var c=ci.value.trim(), a=ai.value.trim();
        if((x.c||'')===c && (x.a||'')===a) return false; if(c) x.c=c; else delete x.c; if(a) x.a=a; else delete x.a; }); }
      ci.addEventListener('change', save); ai.addEventListener('change', save);
      [ci,ai].forEach(function(i){ ['keydown','mousedown','click'].forEach(function(t){ i.addEventListener(t, function(e){ e.stopPropagation(); }); }); });
      ed.appendChild(ci); ed.appendChild(ai); f.appendChild(ed);
      var tl=el('span','aph-tools');
      [['‹','Move left',-1],['›','Move right',1],['✕','Remove this picture',0]].forEach(function(a){
        var t=el('button','',a[0]); t.type='button'; t.title=a[1]; t.setAttribute('aria-label',a[1]);
        t.addEventListener('click', function(e){ e.stopPropagation(); edit(function(l){
          var at=l.map(function(q){ return q.i; }).indexOf(it.i); if(at<0) return false;
          if(a[2]===0) l.splice(at,1); else { var to=at+a[2]; if(to<0||to>=l.length) return false; var q=l[at]; l[at]=l[to]; l[to]=q; } }); });
        tl.appendChild(t); });
      f.appendChild(tl);
      row.appendChild(f);
    });
    var add=el('button','aph-add'); add.type='button'; add.setAttribute('aria-label','Add pictures');
    var at1=el('span','','Add pictures'); at1.style.fontWeight='600';
    add.appendChild(el('b','','+')); add.appendChild(at1); add.appendChild(el('span','','choose files or drop them here'));
    var err=el('div','aph-err'); err.setAttribute('role','alert');
    function take(files){
      var a=acc(key); if(!a) return; var room=a.max-a.get().length;
      if(room<=0){ err.textContent='At most '+a.max+' pictures here.'; return; }
      err.textContent=''; add.disabled=true; at1.textContent='Adding…';
      addFiles(files, room, function(items, errs){
        add.disabled=false; at1.textContent='Add pictures';
        if(errs.length) err.textContent=errs.join(' ');
        if(items.length){ var a2=acc(key); if(a2) a2.set(a2.get().concat(items.map(function(it){ return {i:it.i, r:it.r}; }))); }
      });
    }
    add.addEventListener('click', function(e){ e.stopPropagation(); chooser(true, take); });
    add.addEventListener('dragover', function(e){ e.preventDefault(); add.classList.add('over'); });
    add.addEventListener('dragleave', function(){ add.classList.remove('over'); });
    add.addEventListener('drop', function(e){ e.preventDefault(); add.classList.remove('over'); var fs=e.dataTransfer && e.dataTransfer.files; if(fs && fs.length) take(fs); });
    row.appendChild(add); box.appendChild(err);
    return box;
  }
  function place(slot){
    var key=slot.getAttribute('data-aph'), D=S(key);
    if(!D){ slot.removeAttribute('data-aph'); return; }
    if(!D.n.length && !editing()) return;             // a Photos section with nothing in it yet shows only to its owner, editing
    var box=strip(key, D);
    var p=slot.parentNode, host=p && p.tagName==='P' ? p : null;
    if(host && host.parentNode){
      host.parentNode.insertBefore(box, host.nextSibling); slot.parentNode.removeChild(slot);
      if(!host.textContent.trim() && !host.querySelector('img,svg,.aed-k')) host.parentNode.removeChild(host);
    } else slot.parentNode.replaceChild(box, slot);
  }
  function scan(){ var s=document.querySelectorAll('.aph-slot[data-aph]'); for(var i=0;i<s.length;i++){ try{ place(s[i]); }catch(e){ if(window.console) console.warn('alto pics', e); } } }
  /* a section changed in edit mode: its row again, in place */
  API.sync=function(key){
    var old=document.querySelectorAll('.aph[data-aph-key="'+key+'"]');
    [].forEach.call(old, function(b){
      var D=S(key); if(!D){ return; }
      if(!D.n.length && !editing()){ var sl=el('span','aph-slot'); sl.setAttribute('data-aph',key); sl.hidden=true; b.parentNode.replaceChild(sl,b); return; }
      b.parentNode.replaceChild(strip(key, D, b.classList.contains('aph-top')), b);
    });
    if(!old.length) scan();
  };
  API.scan=scan;

  /* ── a card: its small picture with +n, and the pictures beside it when it is enlarged ── */
  function C(){ return window._ALTO_PC || {}; }
  function cardPics(id){ return C()[id] || null; }
  function decorateCard(id){
    var node=document.getElementById('node-'+id), card=node && node.querySelector('.node-card'); if(!card) return;
    var pics=cardPics(id), th=card.querySelector(':scope > .aph-thumb'), add=card.querySelector(':scope > .aph-cardadd');
    if(!pics || !pics.length){
      if(th) th.parentNode.removeChild(th); card.classList.remove('aph-has');
    } else {
      card.classList.add('aph-has');
      var sig=pics.map(function(q){ return q.r; }).join(',');
      if(!th || th.getAttribute('data-sig')!==sig){
        if(th) th.parentNode.removeChild(th);
        th=el('button','aph-thumb'); th.type='button'; th.setAttribute('data-sig', sig);
        th.setAttribute('aria-label', pics.length+' picture'+(pics.length>1?'s':'')+' — open'); th.title=pics.length+' picture'+(pics.length>1?'s':'');
        var im=el('img'); im.alt=''; im.draggable=false; th.appendChild(im); paint(im, null, pics[0].r, 'th');
        if(pics.length>1) th.appendChild(el('b','aph-n','+'+(pics.length-1)));
        ['mousedown','pointerdown','touchstart'].forEach(function(t){ th.addEventListener(t, function(e){ e.stopPropagation(); }); });
        th.addEventListener('click', function(e){ e.stopPropagation(); lightbox(cardPics(id)||[], 0); });
        card.appendChild(th);
      }
    }
    if(!add && editing() && !root.classList.contains('mobile')){
      add=el('button','aph-cardadd','＋'); add.type='button'; add.title='Add pictures to this card'; add.setAttribute('aria-label','Add pictures to this card');
      ['mousedown','pointerdown'].forEach(function(t){ add.addEventListener(t, function(e){ e.stopPropagation(); }); });
      add.addEventListener('click', function(e){ e.stopPropagation(); addToCard(id); });
      card.appendChild(add);
    } else if(add && !editing()) add.parentNode.removeChild(add);
  }
  function addToCard(id){
    var e=E(), f=e && e.field ? e.field('pc|'+id+'|pics') : null; if(!f) return;
    chooser(true, function(files){
      var cur=f.get()||[], room=MAXI_C-cur.length; if(room<=0){ say('A card holds at most '+MAXI_C+' pictures.'); return; }
      say('Adding…');
      addFiles(files, room, function(items, errs){
        if(errs.length) say(errs[0]);
        if(items.length){ var v=(f.get()||[]).concat(items.map(function(it){ return {i:it.i, r:it.r}; })); e.change('pc|'+id+'|pics', v); }
      });
    });
  }
  API.cards=function(){
    var all={}; Object.keys(C()).forEach(function(k){ all[k]=1; });
    [].forEach.call(document.querySelectorAll('.node-card.aph-has'), function(c){ var n=c.closest('.node'); if(n) all[(n.id||'').replace(/^node-/,'')]=1; });
    if(editing()) [].forEach.call(document.querySelectorAll('.node'), function(n){ all[(n.id||'').replace(/^node-/,'')]=1; });
    Object.keys(all).forEach(function(id){ if(id) decorateCard(id); });
  };
  /* the enlarged card: its pictures open beside it */
  function trayOff(){ [].forEach.call(document.querySelectorAll('.aph-tray'), function(t){ t.parentNode.removeChild(t); }); }
  function tray(){
    trayOff();
    var id=window._focusedNodeId, pics=id && cardPics(id); if(!pics || !pics.length || root.classList.contains('mobile')) return;
    var node=document.getElementById('node-'+id); if(!node) return;
    var t=el('div','aph-tray'); t.setAttribute('role','group'); t.setAttribute('aria-label','Pictures on this card');
    pics.slice(0,6).forEach(function(it, j){ var b=el('button'); b.type='button'; b.setAttribute('aria-label',(it.a||it.c||'Picture')+' — open large');
      var im=el('img'); im.alt=it.a||it.c||''; b.appendChild(im); paint(im,null,it.r,'th'); b.addEventListener('click', function(e){ e.stopPropagation(); lightbox(pics, j); }); t.appendChild(b); });
    var cap=pics.filter(function(q){ return q.c; }).map(function(q){ return q.c; }).join(' · '); if(cap) t.appendChild(el('div','aph-tc',cap));
    ['mousedown','pointerdown','click'].forEach(function(ev){ t.addEventListener(ev, function(e){ e.stopPropagation(); }); });
    var r=node.getBoundingClientRect(); if(r.right+330>window.innerWidth) t.classList.add('aph-left');
    node.appendChild(t);
  }
  API.tray=tray;
  function focusWatch(){
    var last=null, w=document.getElementById('world'); if(!w) return;
    new MutationObserver(function(){ var f=window._focusedNodeId||null; if(f!==last){ last=f; tray(); } }).observe(w, {subtree:true, attributes:true, attributeFilter:['class']});
  }

  /* ── a detail page: the card's pictures beside its title ── */
  function top(){
    var dc=document.getElementById('detail-content'); if(!dc) return;
    var P=window._altoPageNow || {type:window._currentDetailType, id:window._currentDetailId};
    var cur=dc.querySelector('.aph-top');
    if(!P || P.type!=='node' || !P.id){ if(cur) cur.parentNode.removeChild(cur); return; }
    var pics=cardPics(P.id) || [], nm=dc.querySelector('.detail-name');
    if(!nm || (!pics.length && !editing())){ if(cur) cur.parentNode.removeChild(cur); return; }
    var side=!editing() && !root.classList.contains('mobile'), key='pc|'+P.id, sig=key+JSON.stringify(pics)+(editing()?'e':'')+(side?'s':'');
    if(cur && cur.getAttribute('data-sig')===sig) return;
    if(cur) cur.parentNode.removeChild(cur);
    var box=strip(key, {lab:'', n:pics}, true, side); box.setAttribute('data-sig', sig);
    var h=nm.closest('.detail-header') || nm.parentNode;
    if(side) h.appendChild(box); else h.parentNode.insertBefore(box, h.nextSibling);
  }
  API.top=top;

  /* ── keeping up: details open, cards drawn, edit mode on or off ── */
  var q=false;
  function soon(){ if(q) return; q=true; Promise.resolve().then(function(){ q=false; scan(); top(); API.cards(); }); }
  API.refresh=soon;
  function watch(){
    var mo=new MutationObserver(function(ms){
      for(var i=0;i<ms.length;i++){ var a=ms[i].addedNodes;
        for(var j=0;j<a.length;j++){ var x=a[j];
          if(x.nodeType===1 && !(x.classList.contains('aph-thumb')||x.classList.contains('aph-tray')||x.classList.contains('aph-cardadd')||x.classList.contains('aph')) && (x.classList.contains('aph-slot')||x.classList.contains('node')||x.id==='detail-content'||x.querySelector('.aph-slot,.node,.detail-name'))){ soon(); return; } } }
    });
    var dp=document.getElementById('detail-page') || document.getElementById('detail-content');
    if(dp) mo.observe(dp, {childList:true, subtree:true});
    var w=document.getElementById('world'); if(w) mo.observe(w, {childList:true});
    new MutationObserver(function(){ soon(); }).observe(root, {attributes:true, attributeFilter:['class']});
    scan(); top(); API.cards(); focusWatch();
  }
  if(document.body) watch(); else document.addEventListener('DOMContentLoaded', watch);
  /* ── forgetting this browser's copies when the account signs out is alto-cloud.js's job ── */
  window.__GUARD__=API;
  window.addEventListener('alto-auth', function(){ soon(); });
})();
"""


# ───────────────────── the page's part of edit mode (spliced into manual_edit.MANUAL_JS) ─────────────────────
# `ph|<section key>|pics` a Photos section's whole list ({lab, n: [{i, r, c?, a?}]}), `pc|<card id>|pics` a card's [{i, r, c?, a?}].
# Everything that draws or adds is the hosted script; these two pieces only keep the data and say what to redraw.
EDIT_FIELD = r"""    if((kind === 'ph' || kind === 'pc') && p.length === 3 && p[2] === 'pics'){
      var PHD = window._ALTO_PH = window._ALTO_PH || {}, PCD = window._ALTO_PC = window._ALTO_PC || {};
      if(kind === 'pc'){
        if(!srcNode(id)) return null;
        return {kind:'list', get:function(){ return PCD[id] ? JSON.parse(JSON.stringify(PCD[id])) : []; },
          set:function(v){ if(v && v.length) PCD[id] = JSON.parse(JSON.stringify(v)); else delete PCD[id]; }};
      }
      if(NEWT.test(id)){
        if(!PHD[id] && !newTreeSec(id)) return null;
        return {kind:'struct', sig:function(){ return 'new'; },
          get:function(){ return PHD[id] ? JSON.parse(JSON.stringify(PHD[id])) : null; },
          set:function(v){ var q = newTreeSec(id);
            if(v){ PHD[id] = JSON.parse(JSON.stringify(v)); if(q) setSlot(q.s, id, true, 'aph'); }
            else { delete PHD[id]; if(q) setSlot(q.s, id, false, 'aph'); } }};
      }
      if(!PHD[id]) return null;
      return {kind:'struct', sig:function(){ return PRIS['ph|' + id]; },
        get:function(){ return JSON.parse(JSON.stringify(PHD[id])); },
        set:function(v){ PHD[id] = JSON.parse(JSON.stringify(v)); }};
    }
"""

EDIT_REFRESH = r"""    if(kind === 'ph' || kind === 'pc'){
      if(window._altoPicsLoad) window._altoPicsLoad();
      var PA = window._altoPics;
      if(kind === 'ph' && NEWT.test(p[1] || '')){ if(P){ rerenderPage(P); repaint(); } return; }
      if(PA){ if(kind === 'ph') PA.sync(p[1]); else { PA.cards(); PA.top(); if(PA.tray) PA.tray(); } }
      return;
    }
"""

MAX_FILE = 40 * 1024 * 1024          # a file larger than this is refused before it is opened
MAX_BIG = 900_000                    # the large size, bytes (one Firestore document holds it with room)

# SOLAR_JS is added by solar_pics.py (the System's rising panel); a page without a System has none.


def _asset() -> str:
    js = (PICS_JS.replace("__GUARD__", GUARD).replace("__MAXB__", str(MAX_BIG)).replace("__MAXF__", str(MAX_FILE))
          .replace("__MAXI__", str(MAX_ITEMS)).replace("__MAXC__", str(MAX_CARD))
          .replace("__CSS__", json.dumps(CSS)))
    return js


ASSET = _asset()
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-pics-{V}.js"


def pics_asset() -> tuple[str, str]:
    """(file name under /pics/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET
