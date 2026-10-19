"""Overpass resilience: every public mirror tried in turn (palace_map._post_overpass), the names query asked in
tiles x chunks and merged (city_setup.fetch_names), and set_up_palace saying which server answered (map_source).
No network: urllib.request.urlopen is replaced by a fake that answers per server."""
import io
import json
import urllib.error

import pytest

from alto import palace_map as pm
from alto.build import city_setup as cs

DE, KUMI, FR, RU, COFFEE = pm.OVERPASS_MIRRORS
BB = (40.70, -74.02, 40.76, -73.95)                 # ~6.7 x 5.9 km of Manhattan: 3 x 3 names tiles


def host(u):
    return u.split("/")[2]


def fake_servers(monkeypatch, behaviour, calls=None):
    """behaviour: {url: callable(req) -> bytes | raises}; a url not listed answers an empty result."""
    calls = [] if calls is None else calls

    def urlopen(req, timeout=0, **kw):
        assert kw.get("context") is pm._tls()
        calls.append(req.full_url)
        f = behaviour.get(req.full_url)
        return io.BytesIO(f(req) if f else b'{"elements": []}')

    monkeypatch.setattr(pm.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(pm, "_sleep", lambda s: None)
    return calls


def http(code):
    def f(req):
        raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b""))
    return f


def refused(req):
    raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


def ok(elements):
    return lambda req: json.dumps({"elements": elements}).encode()


# ── mirrors ─────────────────────────────────────────────────────────────────
def test_the_mirror_list_is_the_five_public_servers_in_order():
    assert [host(u) for u in pm.OVERPASS_MIRRORS] == [
        "overpass-api.de", "overpass.kumi.systems", "overpass.openstreetmap.fr", "maps.mail.ru",
        "overpass.private.coffee"]
    assert pm.OVERPASS_MIRRORS[3].endswith("/osm/tools/overpass/api/interpreter")


def test_primary_fails_then_a_fallback_answers_and_the_report_names_it(monkeypatch):
    calls = fake_servers(monkeypatch, {DE: http(504), KUMI: refused, FR: ok([{"type": "node", "id": 1}])})
    mark = pm.overpass_mark()
    assert pm._post_overpass("q", 10) == {"elements": [{"type": "node", "id": 1}]}
    assert calls == [DE, DE, KUMI, FR]                       # busy: once more; refused: straight on
    rep = pm.overpass_report(mark)
    assert rep["requests"] == 1 and rep["served_by"] == {"overpass.openstreetmap.fr": 1}
    assert rep["failed"]["overpass-api.de"] == {"n": 2, "last": "HTTP 504"}
    assert "refused" in rep["failed"]["overpass.kumi.systems"]["last"]
    assert "unanswered" not in rep


def test_the_server_that_answered_goes_first_and_a_failed_one_waits_at_the_back(monkeypatch):
    calls = fake_servers(monkeypatch, {DE: http(503), KUMI: http(500)})
    pm._post_overpass("q", 10)
    assert calls == [DE, DE, KUMI, FR]
    calls.clear()
    pm._post_overpass("q", 10)
    assert calls == [FR]                                     # no time lost on the two that just failed
    assert pm.overpass_mirrors() == [FR, RU, COFFEE, DE, KUMI]


def test_an_html_page_or_a_partial_answer_moves_on(monkeypatch):
    calls = fake_servers(monkeypatch, {
        DE: lambda req: b"<html>Gateway</html>",
        KUMI: lambda req: b'{"elements": [], "remark": "runtime error: Query timed out"}',
        FR: lambda req: b"[]",
    })
    assert pm._post_overpass("q", 10) == {"elements": []}
    assert calls == [DE, KUMI, FR, RU]


def test_every_server_failing_raises_naming_each_and_counts_unanswered(monkeypatch):
    fake_servers(monkeypatch, {u: refused for u in pm.OVERPASS_MIRRORS})
    mark = pm.overpass_mark()
    with pytest.raises(RuntimeError) as e:
        pm._post_overpass("q", 10)
    for u in pm.OVERPASS_MIRRORS:
        assert host(u) in str(e.value)
    rep = pm.overpass_report(mark)
    assert rep["requests"] == 0 and rep["unanswered"] == 1 and len(rep["failed"]) == 5


def test_a_bad_query_does_not_put_a_server_at_the_back(monkeypatch):
    fake_servers(monkeypatch, {u: http(400) for u in pm.OVERPASS_MIRRORS})
    with pytest.raises(RuntimeError):
        pm._post_overpass("q", 10)
    assert pm.overpass_mirrors()[0] == DE


def test_alto_overpass_url_puts_the_users_own_server_first(monkeypatch):
    monkeypatch.setenv("ALTO_OVERPASS_URL", "https://my.overpass/api/interpreter")
    calls = fake_servers(monkeypatch, {})
    pm._post_overpass("q", 10)
    assert calls == ["https://my.overpass/api/interpreter"]


