"""1.9.97: the first-person ride is a hosted static file (/ride/palace-ride-<hash>.js), not part of the page. A private page is ONE Firestore document
(private_shell.MAX_PAGE_BYTES stored bytes); the ride's ~370 KB of script (~135 KB gzipped) did not fit beside the palace. These tests pin: the page carries a
small synchronous loader instead of the ride, every use of window._palRide is guarded (the page works with the file missing), the site writes the file under a
content-hashed name with an immutable-cache rule, and the page's size stays clear of the cap."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from alto.build import palace, palace_ride, palace_ride_f, palace_transit_js, palace_directions, private_shell

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
QA = Path.home() / "Desktop" / "Alto Development" / "_qa"


def test_the_page_carries_the_loader_not_the_ride():
    assert palace_ride.RIDE_LOADER in palace.PALACE_JS
    assert palace_ride.RIDE_JS not in palace.PALACE_JS
    assert "(function(){\nif(window._palRide) return;" not in palace.PALACE_JS        # none of the ride's own source
    assert len(palace_ride.RIDE_LOADER) < 600 and len(palace_ride.RIDE_JS) > 300_000
    assert palace_ride.RIDE_CSS not in palace.PALACE_CSS and __import__("json").dumps(palace_ride.RIDE_CSS) in palace_ride.RIDE_ASSET   # the ride's rules ride in the asset
    # the loader comes before the palace's own code, which calls _palRide.init at once
    assert palace.PALACE_JS.index(palace_ride.RIDE_LOADER) < palace.PALACE_JS.index("if(window._palRide) window._palRide.init(")


def test_the_loader_is_a_synchronous_request_and_an_inline_script():
    l = palace_ride.RIDE_LOADER
    assert "open('GET','" + palace_ride.RIDE_PATH + "',false)" in l                    # synchronous: _palRide must exist for the code that follows
    assert "s.text=x.responseText" in l and "appendChild(s)" in l                      # CSP allows inline scripts, not eval; document.write would run it too late
    assert "eval" not in l and "document.write" not in l and "new Function" not in l
    assert "catch(e){}" in l and "x.status===200" in l                                 # a missing file / network error leaves _palRide undefined
    assert l.startswith("\n(function(){ if(window._palRide) return;")                   # a second load is a no-op


def test_the_asset_is_named_by_a_hash_of_its_own_text():
    import hashlib
    name, js = palace_ride.ride_asset()
    assert js == palace_ride.RIDE_ASSET and palace_ride.RIDE_JS in js
    assert name == "palace-ride-" + hashlib.sha256(js.encode("utf-8")).hexdigest()[:10] + ".js"
    assert palace_ride.RIDE_PATH == "/ride/" + name and palace_ride.RIDE_V in name
    assert re.fullmatch(r"/ride/palace-ride-[0-9a-f]{10}\.js", palace_ride.RIDE_PATH)
    assert palace_ride.RIDE_PATH in palace.PALACE_JS                                    # the page asks for exactly that name


def _guarded_uses():
    """(file, line no, line) of every window._palRide use outside the ride's own modules."""
    out = []
    for mod in (palace, palace_transit_js, palace_directions):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            if "_palRide" in line and not line.lstrip().startswith(("#", "/*", "//")):
                out.append((Path(mod.__file__).name, n, line))
    return out


GUARDS = ("window._palRide&&", "window._palRide &&", "if(window._palRide)", "window._palRide?", "var rr=window._palRide")


def test_every_use_of_the_ride_in_the_page_is_guarded():
    uses = _guarded_uses()
    assert len(uses) >= 12, "the hooks moved?"
    for f, n, line in uses:
        # a use sits behind a window._palRide test on its own line (audited by hand for 1.9.97: all of palace.py / palace_transit_js.py)
        assert any(g in line for g in GUARDS), "unguarded use of the ride at %s:%d: %s" % (f, n, line.strip()[:160])
        first = min(line.index(g) for g in GUARDS if g in line)
        assert not re.search(r"window\._palRide\.\w", line[:first]), "a use before its guard at %s:%d" % (f, n)


