"""City tiles (1.9.145): the Memory Palace's city geometry off the page, in hosted, content-hashed files the page loads.

A private page is one Firestore document (private_shell.MAX_PAGE_BYTES), and a city at full detail (all five boroughs of New York) is many
times that. So the page keeps only what the cards need (where each building stands, its floors and numbers), and the city comes from the site:

  base    /cmap/b-<h12>.json — one per build: the processed map of palace_data (window._ALTO_PALACE.m less its scalars, the lots `b`) and the
          fill-in of the zone (window._ALTO_FILL). Everything near the cards is here at full detail, so placing cards, routes, the ride and the
          first-person view never wait for anything. Fetched by a synchronous request (as the ride, the fleet and Retro are) before the palace
          script runs, answered from the browser's cache after the first visit; the palace script itself is unchanged.
  tiles   /cmap/t-<h10>.json — made at set_up, card-independent: the detail of one CELL x CELL page-px cell outside the zone (its block
          outlines, loose lines, minor streets, small parks and the fill-in's buildings). The page asks for the cells in view once the
          board is zoomed in to a few kilometres (TILES_JS) and draws them into the city's own layers.

`cut()` (set_up) splits a full map into the zone map (what data_z keeps) and the tiles (written to the blob folder, their hashes in
m["ct"]). `page_js()` (build) writes the base and returns the page's script: the base inline (timeline.html and the offline copy read it
from window._ALTO_CITY_F) between markers that `strip()` removes for the private and hosted pages, which load it from the site. A page
whose base cannot be loaded keeps its cards (P.none) and says the map did not load. `blobs()` lists what a publish puts in site/cmap/.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
from pathlib import Path

FOLDER = "cmap"
CELL = 2048                      # page px per tile cell side (about 1.4 km in New York's lattice)
ZONE_PAD = 2048                  # page px round the districts kept at full detail in the base (whole cells)
TE_LONG = 4000                   # page px: a loose line this long (about 2.5 km in New York) is a road drawn at every zoom (base)
PARK_SMALL = 2                   # a park of size class z at or under this outside the zone is drawn only close in (tiles) ...
PARK_BASE_PX2 = 5.0e6            # ... unless it is this big (page px^2, about 150 ha in New York): the big parks show at every zoom
BASE_MAX = 350 * 1024            # gzipped: the base is fetched before the palace draws (the build warns past it)
TILE_MAX = 64 * 1024             # gzipped: a tile over this is split into its four quarters
OFFLINE_REACH = 3                # cells round the zone an offline copy carries inline (past them it shows the base's overview)
VERSION = 1
BASE_RE = re.compile(r"^b-([0-9a-f]{12})\.json$")
TILE_RE = re.compile(r"^t-([0-9a-f]{10})\.json$")
MARK0, MARK1 = "/*<alto-cmap>*/", "/*</alto-cmap>*/"
PUBLISHED_LOG = "published-%s.txt"      # per site (ALTO_FIREBASE_SITE): a site publishes the bases its own pages named
RECENT_DAYS = 14                         # a base built this recently has its tiles on the tile host (palace_tiles.blobs)
# map keys that stay on the page: its scalars, and everything the user's own material decides (the landmark buildings they chose and the
# pages those open, the words across a river, hypothetical railways and their stops, the ships named after them) — the base on the site is
# only public geography (a file named by its hash, readable by anyone who has its name)
CORE_KEYS = ("v", "place", "scale", "attribution", "layout", "W", "H", "landmarks", "banners", "rails", "stations", "boats", "bases", "portals")


def tile_host() -> str:
    """Where the detail tiles are served from: ALTO_TILE_HOST (an https origin, e.g. the public Alto site that every user of this machine's
    sites shares; the tiles are card-independent geography, so one copy serves every palace and every build), else "" = the page's own
    site. The bases (one per page build) always stay on the page's own site."""
    return (os.environ.get("ALTO_TILE_HOST") or "").strip().rstrip("/")


def hosts_tiles(site: str = None) -> bool:
    """Does this deploy carry the tiles? With no tile host every site carries its own; with one, only the host's site does."""
    h = tile_host()
    site = site if site is not None else os.environ.get("ALTO_FIREBASE_SITE", "")
    return not h or h == "https://%s.web.app" % site or h == "https://%s.firebaseapp.com" % site


def blob_dir() -> Path:
    return Path(os.environ.get("ALTO_TILES_DIR") or (Path.home() / ".cache" / "alto" / FOLDER))


