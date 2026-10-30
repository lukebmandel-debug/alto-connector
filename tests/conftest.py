"""Shared test fixtures.

The one piece of genuinely global state in this codebase is
`alto.mcp_server._require_auth`. Importing `alto.web` sets it True for the
whole process — correct in production, where a process is either the stdio
server or the OAuth-protected web app and never both, but in a test session
both live in the same interpreter. Whichever module imported first then
decides whether unrelated tests see a working `uid()`.

That is a test-ordering bug waiting to happen, so reset it around every test
rather than remembering to do it in each one.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── tests never make a sound ─────────────────────────────────────────────────────────────────────────────────────
# The palace's sound code (battleship, crowd, ...) stays exactly as it is in Alto; only the TEST browsers are silenced, so a run on the
# owner's Mac is not audible. Every Playwright browser the tests open gets (1) a page script that routes anything an AudioNode sends to the
# context's destination through a zero-gain node (the whole Web Audio graph still runs, so tests of it still see real nodes) and keeps
# media elements muted, and (2) --mute-audio for Chromium. ALTO_TEST_SOUND=1 turns this off (to hear a test on purpose).
_MUTE_JS = """(function(){ try{
  var AN=window.AudioNode; if(AN && AN.prototype && !AN.prototype.__altoMuted){ var oc=AN.prototype.connect; AN.prototype.__altoMuted=true;
    AN.prototype.connect=function(d){ try{ if(d && window.AudioDestinationNode && d instanceof window.AudioDestinationNode){ var cx=d.context; if(!cx.__altoMute){ var g=cx.createGain(); g.gain.value=0; oc.call(g,d); cx.__altoMute=g; }
      var a=Array.prototype.slice.call(arguments); a[0]=cx.__altoMute; oc.apply(this,a); return d; } }catch(e){} return oc.apply(this,arguments); }; }
  var M=window.HTMLMediaElement; if(M && M.prototype && !M.prototype.__altoMuted){ var op=M.prototype.play; M.prototype.__altoMuted=true; M.prototype.play=function(){ try{ this.muted=true; this.volume=0; }catch(e){} return op.apply(this,arguments); }; }
  if(window.speechSynthesis){ try{ window.speechSynthesis.speak=function(){}; }catch(e){} }
}catch(e){} })();"""


def _silence_test_browsers():
    import os
    if os.environ.get("ALTO_TEST_SOUND") == "1":
        return
    try:
        from playwright.sync_api import Browser, BrowserType
    except Exception:
        return
    if getattr(Browser, "_alto_muted", False):
        return
    o_ctx, o_page, o_launch = Browser.new_context, Browser.new_page, BrowserType.launch

    def new_context(self, *a, **k):
        c = o_ctx(self, *a, **k)
        c.add_init_script(_MUTE_JS)
        return c

    def new_page(self, *a, **k):
        p = o_page(self, *a, **k)
        p.context.add_init_script(_MUTE_JS)
        return p

    def launch(self, *a, **k):
        if getattr(self, "name", "") == "chromium":
            k["args"] = list(k.get("args") or []) + ["--mute-audio"]
        return o_launch(self, *a, **k)

    Browser.new_context, Browser.new_page, BrowserType.launch = new_context, new_page, launch
    Browser._alto_muted = True


_silence_test_browsers()


@pytest.fixture(autouse=True)
def _isolate_global_server_state(tmp_path_factory, monkeypatch, request):
    from alto import mcp_server as srv

    # set_up / set_up_palace fetch the fill-in footprints (palace_fillin) from Overpass: a test that stubs the
    # city fetch must not reach the network through them (it hung the suite on a live Overpass). A test that
    # exercises fetch_buildings itself stubs _post_overpass and is left alone.
    if request.module.__name__.rsplit(".", 1)[-1] != "test_palace_fillin":
        from alto import palace_map as _pm
        monkeypatch.setattr(_pm, "fetch_buildings", lambda box, **kw: {"elements": [], "missing": []})
        monkeypatch.setattr(_pm, "_sleep", lambda s: None)       # (fetch_footprints waits BLD_PAUSE between the cells it asks for: not here)

    # which Overpass server answered last / failed lately is module state: every test starts with none, in the
    # built-in order (no ALTO_OVERPASS_URL of the machine's own)
    from alto import palace_map as _pm0
    monkeypatch.setattr(_pm0, "_last_ok", None)
    monkeypatch.setattr(_pm0, "_down_until", {})
    monkeypatch.delenv("ALTO_OVERPASS_URL", raising=False)
    from alto.build import city_setup as _cs0
    monkeypatch.setattr(_cs0, "_sleep", lambda s: None)

    # set_up fetches the fleet (palace_fleet.fetch: museum ships, military land) from Overpass too: not from a test that stubs the city fetch (it hung on a busy Overpass)
    if request.module.__name__.rsplit(".", 1)[-1] != "test_palace_1999_fleet":
        from alto.build import palace_fleet as _pf
        monkeypatch.setattr(_pf, "fetch", lambda box, **kw: {"elements": []})


    # the city's base and tiles (palace_tiles.py) likewise
    monkeypatch.setenv("ALTO_TILES_DIR", str(tmp_path_factory.mktemp("alto-cmap")))

    # Point the default store at a temp directory for EVERY test. Without
    # this, any test that exercises a code path reaching get_store() without
    # setting ALTO_STORE_DIR writes into the real ~/Documents/Alto — which is
    # exactly what happened: a test run left OAuth token fixtures in the
    # author's home directory. A test suite must never touch it.
    monkeypatch.setenv(
        "ALTO_STORE_DIR", str(tmp_path_factory.mktemp("alto-store")))
    # Same for the sign-in session, the managed site record (site.json) and
    # set_up_site's tools: a real one on this machine must never steer a test
    # (store_mode 'auto' becomes cloud when site.json says ready).
    monkeypatch.setenv(
        "XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("xdg-config")))
    monkeypatch.setenv(
        "ALTO_TOOLS_DIR", str(tmp_path_factory.mktemp("alto-tools")))
    from alto.cloud import provision
    provision.set_provisioner(None)

    previous_auth = srv._require_auth
    srv.require_auth(False)
    yield
    srv.require_auth(previous_auth)
    # The store is a module-level singleton; a test that swapped it in must
    # not leak that store into the next test's assertions.
    srv.set_store(None)


# ── CI-only skips ────────────────────────────────────────────────────────────────────────────────────────────────
# Only when ALTO_CI=1 (set by .github/workflows/tests-full.yml). A normal local run never reads this list. Each entry is a node-id
# prefix and ONE reason; only a test that needs something a hosted runner does not have goes here (a GPU, a private fixture), and only
# with evidence from a CI log. A test that merely failed on CI is not skipped: it is looked at.
CI_SKIPS = (
    ("tests/test_solar_camera.py::test_a_flight_a_dive_and_a_zoom_out_keep_the_eye_and_the_ship_clear",
     "counts more than 100 animation frames of a flight; the runner has no GPU and records about 11 (tests-full run 41073176698)"),
    ("tests/test_solar_round10.py::test_a_flight_in_3d_flies_the_chosen_craft_then_dives_close_up",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_a_long_flight_is_at_most_five_seconds_and_enter_lands_it",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_an_enlarged_body_is_its_globe_close_up",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_retro_flies_a_regal_ship_smoothly",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_ships_point_along_their_way_and_arrive_into_an_orbit",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_the_explorer_warps_between_systems_and_flies_on_impulse_within_one",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_the_halo_jumps_in_a_flash_of_light",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round10.py::test_the_rocket_brakes_tail_first_into_a_smooth_orbit",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_fly.py::test_a_flight_to_another_system_swings_by_and_its_frames_are_cheap",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_round12.py::test_the_camera_reports_the_frame_on_the_window_while_it_glides",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
    ("tests/test_solar_camera.py::test_a_free_camera_is_never_inside_a_body",
     "needs WebGL/GPU (results None / frame budget on software rendering), tests-full run 41078430121"),
)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("ALTO_CI") != "1":
        return
    for item in items:
        for prefix, why in CI_SKIPS:
            if item.nodeid.startswith(prefix):
                item.add_marker(pytest.mark.skip(reason="CI: " + why))