def test_tls_trusts_certifi_roots_too():
    certifi = pytest.importorskip("certifi")
    import ssl
    own = ssl.create_default_context()
    own.load_verify_locations(certifi.where())
    assert pm._tls() is pm._tls()                            # built once
    assert len(pm._tls().get_ca_certs()) >= len(own.get_ca_certs()) > 0


def test_a_report_with_no_requests_says_the_cache_answered():
    rep = pm.overpass_report(pm.overpass_mark())
    assert rep["requests"] == 0 and "cache" in rep["note"]


# ── the names query in tiles x chunks ───────────────────────────────────────
def _box_of(query):
    import re
    m = re.search(r"\]\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\);", query)
    return tuple(float(v) for v in m.groups())


def test_names_are_asked_tile_by_tile_and_merged_once(monkeypatch, tmp_path):
    asked = []
    long_street = {"type": "way", "id": 7, "tags": {"name": "Broadway"}, "geometry": [{"lat": 40.7, "lon": -74}]}

    def post(q, t):
        b = _box_of(q)
        asked.append(b)
        els = [long_street, {"type": "node", "id": len(asked) + 100, "tags": {"name": "Pier %d" % len(asked)}}]
        return {"elements": els}

    monkeypatch.setattr(pm, "_post_overpass", post)
    raw = cs.fetch_names(BB, ["Broadway", "Pier 1"], cache_dir=tmp_path)
    tiles = pm.tile_boxes(BB, *cs.NAMES_TILE)
    assert len(tiles) == 9 and sorted(asked) == sorted(tiles)
    ids = [(e["type"], e["id"]) for e in raw["elements"]]
    assert ids.count(("way", 7)) == 1 and len(ids) == 10    # Broadway on every tile is kept once
    # cached whole and per piece: asked again, nothing goes out
    asked.clear()
    assert cs.fetch_names(BB, ["Pier 1", "Broadway"], cache_dir=tmp_path) == raw
    assert asked == []
    assert len(list(tmp_path.glob("names-*.json"))) == 10


def test_a_rerun_after_a_failed_tile_asks_only_for_what_is_missing(monkeypatch, tmp_path):
    asked, down = [], {"on": True}

    def post(q, t):
        b = _box_of(q)
        asked.append(b)
        if down["on"] and len(asked) == 5:
            raise RuntimeError("no server answered")
        return {"elements": []}

    monkeypatch.setattr(pm, "_post_overpass", post)
    monkeypatch.setattr(cs, "_names_piece", _no_split(cs._names_piece))
    with pytest.raises(RuntimeError):
        cs.fetch_names(BB, ["A"], cache_dir=tmp_path)
    down["on"], asked[:] = False, []
    cs.fetch_names(BB, ["A"], cache_dir=tmp_path)
    assert len(asked) == 9 - 4                               # the four tiles answered before are not asked again


def _no_split(f):
    def g(tb, names, cache_dir, timeout, log, depth=0):
        return f(tb, names, cache_dir, timeout, log, depth=1)  # the quarter level: one round, no further split
    return g


def test_many_names_are_asked_in_chunks(monkeypatch):
    asked = []
    monkeypatch.setattr(pm, "_post_overpass", lambda q, t: asked.append(q.count('nwr["name"')) or {"elements": []})
    small = (40.70, -74.00, 40.71, -73.99)                   # one tile
    cs.fetch_names(small, ["N%03d" % i for i in range(cs.NAMES_CHUNK * 2 + 5)])
    assert asked == [cs.NAMES_CHUNK, cs.NAMES_CHUNK, 5]


def test_a_tile_no_server_answers_is_asked_again_in_quarters(monkeypatch):
    asked = []

    def post(q, t):
        b = _box_of(q)
        asked.append(b)
        if b[2] - b[0] > 0.015:                              # the whole tile is too much for every server
            raise RuntimeError("no server answered")
        return {"elements": [{"type": "node", "id": len(asked)}]}

    monkeypatch.setattr(pm, "_post_overpass", post)
    small = (40.70, -74.00, 40.72, -73.98)                   # one 0.02 x 0.03 tile
    raw = cs.fetch_names(small, ["A"])
    assert len(asked) == len(cs.RETRY_S) + 1 + 4             # the tile (with its retries), then its four quarters
    assert len(raw["elements"]) == 4


def test_one_small_box_is_still_one_request(monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(pm, "_post_overpass", lambda q, t: asked.append(q) or {"elements": []})
    cs.fetch_names((40.70, -74.00, 40.71, -73.99), ["A", "B"], cache_dir=tmp_path)
    assert len(asked) == 1 and len(list(tmp_path.glob("names-*.json"))) == 1