def text_of(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def digest(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def gz_len(text: str) -> int:
    return len(gzip.compress(text.encode("utf-8"), 6))


def store(name: str, text: str, directory=None) -> str:
    d = Path(directory) if directory else blob_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    if not p.is_file() or p.read_text("utf-8") != text:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(text, "utf-8")
        tmp.replace(p)
    return name


def read(name: str, directory=None):
    d = Path(directory) if directory else blob_dir()
    try:
        return (d / name).read_text("utf-8")
    except OSError:
        return None


# ── set_up: the full map -> the zone map + the tiles ──────────────────────
def zone_cells(m, districts) -> list:
    """[i0, j0, i1, j1]: the cells (inclusive) round every district's box plus ZONE_PAD; the whole map when there are no districts."""
    from . import palace_place as pp
    boxes = []
    for d in districts or ():
        try:
            boxes.append(pp.district_box(m, d))
        except Exception:                               # noqa: BLE001 — a district without bounds adds nothing
            continue
    W, H = float(m.get("W") or 0), float(m.get("H") or 0)
    if not boxes:
        return [0, 0, int(W // CELL), int(H // CELL)]
    x0 = min(b[0] for b in boxes) - ZONE_PAD
    y0 = min(b[1] for b in boxes) - ZONE_PAD
    x1 = max(b[2] for b in boxes) + ZONE_PAD
    y1 = max(b[3] for b in boxes) + ZONE_PAD
    return [max(0, int(x0 // CELL)), max(0, int(y0 // CELL)), int(x1 // CELL), int(y1 // CELL)]


def _cell(x, y):
    return int(math.floor(x / CELL)), int(math.floor(y / CELL))


def _inside(c, z):
    return z[0] <= c[0] <= z[2] and z[1] <= c[1] <= z[3]


def _plen(p):
    return sum(math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]) for i in range(0, len(p) - 3, 2))


def _area(r):
    n = len(r) // 2
    return abs(sum(r[2 * i] * r[2 * ((i + 1) % n) + 1] - r[2 * ((i + 1) % n)] * r[2 * i + 1] for i in range(n))) / 2


def _mid(p):
    n = len(p) // 2
    return p[2 * (n // 2)], p[2 * (n // 2) + 1]


def _ringc(a):
    n = len(a) // 2
    return sum(a[0::2]) / n, sum(a[1::2]) / n


def cell_of_fill(doms):
    """A function (dom, local x, local y) -> page cell, for the fill-in's records (palace_fillin.fill_data split=)."""
    def f(dk, x, y):
        d = doms[dk]
        a = math.radians(d[0])
        return _cell(x * math.cos(a) - y * math.sin(a) + d[1], x * math.sin(a) + y * math.cos(a) + d[2])
    return f


def cut(m, blocks, districts, fill=None, directory=None):
    """Split the full map in place: what lies outside the zone and is detail (block outlines, loose lines shorter than TE_LONG, streets
    of class k >= 2 that are no bridge or diagonal, small parks) moves into tiles, and so do the zone-less blocks' lots (none are kept:
    a card stands in the zone). fill: palace_fillin's {"parts": {cell: part}} (popped here) — each part joins its cell's tile.
    Writes the tiles and sets m["ct"]; returns (blocks kept, {"tiles": n, "bytes": gz total, "max": largest gz})."""
    z = zone_cells(m, districts)
    tiles: dict = {}

    def T(c):
        return tiles.setdefault(c, {})

    def put(c, key, item):
        T(c).setdefault(key, []).append(item)

    # a block or loose line the river runs through is drawn only as its dry pieces (palace_banks.cut_outlines): apply the cuts first,
    # so no index list has to survive the split
    for key, ck in (("tiles", "tcut"), ("edges", "ecut"), ("tq", "qcut")):
        cut_ = set(m.pop(ck, None) or ())
        if cut_ and m.get(key):
            m[key] = [v for i, v in enumerate(m[key]) if i not in cut_]
    for key in ("tiles", "edges"):
        keep = []
        for t in m.get(key) or []:
            c = _cell((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)
            (keep.append(t) if _inside(c, z) else put(c, key, t))
        if key in m:
            m[key] = keep
    keep = []
    for a in m.get("tq") or []:
        c = _cell(*_ringc(a))
        (keep.append(a) if _inside(c, z) else put(c, "tq", a))
    if "tq" in m:
        m["tq"] = keep
    keep = []
    for p in m.get("te") or []:
        if len(p) < 4:
            continue
        c = _cell(*_mid(p))
        (keep.append(p) if _inside(c, z) or _plen(p) >= TE_LONG else put(c, "te", p))
    if "te" in m:
        m["te"] = keep
    keep = []
    for s in m.get("streets") or []:
        p = s.get("p") or []
        c = _cell(*_mid(p)) if len(p) >= 2 else (0, 0)
        detail = s.get("k", 0) >= 2 and not s.get("o") and not s.get("t") and not s.get("hw")
        (put(c, "streets", s) if detail and not _inside(c, z) else keep.append(s))
    m["streets"] = keep
    keep, water = [], None
    for pk in m.get("parks") or []:
        rs = [r for r in pk.get("r") or [] if len(r) >= 6]
        c = _cell(*_ringc(rs[0])) if rs else (0, 0)
        big = (pk.get("z") or 0) > PARK_SMALL or sum(_area(r) for r in rs) >= PARK_BASE_PX2
        if rs and not big and not _inside(c, z):
            # a park bound for a tile is kept on dry land here (the base's parks are fitted at build: palace_parkfit, palace_data)
            if water is None:
                from .palace_parkfit import Water
                water = Water(m)
            from .palace_parks import _dry
            pk = _dry(dict(pk), water)
            if pk:
                put(c, "parks", pk)
        else:
            keep.append(pk)
    m["parks"] = keep
    for nm in m.pop("nb", None) or []:                  # the close-in neighbourhood names (city_outer_lattice): always tile detail
        put(_cell(nm["x"], nm["y"]), "nb", nm)
    blocks = [b for b in blocks or () if _inside(_cell(b["x"], b["y"]), z)] if blocks is not None else blocks
    for key, part in ((fill or {}).pop("parts", None) or {}).items():
        T(tuple(key) if not isinstance(key, str) else tuple(int(v) for v in key.split(",")))["f"] = part
    total, big = 0, 0
    for c, t in sorted(tiles.items()):
        for name, text, g in _emit(c, t):
            store(name, text, directory)
            total += g
            big = max(big, g)
    m["ct"] = {"v": VERSION, "cell": CELL, "zone": z, "c": _index()}
    return blocks, {"tiles": len(m["ct"]["c"]), "bytes": total, "max": big}


_EMITTED: dict = {}               # (cell key) -> tile name, of the last cut (the index)


def _emit(c, t, depth=0, key=None):
    """[(file name, text, gz bytes)] of one cell (a cell over TILE_MAX split into its four quarters, twice at most)."""
    key = key or "%d,%d" % c
    text = text_of({"v": VERSION, "k": key, **t})
    g = gz_len(text)
    if g <= TILE_MAX or depth >= 2:
        name = "t-%s.json" % digest(text, 10)
        _EMITTED[key] = name
        return [(name, text, g)]
    x0, y0 = c[0] * CELL / (2 ** depth), c[1] * CELL / (2 ** depth)
    half = CELL / (2 ** (depth + 1))
    quads = [{} for _ in range(4)]

    def qi(x, y):
        return (1 if x >= x0 + half else 0) + (2 if y >= y0 + half else 0)
    for k, items in t.items():
        if k == "f":
            quads[0]["f"] = items                        # the buildings stay together (one stream), in the first quarter
            continue
        for it in items:
            if k in ("tiles", "edges"):
                x, y = (it[0] + it[2]) / 2, (it[1] + it[3]) / 2
            elif k == "tq":
                x, y = _ringc(it)
            elif k == "te":
                x, y = _mid(it)
            elif k == "streets":
                x, y = _mid(it.get("p") or [x0, y0])
            elif k == "nb":
                x, y = it["x"], it["y"]
            else:
                rs = it.get("r") or [[x0, y0, x0, y0, x0, y0]]
                x, y = _ringc(rs[0])
            quads[qi(x, y)].setdefault(k, []).append(it)
    out = []
    for i, q in enumerate(quads):
        if q:
            sub = (c[0] * 2 + (i & 1), c[1] * 2 + (i >> 1))
            out += _emit(sub, q, depth + 1, key + "/" + str(i))
    return out


def _index() -> dict:
    """{cell key (or key/quarter): tile hash} of what _emit just wrote."""
    out = {}
    for k, name in sorted(_EMITTED.items()):
        out[k] = name[2:-5]
    _EMITTED.clear()
    return out


def tile_names(m) -> list:
    return ["t-%s.json" % h for h in sorted(set(((m or {}).get("ct") or {}).get("c", {}).values()))]


# ── build: the page's city, inline; the site's page: the base hosted ─────
def page_js(out: dict, fill, directory=None) -> str:
    """The palace's data as timeline.html and the offline copy carry it: window._ALTO_PALACE (and _ALTO_FILL) whole, as before, and the
    tiles within OFFLINE_REACH cells of the zone in window._ALTO_CITY_F, all between MARK0 and MARK1 (strip() makes the site's page)."""
    from .sanitize import js_json
    js = "\nwindow._ALTO_PALACE=" + js_json(out, separators=(",", ":")) + ";"
    if fill is not None:
        js += "\nwindow._ALTO_FILL=" + js_json(fill, separators=(",", ":")) + ";"
    inline = {}
    ct = (out.get("m") or {}).get("ct") or {}
    if ct.get("c"):
        z, R = ct.get("zone") or [0, 0, -1, -1], OFFLINE_REACH
        for k, h in sorted(ct["c"].items()):
            parts = k.split("/")
            i, j = (int(v) >> (len(parts) - 1) for v in parts[0].split(","))
            if z[0] - R <= i <= z[2] + R and z[1] - R <= j <= z[3] + R:
                txt = read("t-%s.json" % h, directory)
                if txt is not None:
                    inline["t-" + h] = json.loads(txt)
    if inline:
        js += "\nwindow._ALTO_CITY_F=" + js_json(inline, separators=(",", ":")) + ";"
    return MARK0 + js + "\n" + MARK1                  # (";\n" ends the data, as it always did: the tests and tools read it so)


# the site's page: the base, from the site, merged into window._ALTO_PALACE before the palace script reads it
LOADER_JS = r"""(function(){ var P=window._ALTO_PALACE; if(!P || !P.cb) return; var B=null;
  try{ var x=new XMLHttpRequest(); x.open('GET','/""" + FOLDER + r"""/'+P.cb+'.json',false); x.send(null); if(x.status===200 && x.responseText) B=JSON.parse(x.responseText); }catch(e){}
  if(!B || !B.m){ P.none=1; P.nomap=1; return; }
  for(var k in B.m) P.m[k]=B.m[k]; P.b=B.b||[]; if(B.f) window._ALTO_FILL=B.f; })();
"""
LAST_BASE: dict = {}              # the last strip(): {"name", "gz"} (the build report)


def _grab(block: str, name: str):
    k = block.find("window." + name + "=")
    if k < 0:
        return None
    return json.JSONDecoder().raw_decode(block, k + len("window." + name + "="))[0]


def strip(html: str, directory=None) -> str:
    """The page as the site serves it: the inline city (MARK0 .. MARK1) becomes the page's core (the cards' data and the map's scalars)
    and the loader; the rest of the map, the lots and the fill-in go to the base file in the blob folder (published under /cmap/)."""
    from .sanitize import js_json
    i = html.find(MARK0)
    if i < 0:
        return html
    j = html.find(MARK1, i)
    block = html[i + len(MARK0):j]
    out, fill = _grab(block, "_ALTO_PALACE"), _grab(block, "_ALTO_FILL")
    if not isinstance(out, dict) or not isinstance(out.get("m"), dict):
        return html[:i] + block + html[j + len(MARK1):]
    mp = out["m"]
    base = {"v": VERSION, "m": {k: v for k, v in mp.items() if k not in CORE_KEYS}, "b": out.get("b") or [], "f": fill}
    btext = text_of(base)
    name = "b-%s.json" % digest(btext, 12)
    store(name, btext, directory)
    LAST_BASE.clear()
    LAST_BASE.update({"name": name, "gz": gz_len(btext)})
    core = {**out, "m": {k: mp[k] for k in CORE_KEYS if k in mp}, "b": [], "cb": name[:-5], **({"cu": tile_host()} if tile_host() else {})}
    return html[:i] + "\nwindow._ALTO_PALACE=" + js_json(core, separators=(",", ":")) + ";\n" + LOADER_JS + html[j + len(MARK1):]


def page_refs(html: str) -> set:
    """The base files a built page names."""
    return {"b-%s.json" % h for h in re.findall(r'"cb":"b-([0-9a-f]{12})"', html or "")}


# ── publish: what goes into site/cmap/ ───────────────────────────────────
LAST_MISSING: list = []
LAST_PUBLISH: dict = {}           # what the last blobs() put in the deploy: counts and raw bytes of bases and tiles (the publish report)


def blobs(referenced=(), directory=None) -> list:
    """[(file name, text)]: every base a published page of this site names now or ever did (the folder's published-<site>.txt: a share is a
    copy of the page as it was, and still names its base) and every tile those bases name. A named file the folder lacks goes to LAST_MISSING."""
    LAST_MISSING.clear()
    d = Path(directory) if directory else blob_dir()
    log = d / (PUBLISHED_LOG % re.sub(r"[^a-z0-9-]", "", os.environ.get("ALTO_FIREBASE_SITE", "local").lower()) or "local")
    names = set(referenced or ())
    try:
        names |= {ln.strip() for ln in log.read_text("utf-8").splitlines() if ln.strip()}
    except OSError:
        pass
    names = {n for n in names if BASE_RE.match(n)}
    out, tiles = {}, set()
    for n in sorted(names):
        txt = read(n, d)
        if txt is None or digest(txt, 12) != BASE_RE.match(n).group(1):
            LAST_MISSING.append(n)
            continue
        out[n] = txt
        try:
            tiles |= set(tile_names(json.loads(txt).get("m")))
        except ValueError:
            pass
    if not hosts_tiles():
        tiles = set()                                   # the tiles live on the tile host (tile_host), not in this deploy
    elif tile_host():
        # the host carries the tiles of every base any site of this machine published (each published-<site>.txt) or built in the last
        # RECENT_DAYS (a page about to be published names a base built already: deploy the host first, then the page's site)
        import time as _t
        others = set()
        for lg in d.glob(PUBLISHED_LOG % "*"):
            try:
                others |= {ln.strip() for ln in lg.read_text("utf-8").splitlines() if BASE_RE.match(ln.strip())}
            except OSError:
                pass
        others |= {p.name for p in d.glob("b-*.json") if BASE_RE.match(p.name) and _t.time() - p.stat().st_mtime < RECENT_DAYS * 86400}
        for n in sorted(others - set(out)):
            txt = read(n, d)
            if txt is None:
                continue
            try:
                tiles |= set(tile_names(json.loads(txt).get("m")))
            except ValueError:
                pass
    LAST_PUBLISH.clear()
    for n in sorted(tiles):
        txt = read(n, d)
        if txt is None or digest(txt, 10) != TILE_RE.match(n).group(1):
            LAST_MISSING.append(n)
            continue
        out[n] = txt
    LAST_PUBLISH.update({"bases": sum(1 for k in out if BASE_RE.match(k)), "base_bytes": sum(len(v.encode()) for k, v in out.items() if BASE_RE.match(k)),
                         "tiles": sum(1 for k in out if TILE_RE.match(k)), "tile_bytes": sum(len(v.encode()) for k, v in out.items() if TILE_RE.match(k))})
    if referenced:
        try:
            d.mkdir(parents=True, exist_ok=True)
            old = log.read_text("utf-8").split() if log.is_file() else []
            new = [n for n in sorted(set(referenced)) if n not in old and n in out]
            if new:
                with log.open("a", encoding="utf-8") as f:
                    f.write("".join(n + "\n" for n in new))
        except OSError:
            pass
    return sorted(out.items())


def find(path: str, directory=None):
    """(content type, text) for /cmap/<name> from the blob folder (the QA kit's local server), else None."""
    p = path.split("?")[0]
    if not p.startswith("/" + FOLDER + "/"):
        return None
    n = p.rsplit("/", 1)[1]
    if not (BASE_RE.match(n) or TILE_RE.match(n)):
        return None
    txt = read(n, directory)
    return ("application/json; charset=utf-8", txt) if txt is not None else None


# ── the page: the detail tiles, loaded and drawn as the board is zoomed in (spliced into the palace's closure, palace.palace_js) ──
CT_ON = 7000                     # page px: a view this wide or narrower draws the detail tiles (about 5 km of New York)
CT_OFF = 9500                    # ... and one wider than this hides them again (between the two nothing changes)
CT_LITE = 30000                  # page px: up to this wide the tiles' blocks and parks are drawn (a borough's texture, lite) ...
CT_LITE_OFF = 38000              # ... and past this they go

# No standing opacity on a tile's groups: an SVG group with an opacity (or one being faded) is painted into its own transparency layer,
# again for every screen tile WebKit repaints (a pan with a dozen tiles cost 330 ms a frame). A tile fades in and out by a short inline
# opacity that is taken off when it ends; a hidden tile is display:none.
TILES_CSS = r"""
  .pal-svg g.ct.ct-off{display:none;}
"""
FADE_MS = 280
BUDGET_MS = 10                    # ms of tile drawing a frame (more tiles a frame once one is cheap: the lite ones)
SETTLE_MS = 300                   # ms a view must stay still before tiles are drawn, names fitted and buildings laid again

TILES_JS = r"""
/* ── city tiles (palace_tiles.py): the detail of the cells in view, fetched from /cmap/ once the board shows a few km, drawn into the
   city's own layers (parks, streets, names, hover lines) and its buildings into the fill-in; a cell far from the view leaves the board ── */
var CT=(M.ct&&M.ct.c)?M.ct:null, CTE=[], CTC={}, CTL=0, CTon={}, CTpend=[], CTraf=0, CTlbl=0, CTfill=0;
if(CT){ var CTS=CT.cell||2048; Object.keys(CT.c).forEach(function(k){ var q=k.split('/'), ij=q[0].split(','), i=+ij[0], j=+ij[1], s=CTS;
    /* a quarter (k "i,j/q/q"): its own finer cell */
    var x0=i*s, y0=j*s; for(var d=1;d<q.length;d++){ s/=2; x0+=(+q[d]&1)*s; y0+=(+q[d]>>1)*s; }
    CTE.push({k:k, h:CT.c[k], b:[x0, y0, x0+s, y0+s]}); }); }
function ctView(){ var cv=document.getElementById('canvas'), world=document.getElementById('world'); if(!cv || !world || !svgD || PV || Z==null) return null;
  var wr=world.getBoundingClientRect(), cr=cv.getBoundingClientRect(), k=(cr.width/cv.clientWidth)||1, pad=(typeof WORLD_PAD_TOP!=='undefined')?WORLD_PAD_TOP:0;
  var x0=(cr.left-wr.left)/k/Z-MX, y0=((cr.top-wr.top)/k-pad)/Z-MY; return [x0, y0, x0+cv.clientWidth/Z, y0+cv.clientHeight/Z]; }
function ctData(e){ var c=CTC[e.k]; if(!c){ c=CTC[e.k]={e:e, st:0, on:{}, g:{}, lv:{}};
    var F=window._ALTO_CITY_F||{}; if(F['t-'+e.h]){ c.d=F['t-'+e.h]; c.st=2; } }
  return c; }
function ctFetch(c){ c.st=1; CTL++;
  fetch((P.cu||'')+'/cmap/t-'+c.e.h+'.json').then(function(r){ return r.ok?r.json():null; }).then(function(d){ CTL--; c.d=d; c.st=d?2:3; ctTick(); })
    .catch(function(){ CTL--; c.st=3; }); }
/* where the city is shown now: the board (desktop) and the phone's map page, each with its view in map px */
function ctTargets(){ var t=[]; if(svgD && palaceOn()){ var v=ctView(); if(v) t.push([svgD, v]); }
  if(MM.svg && MM.box && MM.box.classList.contains('on') && typeof PM!=='undefined' && PM.W && PM.z){ var z=PM.z;
    t.push([MM.svg, [PM.sx/z-MX, PM.sy/z-MY, (PM.sx+PM.W)/z-MX, (PM.sy+PM.H)/z-MY]]); }
  return t; }
/* drawing a tile, fitting the names and laying the buildings again wait until the view has settled (docs/markers.md: layout once, after
   the gesture): while a pan or zoom runs, tiles are only fetched */
var CTmv=0, CTlast='';
function ctMoving(){ if(PV){ CTmv=performance.now(); return true; } return performance.now()-CTmv<CT_SETTLE; }   /* a zoom glide runs (PV) */
/* the close-in buildings' canvas (palace_fillin) is set aside while a zoom glide scales the board (WebKit re-scales a painted canvas of the
   window's size every frame: 350 ms a frame with a borough's buildings on it) and comes back, painted for the new zoom, when it settles */
var CTwo=null, CTwt=0;
function ctWatchZoom(){ if(CTwo) return; var w=document.getElementById('world'); if(!w) return;
  CTwo=new MutationObserver(function(){ var c=document.getElementById('pal-fillc'); if(!c) return;
    if(w.style.transform){ clearTimeout(CTwt); CTwt=0; c.style.visibility='hidden'; return; }
    /* back only once the board has stayed still a moment (a zoom that pauses between frames is laid out and goes on: painting the canvas
       at each such pause made the next frame slow, and the next) */
    if(c.style.visibility && !CTwt) CTwt=setTimeout(function(){ CTwt=0; if(w.style.transform) return; c.style.visibility=''; if(typeof fillSoon==='function') fillSoon(); }, CT_SETTLE+50); });
  CTwo.observe(w, {attributes:true, attributeFilter:['style']}); }
function ctTick(){ if(!CT) return; ctWatchZoom(); var tv=ctTargets(), key=tv.map(function(t){ return t[1].map(Math.round).join(','); }).join('|');
  if(key!==CTlast){ CTlast=key; CTmv=performance.now(); }
  CTpend=[];                                         /* what to draw is decided afresh each tick, nearest the view's middle first: never a queue of the last place's tiles */
  tv.forEach(function(t){ ctTick1(t[0], t[1]); }); if(CTpend.length && !CTraf && !ctMoving()) CTraf=requestAnimationFrame(ctStep); }
/* two levels: full (every part: names, hover lines, buildings) on a view CT_ON px wide or less, lite (blocks, loose lines and parks: the
   texture of a borough) up to CT_LITE; each level a held band (on below one width, off above a wider one: docs/markers.md) */
function ctTick1(svg, v){
  var sid=svg._sid||'', w=v[2]-v[0], was=CTon[sid]||0;
  var lv=CTon[sid]=(was===2?(w<=CT_OFF):(w<=CT_ON))?2:((was>=1?(w<=CT_LITE_OFF):(w<=CT_LITE))?1:0), on=lv>0;
  var cx=(v[0]+v[2])/2, cy=(v[1]+v[3])/2, m=CTS, near=[];
  CTE.forEach(function(e){ var b=e.b, c=CTC[e.k], inv=on && b[2]>v[0]-m && b[0]<v[2]+m && b[3]>v[1]-m && b[1]<v[3]+m;
    if(inv){ near.push(e); return; }
    if(c && c.on[sid]){ var far=!on || b[2]<v[0]-3*m || b[0]>v[2]+3*m || b[3]<v[1]-3*m || b[1]>v[3]+3*m; ctShow(c, svg, far?'drop':'hide'); } });
  near.sort(function(a,b){ return Math.hypot((a.b[0]+a.b[2])/2-cx,(a.b[1]+a.b[3])/2-cy)-Math.hypot((b.b[0]+b.b[2])/2-cx,(b.b[1]+b.b[3])/2-cy); });
  near.forEach(function(e){ var c=ctData(e);
    if(c.on[sid] && lv===2 && c.lv[sid]===1){ ctShow(c, svg, 'drop'); }                   /* lite -> full: drawn again, whole */
    if(c.st===0 && CTL<4) ctFetch(c);
    else if(c.st===2 && !c.on[sid]) CTpend.push([c, svg, lv]);
    else if(c.st===2 && c.g[sid] && c.g[sid][0] && c.g[sid][0].classList.contains('ct-off')) ctShow(c, svg, 'show'); }); }
/* tiles drawn a frame's budget at a time (CT_BUDGET ms), at least one */
function ctStep(){ CTraf=0; if(ctMoving()) return; var t0=performance.now(), n=0;
  while(CTpend.length && (n===0 || performance.now()-t0<CT_BUDGET)){ var q=CTpend.shift(), c=q[0], svg=q[1], sid=svg._sid||'';
    if(!c.on[sid] && svg.isConnected){ var lite=(CTon[sid]||0)<2; ctDraw(svg, c, true, lite); c.on[sid]=1; c.lv[sid]=lite?1:2; if(!lite) ctAfter(svg); n++; } }
  if(CTpend.length) CTraf=requestAnimationFrame(ctStep); }
/* a fade on the group's own inline opacity, taken off when it ends (no standing transparency layer: see TILES_CSS) */
function ctFade(g, to, done){ var t0=performance.now(), from=to?0:1;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches){ g.style.opacity=''; if(done) done(); return; }
  g.style.opacity=from; (function f(t){ var k=Math.min(1,(t-t0)/CT_FADE); g.style.opacity=from+(to-from)*k*k*(3-2*k);
    if(k<1) requestAnimationFrame(f); else { g.style.opacity=''; if(done) done(); } })(t0); }
function ctShow(c, svg, how){ var sid=svg._sid||''; var gs=c.g[sid]||[];
  if(how==='drop'){ gs.forEach(function(g){ if(g.parentNode) g.parentNode.removeChild(g); }); c.g[sid]=null; c.on[sid]=0; if(c.fs) ctFillSoon(); return; }
  var changed=0;
  gs.forEach(function(g){ var off=g.classList.contains('ct-off');                                   /* fade, never pop (docs/markers.md) */
    if(how==='hide' && !off && !g._fo){ changed=1; g._fo=1; ctFade(g, 0, function(){ g._fo=0; g.classList.add('ct-off'); }); }
    else if(how==='show' && off){ changed=1; g.classList.remove('ct-off'); ctFade(g, 1); } });
  if(changed && c.fs) ctFillSoon(); }
function ctAfter(svg){ clearTimeout(CTlbl); CTlbl=setTimeout(function(){ if(ctMoving()){ ctAfter(svg); return; } if(svg.isConnected){ try{ lblFit(svg, true); }catch(e){} } }, 200); }
/* the city's layers: the tile's groups go under what the base draws there (the base's major lines stay on top) */
function ctLayers(svg){ var lb=svg.querySelector(':scope > g > .pl-credit'); return {pk:svg.querySelector(':scope > .pl-parks'), st:svg.querySelector(':scope > .pl-streets'),
  lb:lb?lb.parentNode:null, hit:svg.querySelector(':scope > .pl-hits'), defs:svg.querySelector(':scope > defs')}; }
function ctG(parent, c, sid, fade, first){ var g=el('g',{'class':'ct', 'data-ct':c.e.k}); if(fade) g.style.opacity=0; if(first && parent.firstChild) parent.insertBefore(g, parent.firstChild); else parent.appendChild(g);
  (c.g[sid]=c.g[sid]||[]).push(g); return g; }
function ctRpc(a, r){ var n=a.length>>1, d=''; for(var i=0;i<n;i++){ var x=a[2*i], y=a[2*i+1], px=a[2*((i+n-1)%n)], py=a[2*((i+n-1)%n)+1], nx=a[2*((i+1)%n)], ny=a[2*((i+1)%n)+1],
    l1=Math.hypot(x-px,y-py)||1, l2=Math.hypot(nx-x,ny-y)||1, rr=Math.min(r,l1/2,l2/2), sx=x+(px-x)/l1*rr, sy=y+(py-y)/l1*rr;
    d+=(i?'L':'M')+sx+' '+sy+'Q'+x+' '+y+' '+(x+(nx-x)/l2*rr)+' '+(y+(ny-y)/l2*rr); } return d+'Z'; }
function ctTileD(t){ var x0=t[0], y0=t[1], x1=t[2], y1=t[3], r=Math.min(R, (x1-x0)/2, (y1-y0)/2);
  return 'M'+(x0+r)+' '+y0+'H'+(x1-r)+'Q'+x1+' '+y0+' '+x1+' '+(y0+r)+'V'+(y1-r)+'Q'+x1+' '+y1+' '+(x1-r)+' '+y1
    +'H'+(x0+r)+'Q'+x0+' '+y1+' '+x0+' '+(y1-r)+'V'+(y0+r)+'Q'+x0+' '+y0+' '+(x0+r)+' '+y0+'Z'; }
function ctDraw(svg, c, fade, lite){
  var T=c.d, L=ctLayers(svg), sid=svg._sid||''; if(!T || !L.st) return; c.g[sid]=[];
  if(T.parks && T.parks.length && L.pk){ var pg=ctG(L.pk, c, sid, fade, true);
    T.parks.forEach(function(pk){ var g=el('g',{'class':'pl-pk-g','data-name':pk.n||''},pg);
      el('path',{'class':'pl-pk', d:(pk.r||[]).map(function(r){ return ctRpc(r, R); }).join('')},g);
      (pk.p||[]).forEach(function(p){ el('path',{'class':'pl-pkp', d:rp(p)},g); });
      (pk.o||[]).forEach(function(o){ el('circle',{'class':'pl-pko', cx:o[0], cy:o[1], r:o[2]},g); }); }); }
  var byU={}, rings=[], heavy=[], sts=T.streets||[];
  (T.tiles||[]).forEach(function(t){ rings.push({t:t, c:[(t[0]+t[2])/2,(t[1]+t[3])/2]}); });
  (T.edges||[]).forEach(function(e){ var u=distAt((e[0]+e[2])/2,(e[1]+e[3])/2); byU[u]=(byU[u]||'')+'M'+e[0]+' '+e[1]+'L'+e[2]+' '+e[3]; });
  (T.tq||[]).forEach(function(a){ rings.push({q:a, c:ringC(a)}); });
  (T.te||[]).forEach(function(p){ if(p.length<4) return; var u=distAt((p[0]+p[p.length-2])/2,(p[1]+p[p.length-1])/2); byU[u]=(byU[u]||'')+rp(p); });
  sts.forEach(function(st){ if(st.L) for(var i=0;i+3<st.p.length;i+=2) heavy.push([st.p[i],st.p[i+1],st.p[i+2],st.p[i+3]]); });
  var sbk=superBlocks(rings, heavy);
  rings.forEach(function(r, i){ var u=distAt(r.c[0], r.c[1]), k=u+'|'+sbk[i]; byU[k]=(byU[k]||'')+(r.t?ctTileD(r.t):ctRpc(r.q, R)); });
  function tc(k){ var u=String(k).split('|')[0]; return tubeCol(dcol(u==='null'?null:+u)||NEUTRAL()); }
  var sg=ctG(L.st, c, sid, fade, true); stubes(sg, byU, tc, 3.6, 't-min');
  var byL={}; sts.forEach(function(st){ if(st.L) lruns(st.p).forEach(function(r){ byL[r.u]=(byL[r.u]||'')+rp(r.p); }); });
  if(Object.keys(byL).length) stubes(sg, byL, tc, 5.6, 't-maj');
  if(lite){ if(fade) (c.g[sid]||[]).forEach(function(g){ ctFade(g, 1); }); return; }
  var pkn=(T.parks||[]).filter(function(pk){ return pk.n && pk.t; }), nbs=T.nb||[];
  if(L.lb && (sts.length || pkn.length || nbs.length)){ var lg=ctG(L.lb, c, sid, fade), M0=M, mj=T.mj||sts.map(function(s){ return s.n; }).filter(Boolean);
    if(sts.length){ M={streets:sts, majors:mj, top:[]}; try{ streetLabels(svg, L.defs, lg); } finally { M=M0; } }
    pkn.forEach(function(pk){ var t=lbl(lg, 'pl-pkt', pk.n, pk.t[0], pk.t[1]); t._g=[pk.t[0], pk.t[1], 0]; t._up=.35; });
    nbs.forEach(function(a){ var t=el('text',{'class':'pl-area', x:a.x, y:a.y, 'text-anchor':'middle', 'data-r':4, 'aria-hidden':'true'},lg); t.textContent=a.n; t._g=[a.x, a.y, 0]; t._up=.35; }); }
  if(L.hit && sts.length){ var hg=ctG(L.hit, c, sid, false); sts.forEach(function(s){ if(!s.n || s.t) return; var h=el('path',{'class':'pl-hit', d:pts(s.p)},hg); h._n=s.n; }); }
  if(T.f && !c.fl){ c.fl=1; ctFillAdd(T.f, c); } else if(c.fs) ctFillSoon();
  if(fade) (c.g[sid]||[]).forEach(function(g){ ctFade(g, 1); });
}
/* a redrawn board (light/dark, a new map ground) draws the tiles it showed again */
function ctDrawAll(svg){ if(!CT) return; var sid=svg._sid||''; Object.keys(CTC).forEach(function(k){ var c=CTC[k]; if(c.on[sid]){ c.g[sid]=null; ctDraw(svg, c, false, c.lv[sid]===1); } }); }
/* the tile's buildings join the fill-in while the tile is shown, and leave it with the tile: the fill holds the page's own buildings and
   those of the tiles on the board, never every tile ever visited. Each keeps its own thinning rank (rk), so the set changing never
   reshuffles which buildings a slider share shows. */
var CTfs0=null;
function ctFillAdd(part, c){
  if(typeof fillShapes!=='function' || !FILL) return; var S0=fillShapes(); if(!S0) return;
  if(!CTfs0) CTfs0=S0.map(function(a){ return a?a.slice():a; });
  var F0=FILL; FILL={L:part.L, h:part.h, n:part.n, q:F0.q, doms:F0.doms, ch:F0.ch, c:part.c}; FS=null; var Sp;
  try{ Sp=fillShapes(); } finally { FILL=F0; FS=S0; }
  var seed=0; for(var i=0;i<c.e.k.length;i++) seed=(Math.imul(seed,31)+c.e.k.charCodeAt(i))|0;
  for(var lv=1;lv<=4;lv++) (Sp&&Sp[lv]||[]).forEach(function(sh,i){ sh.rk=((Math.imul(i+1+seed,2654435761)^Math.imul(lv,40503))>>>0)%1000/1000; });
  c.fs=Sp; ctFillSoon(); }
function ctFillSoon(){ clearTimeout(CTfill); CTfill=setTimeout(ctFillSet, 150); }
function ctFillSet(){ if(!CTfs0 || typeof fillShapes!=='function') return; if(ctMoving()){ ctFillSoon(); return; }
  var on=Object.keys(CTC).sort().map(function(k){ return CTC[k]; }).filter(function(c){ return c.fs && ['d','m'].some(function(k){ var g=c.on[k] && c.g[k] && c.g[k][0]; return g && c.lv[k]===2 && !g.classList.contains('ct-off') && !g._fo; }); });
  for(var lv=1;lv<=4;lv++){ var a=(CTfs0[lv]||[]).slice(); on.forEach(function(c){ if(c.fs[lv]) Array.prototype.push.apply(a, c.fs[lv]); }); FS[lv]=a; }
  FG=null; if(FC) FC.cache={}; if(svgD){ fillDraw(svgD); fillLOD(svgD); fillSoon(); } if(MM.svg){ fillDraw(MM.svg); fillLOD(MM.svg); } }
if(CT){ setInterval(function(){ if(!document.hidden) ctTick(); }, 250);
  /* other code (the ride, the first-person view) can ask for a box's tiles: their streets come back once drawn */
  window._altoCity={ensure:function(box, cb){ var n=0; CTE.forEach(function(e){ var b=e.b; if(b[2]>box[0] && b[0]<box[2] && b[3]>box[1] && b[1]<box[3]){ var c=ctData(e); if(c.st===0){ n++; ctFetch(c); } } });
      if(cb){ var t0=Date.now(); (function wait(){ var busy=CTE.some(function(e){ var c=CTC[e.k]; return c && c.st===1; }); if(busy && Date.now()-t0<8000) setTimeout(wait, 100); else cb(window._altoCity.streets(box)); })(); } return n; },
    streets:function(box){ var out=[]; Object.keys(CTC).forEach(function(k){ var c=CTC[k], b=c.e.b; if(c.d && b[2]>box[0] && b[0]<box[2] && b[3]>box[1] && b[1]<box[3]) out=out.concat(c.d.streets||[]); }); return out; },
    stats:function(){ var cv=document.getElementById('pal-fillc');
      var s={cells:CTE.length, loaded:0, drawn:0, inflight:CTL, pend:CTpend.length, on:CTon.d||0, fs:(typeof FS!=='undefined'&&FS)?FS.map(function(a){ return a?a.length:0; }):null,
             canvas:cv?{vis:cv.style.visibility, disp:cv.style.display, w:cv.width, painted:window._fillPaintMs}:null, lvl:(typeof fillLevel!=='undefined')?fillLevel:null}; Object.keys(CTC).forEach(function(k){ var c=CTC[k]; if(c.st===2) s.loaded++; if(c.on.d && c.g.d && c.g.d[0] && !c.g.d[0].classList.contains('ct-off')) s.drawn++; }); return s; }}; }
"""


# A city of several boroughs: the base's loose lines and heavy lines, grouped by district colour alone, made one path each that ran the
# length of the city, and WebKit strokes a whole path again for every screen tile it repaints (a pan cost 300 ms a frame). Each colour's
# lines are grouped per CHUNK px square as well (the chunk is part of the key; stubes colours by the part before "|").
CHUNK = 4096
_GROUP = (
    ("(M.te||[]).forEach(function(p){ if(p.length<4) return; var u=distAt((p[0]+p[p.length-2])/2,(p[1]+p[p.length-1])/2); byU[u]=(byU[u]||'')+rp(p); });",
     "(M.te||[]).forEach(function(p){ if(p.length<4) return; var u=distAt((p[0]+p[p.length-2])/2,(p[1]+p[p.length-1])/2)+ctChunk(p); byU[u]=(byU[u]||'')+rp(p); });"),
    ("if(hasL){ var byL={}; M.streets.forEach(function(st){ if(st.L) lruns(st.p).forEach(function(r){ byL[r.u]=(byL[r.u]||'')+rp(r.p); }); });",
     "if(hasL){ var byL={}; M.streets.forEach(function(st){ if(st.L) lruns(st.p).forEach(function(r){ var k=r.u+ctChunk(r.p); byL[k]=(byL[k]||'')+rp(r.p); }); });"),
)
CHUNK_JS = ("function ctChunk(p){ var n=p.length>>1, x=p[2*(n>>1)], y=p[2*(n>>1)+1]; return '|c'+Math.floor(x/" + str(CHUNK) +
            ")+','+Math.floor(y/" + str(CHUNK) + "); }\n")


def patch_js(js: str) -> str:
    """The palace script with the tiles' loader (only a palace whose map has m.ct with cells), and the base's lines grouped by chunk."""
    a = "window._altoPalace=function(h){"
    b = "  svg._b=bg; svg._r=route;"
    if js.count(a) != 1 or js.count(b) != 1 or any(js.count(o) != 1 for o, _n in _GROUP):
        raise ValueError("palace_tiles.patch_js: anchors not found")
    js = js.replace(a, TILES_JS.replace("CT_OFF", str(CT_OFF)).replace("CT_ON", str(CT_ON)).replace("CT_LITE_OFF", str(CT_LITE_OFF)).replace("CT_LITE", str(CT_LITE)).replace("CT_FADE", str(FADE_MS)).replace("CT_SETTLE", str(SETTLE_MS)).replace("CT_BUDGET", str(BUDGET_MS)) + CHUNK_JS + a)
    for o, n in _GROUP:
        js = js.replace(o, n)
    return js.replace(b, "  ctDrawAll(svg);\n" + b)
