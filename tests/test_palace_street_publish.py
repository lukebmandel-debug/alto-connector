"""2.0.0 review fixes 3, 4, 5, 7, 8, 9 around the street data: publishing every referenced manifest (two palaces over one box, a machine without the cache), the browser loader
(bad format, 404 / HTML, backoff, retries), the ride's retry / hold / note, the hosting cache headers, the OpenStreetMap credit and the real neighbourhood in the HUD."""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from alto.build import palace_assets, palace_ride, palace_ride_credit, palace_street as ps
from alto.build.palace import pack
from alto.build.palace_street_js import STREET_JS
from tests.test_palace_street import BBOX, BLD, ST, _geom, _sq

NODE = Path.home() / ".local" / "node" / "bin" / "node"
needs_node = pytest.mark.skipif(not NODE.exists(), reason="node not on this machine")

PLACES = [
    {"type": "node", "id": 900, "lat": 39.9500, "lon": -75.1700, "tags": {"place": "neighbourhood", "name": "Rittenhouse Test"}},
    {"type": "way", "id": 901, "geometry": _sq(39.9480, -75.1740, 0.004), "tags": {"place": "suburb", "name": "Big Suburb"}},
    {"type": "way", "id": 902, "geometry": _sq(39.9540, -75.1700, 0.001), "tags": {"place": "quarter", "name": "Small Quarter"}},
    {"type": "node", "id": 903, "lat": 39.9600, "lon": -75.1520, "tags": {"place": "city", "name": "Not A Neighbourhood"}},
    {"type": "node", "id": 904, "lat": 39.9601, "lon": -75.1521, "tags": {"place": "neighbourhood"}},               # no name: no label
]


def _two_palaces(extra=()):
    """Two manifests over the SAME box with different data, both stored in the (test) cache; returns their hashes."""
    st1 = {"elements": ST["elements"] + list(extra)}
    st2 = {"elements": ST["elements"][:6] + list(extra)}
    hs = []
    for st in (st1, st2):
        man, shards = ps.build(BBOX, BLD, st)
        hs.append(ps.store(man, shards))
    assert hs[0] != hs[1]
    return hs


def _age(h, days):
    p = ps.blob_dir() / ps.file_name(h)
    os.utime(p, (time.time() - days * 86400,) * 2)


def _palace(h):
    return {"data_z": pack({"map": {"street": {"h": h}}, "blocks": []})}


def _publish(tmp_path, hashes, site=None, name="store"):
    from alto.publish_static import regenerate_site
    from alto.store.local import LocalStore
    st = LocalStore(tmp_path / name)
    for i, h in enumerate(hashes):
        st.put_timeline("local", "t%d" % i, {"timeline_id": "t%d" % i, "project_id": "", "brief": {"palace": _palace(h)}, "status": "published", "visibility": "link"})
    return regenerate_site(st, "local", site or tmp_path / "site")


def _street(site):
    return {p.name for p in (site / "street").iterdir()} if (site / "street").is_dir() else set()


# ── 3: every referenced manifest is published ───────────────────────────────────────────────
def test_two_palaces_over_one_box_both_keep_their_street_data():
    h1, h2 = _two_palaces()
    _age(h1, 40); _age(h2, 40)                                     # (neither is recent: only a page naming it, or being its box's newest, keeps one)
    names = {n for n, _t in ps.blobs()}
    assert len([n for n in names if n.startswith("palace-street-")]) == 1             # nobody names them: the newest of the box stays, as before
    names = {n for n, _t in ps.blobs(referenced=[h1, h2])}
    for h in (h1, h2):
        man, shards = ps.load(h)
        assert ps.file_name(h) in names and all(ps.file_name(sid) in names for sid in shards)
    assert ps.LAST_MISSING == []