def test_the_init_call_and_the_control_hooks_wait_for_the_ride():
    p = palace.PALACE_JS
    assert "if(window._palRide) window._palRide.init({" in p
    assert p.count("window._palRide.init(") == 1                                         # only that one call
    assert "if(window._palRide&&window._palRide.ui&&window._palRide.ui.keyRows) h+=window._palRide.ui.keyRows();" in p
    assert "if(window._palRide&&window._palRide.ui&&window._palRide.ui.mount) window._palRide.ui.mount(c);" in p
    t = palace_transit_js.TRANSIT_JS
    assert "var rr=window._palRide, was=rr&&rr.active(); if(rr&&!was) rr.mark();" in t        # a trip starts with or without the ride
    assert "function endTrip(){ if(window._palRide) window._palRide.exit();" in t
    assert "(window._palRide?window._palRide.switchHtml():'')" in t
    assert t.count("(window._palRide&&window._palRide.ui?window._palRide.ui.pillHtml():'')") == 2


def test_the_trip_panels_name_the_v_key_only_when_the_ride_is_there():
    t = palace_transit_js.TRANSIT_JS
    assert t.count("(window._palRide?'V first-person rides on / off") == 2
    assert "\u00b7 V first-person" not in t and "· V first-person" not in t.replace("'+(window._palRide?'V first-person", "")


def test_nothing_in_the_page_reaches_into_the_rides_other_globals():
    for name in ("_palRideGL", "_palRideLm", "_palRideNoGL", "_palRideNoShadow"):
        for f, n, line in _guarded_uses():
            assert name not in line, (f, n)


def test_the_site_writes_the_ride_and_keeps_it_for_a_year(tmp_path):
    from alto.publish_static import regenerate_site, _headers
    from alto.store.local import LocalStore
    site = tmp_path / "site"
    (site / "ride").mkdir(parents=True)
    (site / "ride" / "palace-ride-0000000000.js").write_text("old", encoding="utf-8")       # an earlier release's file is swept
    regenerate_site(LocalStore(tmp_path / "store"), "local", site)
    name, js = palace_ride.ride_asset()
    assert sorted(p.name for p in (site / "ride").iterdir()) == [name]
    assert (site / "ride" / name).read_text(encoding="utf-8") == js
    heads = _headers("csp", "ccsp")
    rule = next(h for h in heads if h["source"] == "/ride/**")
    assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rule["headers"]
    assert heads[0]["source"] == "**" and heads.index(rule) > 0                              # after the no-cache default, so it wins
    # the loader's synchronous request is a same-origin fetch: the site's CSP allows it
    from alto.publish_static import _csp
    assert "connect-src 'self'" in _csp("'none'") and "script-src 'self' 'unsafe-inline'" in _csp("'none'")


def _tiny_palace_page():
    sys.path.insert(0, str(HERE))
    import test_palace as tp
    from alto.build.builder import build_timeline
    html, _ = build_timeline(*tp.load(tp.bundle()))
    return html


def test_a_built_palace_page_has_the_loader_and_stays_far_under_the_cap():
    html = _tiny_palace_page()
    assert palace_ride.RIDE_LOADER in html and palace_ride.RIDE_JS not in html and palace_ride.RIDE_PATH in html
    stored = private_shell.stored_bytes(html)
    assert stored < private_shell.MAX_PAGE_BYTES - 300_000
    inline = private_shell.stored_bytes(html.replace(palace_ride.RIDE_LOADER, palace_ride.RIDE_JS))
    assert inline - stored > 100_000                                                    # the ride is what stays out of the stored page


def test_the_pages_code_leaves_room_for_the_city():
    """The civ-pro palace is ~850 KB of city data + fill-in beside the code: the code (JS+CSS, gzipped as the page is stored) must stay small, and the ride must
    stay out of it (inline it is ~135 KB more, which is what broke the cap)."""
    code = private_shell.stored_bytes(palace.PALACE_JS + palace.PALACE_CSS)
    ride = private_shell.stored_bytes(palace_ride.RIDE_JS)
    assert ride > 100_000                                                                   # why it had to leave
    assert code < 185_000, "the palace's own code grew to %d stored bytes; the city page is within a few KB of the cap" % code


@pytest.mark.skipif(not (QA / "kit" / "py").exists(), reason="QA kit not on this machine")
@pytest.mark.parametrize("engine", ["webkit", "chromium"])
def test_the_loader_in_a_browser(engine):
    env = {"HOME": str(Path.home()), "PATH": os.environ.get("PATH", ""), "ALTO_REPO": str(ROOT)}
    r = subprocess.run([str(QA / "kit" / "py"), str(HERE / "ride_split_runtime" / "loader_check.py"), engine], capture_output=True, text=True, env=env, cwd=str(QA))
    assert r.returncode == 0 and "RESULT PASS" in r.stdout, r.stdout[-2500:] + r.stderr[-1500:]