def test_the_site_publishes_both_palaces_streets_and_the_cache_is_not_the_only_copy(tmp_path):
    h1, h2 = _two_palaces()
    _age(h1, 40); _age(h2, 40)
    site = _publish(tmp_path, [h1, h2])
    got = _street(site)
    for h in (h1, h2):
        man, shards = ps.load(h)
        assert ps.file_name(h) in got and all(ps.file_name(sid) in got for sid in shards)
    from alto.publish_static import LAST_STALE
    assert LAST_STALE == []
    # a later publish by a palace that names only one drops the other's files only because nothing names them any more
    site = _publish(tmp_path, [h1], name="store2")
    assert ps.file_name(h1) in _street(site)


def test_a_machine_without_the_cache_keeps_what_the_site_has_and_says_when_it_cannot(tmp_path, monkeypatch):
    h1, h2 = _two_palaces()
    site = _publish(tmp_path, [h1, h2])
    before = _street(site)
    assert ps.file_name(h1) in before and ps.file_name(h2) in before
    # the cache folder is gone (another machine): the files already on the site are kept, nothing is dropped silently, nothing needs to be re-run
    monkeypatch.setenv("ALTO_STREET_DIR", str(tmp_path / "no-such-cache"))
    site = _publish(tmp_path, [h1, h2], name="store3")
    assert _street(site) == before
    from alto.publish_static import LAST_STALE
    assert LAST_STALE == []
    assert ps.LAST_MISSING == [ps.file_name(h1), ps.file_name(h2)] or sorted(ps.LAST_MISSING) == sorted([ps.file_name(h1), ps.file_name(h2)])
    # a fresh site on that machine: the data is nowhere, and the publish says so loudly (LAST_STALE blocks publish_timeline unless ALTO_ALLOW_STALE)
    fresh = _publish(tmp_path, [h1, h2], site=tmp_path / "site2", name="store4")
    assert _street(fresh) == set()
    assert any(ps.file_name(h1) in n and "street data" in n for n in LAST_STALE) and any(ps.file_name(h2) in n for n in LAST_STALE)


def test_a_missing_or_damaged_shard_of_a_referenced_manifest_is_reported(tmp_path):
    h1, _h2 = _two_palaces()
    man, shards = ps.load(h1)
    sid = sorted(shards)[0]
    (ps.blob_dir() / ps.file_name(sid)).write_text("damaged", "utf-8")
    names = {n for n, _t in ps.blobs(referenced=[h1])}
    assert ps.file_name(h1) in names and ps.file_name(sid) not in names
    assert ps.LAST_MISSING == [ps.file_name(sid)]
    ps.blobs()                                                    # (no page names it: nothing to report)
    assert ps.LAST_MISSING == []


def test_a_site_file_still_referenced_is_never_deleted_even_when_the_cache_has_a_newer_one(tmp_path):
    h1, h2 = _two_palaces()
    site = _publish(tmp_path, [h1])
    (site / "street" / "s-deadbeef.json").write_text("{}", "utf-8")            # nobody names it: swept
    site = _publish(tmp_path, [h1], name="store5")
    assert "s-deadbeef.json" not in _street(site) and ps.file_name(h1) in _street(site)


def test_street_hash_reads_the_pages_palace():
    h1, _ = _two_palaces()
    assert ps.street_hash(_palace(h1)) == h1 and ps.street_hash({}) == "" and ps.street_hash({"data_z": "junk"}) == ""
    assert ps.street_hash({"map": {"street": {"h": "../../etc/passwd"}}}) == ""


# ── 7: hosting cache headers ────────────────────────────────────────────────────────────────
def test_only_existing_street_files_are_kept_for_a_year_and_a_404_cannot_be(tmp_path):
    from alto.publish_static import _headers, _security_headers
    h1, h2 = _two_palaces()
    site = _publish(tmp_path, [h1, h2])
    heads = _security_headers(site)
    assert not any(h["source"] in ("/street/**", "/street/*", "**/street/**") for h in heads)            # no folder-wide rule: it would stamp the 404 page too
    rules = [h for h in heads if h["source"].startswith("/street/")]
    assert rules and all({"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in r["headers"] for r in rules)
    named = "|".join(r["source"] for r in rules)
    for n in _street(site):
        assert "/street/" + n in named.split("|")                                                              # one literal path per file
    assert "s-deadbeef" not in named and "*" not in named and "@(" not in named
    first = heads[0]
    assert first["source"] == "**" and {"key": "Cache-Control", "value": "no-cache"} in first["headers"]       # everything else under /street/ is no-cache
    assert heads.index(rules[0]) > 0                                                                          # after the default, so it wins for those files only
    # nothing of an unsafe shape reaches a glob; a site without the folder has no rule
    unsafe = [h["source"] for h in _headers("c", "c", ["../x.json", "s-zz.json", "a|b.json", "s-0123abcd.json"]) if h["source"].startswith("/street/")]
    assert unsafe == ["/street/s-0123abcd.json"]
    assert not [h for h in _headers("c", "c") if h["source"].startswith("/street")]
    assert not [h for h in _security_headers(tmp_path / "nope") if h["source"].startswith("/street")]


def test_the_ride_and_fleet_folders_keep_their_rules():
    from alto.publish_static import _headers
    heads = _headers("c", "c")
    for f in ("ride", "fleet"):
        assert any(h["source"] == "/%s/**" % f for h in heads)


# ── 9: place tags in the street data ────────────────────────────────────────────────────────
def test_places_are_written_to_the_manifest_without_touching_other_data():
    st = {"elements": ST["elements"] + PLACES}
    man, shards = ps.build(BBOX, BLD, st)
    man0, shards0 = ps.build(BBOX, BLD, ST)
    assert shards == shards0 and man["c"] == man0["c"]                        # places live in the manifest only
    names = sorted(p[0] for p in man["pl"])
    assert names == ["Big Suburb", "Rittenhouse Test", "Small Quarter"]       # place=city and an unnamed place are not neighbourhoods
    node = next(p for p in man["pl"] if p[0] == "Rittenhouse Test")
    assert node[4] == 0 and node[1] == ps.PLACES["neighbourhood"]
    poly = next(p for p in man["pl"] if p[0] == "Big Suburb")
    assert len(poly[4]) >= 6 and len(poly[4]) <= 2 * ps.MAX_RING
    assert "pl" not in man0
    assert "place" in ps.street_query((39.95, -75.17, 39.96, -75.16)) and "neighbourhood|suburb|quarter" in ps.street_query((39.95, -75.17, 39.96, -75.16))


def _js(tmp_path, body, files=None):
    (tmp_path / "street.js").write_text(STREET_JS, "utf-8")
    for k, v in (files or {}).items():
        (tmp_path / k).write_text(v, "utf-8")
    (tmp_path / "probe.js").write_text("global.window = global; const fs = require('fs');\n" + body, "utf-8")
    r = subprocess.run([str(NODE), "probe.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


_MOCK = """
let NOW = 1e6; Date.now = () => NOW;                                       // (the jitter comes from the clock: 0.75-1.25)
const RESP = {}; const LOG = [];
let HOLD = 0, ACTIVE = 0, PEAK = 0;
global.fetch = (u) => { const f = u.split('/').pop(); LOG.push(f); const r = RESP[f];
  return new Promise(res => { ACTIVE++; PEAK = Math.max(PEAK, ACTIVE); setTimeout(() => { ACTIVE--;
    if (!r) return res({ok: false, status: 404, text: () => Promise.resolve('<html>not found</html>')});
    res({ok: r.ok !== false, status: r.status || 200, headers: {get: () => r.ct || 'application/json'}, text: () => Promise.resolve(r.body)}); }, HOLD); }); };
require('./street.js');
const P = _palStreet;
"""


@needs_node
def test_the_loader_survives_bad_files_backs_off_and_retries(tmp_path):
    st = {"elements": ST["elements"] + PLACES}
    man, shards = ps.build(BBOX, BLD, st)
    sid = sorted(shards)[0]
    body = _MOCK + """
const M = JSON.parse(fs.readFileSync('man.json', 'utf8')), SH = JSON.parse(fs.readFileSync('sh.json', 'utf8')), SID = %s;
const out = {};
const ok = async (p) => { try { await p; return true; } catch (e) { return String(e.message); } };
(async () => {
  // a manifest that is HTML (a 200 from a rewrite), then not valid, then the wrong shape: each fails without throwing, nothing stays cached
  RESP['m.json'] = {body: '<!doctype html><html></html>'};
  out.html = await ok(P.load('/street/m.json'));
  out.afterHtml = await ok(P.load('/street/m.json'));                      // inside the backoff: rejected at once, no request
  out.logAfterBackoffCall = LOG.length;
  NOW += 2600; RESP['m.json'] = {body: '{"v":2,"c":{}}'};
  out.shape = await ok(P.load('/street/m.json'));
  NOW += 5100; RESP['m.json'] = {body: '{broken'};
  out.json = await ok(P.load('/street/m.json'));
  NOW += 10100; RESP['m.json'] = {body: JSON.stringify(M), ct: 'text/html'};
  out.ct = await ok(P.load('/street/m.json'));
  NOW += 20100; RESP['m.json'] = {body: JSON.stringify(M)};
  out.good = await ok(P.load('/street/m.json'));                             // it recovers: the failed promises were not cached
  out.ready = P.ready();
  // a shard: 404, then a wrong format, then fine
  const x = (-75.1700 - M.o[1]) * M.kx, y = (39.9500 - M.o[0]) * M.ky;
  const ids = Object.keys(M.f);
  out.n404 = await ok(P.need(x, y, 40));
  out.h1 = P.health();
  out.wait = await ok(P.need(x, y, 40));                                     // inside the backoff: no request
  NOW += 70000;
  ids.forEach(i => { RESP['s-' + i + '.json'] = {body: '{"S":"x","c":{}}'}; });
  out.bad = await ok(P.need(x, y, 40));
  NOW += 70000;
  ids.forEach(i => { RESP['s-' + i + '.json'] = {body: JSON.stringify(SH[i] || SH[SID])}; });
  Object.keys(M.f).forEach(i => { RESP['s-' + i + '.json'] = {body: fs.readFileSync('s-' + i + '.json', 'utf8')}; });
  out.shardGood = await ok(P.need(x, y, 40));
  out.loaded = P.loaded(x, y, 40);
  out.place = [P.place(x, y), P.place(-75.1700 > 0 ? 0 : (-75.1650 - M.o[1]) * M.kx, (39.9545 - M.o[0]) * M.ky), P.place(1e6, 1e6)];
  out.attr = P.attribution();
  out.healthEnd = P.health();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
""" % json.dumps(sid)
    files = {"man.json": ps.encode(man), "sh.json": json.dumps({k: v for k, v in shards.items()})}
    for k, v in shards.items():
        files["s-%s.json" % k] = ps.encode(v)
    js = _js(tmp_path, body, files)
    assert js["html"] == "street html" and js["afterHtml"].startswith("street: wait") and js["logAfterBackoffCall"] == 1
    assert js["shape"] == "street format" and js["json"] == "street json" and js["ct"] == "street html"
    assert js["good"] is True and js["ready"] is True
    assert js["n404"] == "street 404" and js["h1"]["fails"] >= 1 and js["h1"]["wait"] > 0 and js["wait"].startswith("street: wait")
    assert js["bad"] == "street format"
    assert js["shardGood"] is True and js["loaded"] is True
    assert js["place"][0] == "Rittenhouse Test" or js["place"][0] == "Big Suburb"          # the node is only used when no outline holds the point; the suburb outline holds it
    assert js["place"][2] == "" and js["attr"] == ps.ATTRIBUTION


@needs_node
def test_a_loader_failure_never_throws_and_requests_are_capped(tmp_path):
    st = {"elements": ST["elements"] + PLACES}
    man, shards = ps.build(BBOX, BLD, st)
    body = _MOCK.replace("let HOLD = 0", "let HOLD = 5") + """
const M = JSON.parse(fs.readFileSync('man.json', 'utf8'));
const out = {};
(async () => {
  // fetch itself throws: a rejection, not an exception
  const f0 = global.fetch; global.fetch = () => { throw new Error('boom'); };
  try { await P.load('/street/m.json'); out.thrown = 'resolved'; } catch (e) { out.thrown = e.message; }
  global.fetch = f0; NOW += 5000;
  RESP['m.json'] = {body: JSON.stringify(M)};
  await P.load('/street/m.json');
  Object.keys(M.f).forEach(i => { RESP['s-' + i + '.json'] = {body: fs.readFileSync('s-' + i + '.json', 'utf8')}; });
  // everything at once: no more than four requests are ever in flight
  const mid = (M.n[0] * M.cs * M.q) / 2, midy = (M.n[1] * M.cs * M.q) / 2;
  await P.need(mid, midy, 1e6);
  out.peak = PEAK; out.shards = Object.keys(M.f).length; out.loaded = P.loaded(mid, midy, 1e6);
  // a bad manifest cannot be used
  try { P.use({v: 2}); out.use = 'ok'; } catch (e) { out.use = e.message; }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""
    files = {"man.json": ps.encode(man)}
    for k, v in shards.items():
        files["s-%s.json" % k] = ps.encode(v)
    js = _js(tmp_path, body, files)
    assert js["thrown"] == "street fetch" and js["peak"] <= 4 and js["loaded"] is True and js["use"] == "street manifest"


# ── 4: the ride's retry / hold / note ───────────────────────────────────────────────────────
def _rwl_region():
    from alto.build.palace_ride_e import JS_E
    a = JS_E.index("/*@RWL-begin")
    b = JS_E.index("/*@RWL-end@*/")
    return JS_E[a:b], JS_E


@needs_node
def test_the_ride_backs_off_caps_requests_holds_the_walker_and_shows_a_note(tmp_path):
    region, jse = _rwl_region()
    a = jse.index("function realPrefetch(){")                                       # the real prefetch (it honours the same backoff) and the real stream
    stream = jse[a:jse.index("function realBound(dt){")]
    harness = r"""
global.window = global;
let T = 0; global.performance = {now: () => T};
const UM = 1.3; let OK = false, CALLS = 0, GATHERS = 0, PENDING = [];
const REAL = {street: () => true, on: true, chunks: {}, have: [[0, 0, 720]], prepare: () => { CALLS++; return new Promise((res, rej) => PENDING.push([res, rej])); }};
const S = {x: 0, y: 0, vx: 3, vy: 0, yaw: 0, real: true, on: true, hud: {root: null}};
const RW = {R: 420, PR: 720, regather: 105, busy: false, gen: null, cx: 0, cy: 0};
function blockedAt() { return false; }
function realNear(rx, ry) { return OK; }
function realGather() { GATHERS++; } function realGatherStep() { GATHERS++; }
const els = []; global.document = {createElement: (t) => { const e = {style: {}, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, offsetHeight: 0, parentNode: null}; els.push(e); return e; }};
S.hud.root = {appendChild(e) { e.parentNode = this; }};
""" + region + "\n" + stream + r"""
const out = {};
const flush = () => new Promise(r => setImmediate(r));
(async () => {
  // the walker is 200 m out from the built world's centre and the data is missing
  S.x = 200 * UM; S.y = 0;
  realStream(false); out.calls1 = CALLS; realStream(false); out.calls1b = CALLS;                // one load in flight: no second request
  PENDING[0][1](new Error('street 404')); await flush();
  out.fails1 = RWL.fails; const gap1 = RWL.retryAt - T;
  for (let i = 0; i < 50; i++) { T += 16; realStream(false); }
  out.callsDuringBackoff = CALLS;                                                            // 50 frames inside the 2 s backoff: no request
  T = RWL.retryAt + 1; realStream(false); out.calls2 = CALLS;
  PENDING[1][1](new Error('street 404')); await flush(); const gap2 = RWL.retryAt - T;
  T = RWL.retryAt + 1; realStream(false); PENDING[2][1](new Error('x')); await flush(); const gap3 = RWL.retryAt - T;
  out.gaps = [gap1, gap2, gap3].map(Math.round); out.tries = RWL.tries;
  for (let i = 0; i < 12; i++) { T = RWL.retryAt + 1; realStream(false); PENDING[PENDING.length - 1][1](new Error('x')); await flush(); }
  out.cap = RWL.retryAt - T;                                                                  // never more than 60 s (+25%)
  // a loader that is itself backing off passes its wait on; no second backoff is stacked
  const f0 = RWL.fails; T = RWL.retryAt + 1; realStream(false); const e = new Error('w'); e.wait = 5000; PENDING[PENDING.length - 1][1](e); await flush();
  out.stacked = RWL.fails - f0; out.waitHonoured = Math.round(RWL.retryAt - T);
  // the walker is held inside the built world: far out, the position is pulled back to the rim and the speed is spent
  S.x = 600 * UM; S.y = 0; S.vx = 5; T += 100; realStream(false);
  out.heldAt = Math.round(S.x / UM); out.held = RWL.held; out.vx = S.vx;
  out.note = {text: els.find(e => e.className === 'rm-load').textContent, opacity: els.find(e => e.className === 'rm-load').style.opacity};
  // nearer the centre they are only slowed gently
  S.x = 250 * UM; S.vx = 3; T += 100; realStream(false); out.slow = [S.vx > 2.2 && S.vx < 3, Math.round(S.x / UM)];
  // the data arrives: no hold, the note fades, and a good load resets the counters
  OK = true; S.x = 600 * UM; S.vx = 5; T += 100; realStream(false);
  out.freeX = Math.round(S.x / UM); out.noteGone = els.find(e => e.className === 'rm-load').style.opacity;
  OK = false; RWL.fails = 3; RWL.retryAt = 0; RW.busy = false; S.x = 200 * UM; realStream(false); PENDING[PENDING.length - 1][0](true); await flush(); out.reset = [RWL.fails, RWL.retryAt];
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""
    (tmp_path / "h.js").write_text(harness, "utf-8")
    r = subprocess.run([str(NODE), "h.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    assert o["calls1"] == 1 and o["calls1b"] == 1 and o["fails1"] == 1
    assert o["callsDuringBackoff"] == 1 and o["calls2"] == 2
    assert o["tries"] == 3 and all(base * 0.75 - 1 <= g <= base * 1.25 + 1 for g, base in zip(o["gaps"], (2000, 4000, 8000)))      # 2 s, 4 s, 8 s, +-25%
    assert o["gaps"][0] < o["gaps"][1] < o["gaps"][2]
    assert 60000 * 0.75 - 1 <= o["cap"] <= 60000 * 1.25 + 1
    assert o["stacked"] == 0 and o["waitHonoured"] == 5000
    assert o["heldAt"] <= 420 - 44 and o["heldAt"] >= 420 - 46 and o["held"] is True and o["vx"] <= 1.1
    assert o["note"]["text"] == "loading the street…" or "not reachable" in o["note"]["text"]
    assert o["note"]["opacity"] == ".9" and o["slow"][0] is True
    assert o["freeX"] == 600 and o["noteGone"] == "0" and o["reset"] == [0, 0]


def test_the_ride_edit_is_fenced_and_small():
    region, jse = _rwl_region()
    assert region.count("function realLoad") == 1 and "RW.retry=RWL" in region and "textContent" in region and "innerHTML" not in region


# ── 8: the credit and 9: the real neighbourhood ─────────────────────────────────────────────
def test_the_credit_is_in_the_ride_and_is_text_only():
    js = palace_ride.RIDE_JS
    assert palace_ride_credit.JS_CREDIT in js and js.index(palace_ride_credit.JS_CREDIT) > js.index("REAL.fromStreet")
    c = palace_ride_credit.JS_CREDIT
    assert "https://www.openstreetmap.org/copyright" in c and "a.target='_blank'" in c and "a.rel='noopener'" in c and "a.textContent" in c and "innerHTML" not in c
    assert "_palStreet.attribution()" in c and "pr-credit" in palace_ride_credit.CSS_CREDIT and "hudFrame" not in c
    assert len(palace_ride_credit.JS_CREDIT) < 7500


@needs_node
def test_the_hud_shows_the_credit_and_the_real_neighbourhood_only_with_street_data(tmp_path):
    harness = r"""
global.window = global; let T = 0; global.performance = {now: () => T};
const els = {}; const OBS = [];
const mk = (tag, cls) => { const e = {tag, style: {}, classes: new Set(cls ? [cls] : []), children: [], textContent: '', parentNode: null, tabIndex: 0,
  classList: {contains: (c) => e.classes.has(c), toggle: (c, on) => { on ? e.classes.add(c) : e.classes.delete(c); }}, appendChild(c) { c.parentNode = e; e.children.push(c); },
  querySelector(q) { return e.kids && e.kids[q] || null; }}; return e; };
const root = mk('div'); root.classes.add('on'); root.id = 'pal-ride';
const AR = mk('em'), LIVE = mk('div'); root.kids = {'.rm-ar': AR, '.rm-live': LIVE};
global.document = {getElementById: (id) => id === 'pal-ride' ? root : (id === 'pal-credit-css' ? els.css || null : null), createElement: (t) => mk(t), head: {appendChild: (e) => { els.css = e; }}};
global.MutationObserver = function (cb) { this.cb = cb; OBS.push(this); this.observe = () => {}; };
global.setInterval = (f) => { global.tick = f; return 1; };
const UM = 1.3; const REAL = {on: true, src: 'street', isOn: () => true};
let PLACE = 'Society Hill Real', ACTIVE = true, REALWALK = true, X = 100 * UM;
const ROAM = {active: () => ACTIVE, state: () => ({real: REALWALK, x: X, y: 100 * UM})};
window._palStreet = {ready: () => true, attribution: () => '\u00a9 OpenStreetMap contributors, ODbL', place: (x, y) => PLACE, toMap: () => [0, 1000]};
// what the HUD does: writes the palace district into the third line (and the live region) and fires the observer
const hud = (district) => { AR.textContent = district; AR.style.display = district ? '' : 'none'; LIVE.textContent = 'Broad St, at Fitzwater. ' + district; OBS.forEach(o => o.cb()); };
""" + palace_ride_credit.JS_CREDIT + r"""
const out = {};
tick(); const a = root.children[0];
out.credit = {text: a.textContent, href: a.href, target: a.target, rel: a.rel, on: a.classes.has('on'), css: !!els.css && els.css.textContent.indexOf('.pr-credit') > 0};
hud('Spring Garden');
out.real = [AR.textContent, AR.style.display, LIVE.textContent];
PLACE = ''; T += 3000; X += 50 * UM; hud('Spring Garden');
out.none = [AR.textContent, AR.style.display, LIVE.textContent];                                   // the data has no neighbourhood here: the line is dropped, not wrong
PLACE = 'Fishtown Real'; T += 3000; X += 50 * UM; tick();
out.moved = AR.textContent;
// the lattice walk (not a real walk): the district the HUD wrote last stands again
REALWALK = false; hud('Spring Garden'); out.lattice = [AR.textContent, AR.style.display];
REALWALK = true; tick(); REALWALK = false; tick();
out.back = [AR.textContent, AR.style.display];
// street data gone, then the ride closed: the credit hides
REAL.src = ''; tick(); out.hidden = !a.classes.has('on');
REAL.src = 'street'; root.classes.delete('on'); tick(); out.offRide = !a.classes.has('on');
process.stdout.write(JSON.stringify(out));
"""
    (tmp_path / "c.js").write_text(harness, "utf-8")
    r = subprocess.run([str(NODE), "c.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    assert o["credit"] == {"text": "\u00a9 OpenStreetMap contributors, ODbL", "href": "https://www.openstreetmap.org/copyright", "target": "_blank", "rel": "noopener", "on": True, "css": True}
    assert o["real"] == ["Society Hill Real", "", "Broad St, at Fitzwater. Society Hill Real"]
    assert o["none"] == ["", "none", "Broad St, at Fitzwater"]
    assert o["moved"] == "Fishtown Real"
    assert o["lattice"] == ["Spring Garden", ""] and o["back"] == ["Spring Garden", ""]
    assert o["hidden"] is True and o["offRide"] is True
