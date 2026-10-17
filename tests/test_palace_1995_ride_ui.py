"""1.9.95 first-person city, the UI part: the Aerial | First-person switch in the palace's control cluster, key F, drop in (a ghost on the pointer,
fly there, hand over to free roaming), the First-person rides setting (shared key and V), legend rows, trip panel and route pills.

Source assertions + a node syntax check always run; the behaviour check (WebKit and Chromium against a fake ROAM) runs when the QA kit is on this machine."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from alto.build import palace, palace_ride, palace_ride_f, palace_transit_js

QA = Path.home() / "Desktop" / "Alto Development" / "_qa"
NODE = Path.home() / ".local" / "node" / "bin" / "node"
HERE = Path(__file__).parent


def test_the_switch_and_the_ride_setting_are_mounted_in_the_control_cluster():
    js = palace.PALACE_JS
    assert "window._palDirMount(c); if(window._palRide&&window._palRide.ui&&window._palRide.ui.mount) window._palRide.ui.mount(c);" in js
    f = palace_ride_f.JS_F
    for needle in ('data-fp="aerial"', 'data-fp="first"', "'pc-rides'", "'pc-stay'", 'aria-label','aria-pressed', "setAttribute('role','group')", "aria-keyshortcuts"):
        assert needle in f
    assert "window._palRide.ui.keyRows" in js                                   # rows in the legend
    assert "Key F" in f and "Key V" in f


def test_the_cluster_buttons_match_the_zoom_pill_and_hide_on_phone_and_print():
    css = palace_ride_f.CSS_F
    assert "#pal-ctl .pc-pill.pc-fp button" in css and "#pal-ctl .pc-rides" in css
    assert "var(--card-glass-bg,var(--surface))" in css                          # the cluster's own glass, so light and dark follow
    assert "html.mobile #pal-fp-ghost" in css and "html.printing #pal-fp-ghost" in css
    assert "prefers-reduced-motion" in css
    assert "html.mobile #pal-ctl" in palace.PALACE_CSS                           # the cluster itself is hidden there


def test_the_setting_shares_the_ride_view_key_and_the_v_key():
    f = palace_ride_f.JS_F
    assert "toggle()" in f and "pref()" in f and "k==='v'||k==='V'" in f
    assert "alto-palace-ride-view" in palace_ride.RIDE_JS
    assert "var _lb=labelBtns; labelBtns=function(){ _lb(); sync(); };" in f   # follows V / setPref from anywhere
    assert "switchHtml=panelHtml;" in f                                          # the trip panel's switch is the labelled setting
    t = palace_transit_js.TRANSIT_JS
    assert t.count("window._palRide.ui.pillHtml()") == 2                         # both route pills
    assert "V first-person rides on / off" in t


def test_dropping_in_flies_then_enters_roam_with_the_aerial_view_kept():
    f = palace_ride_f.JS_F
    assert "E.fly(x, y, z, enter)" in f and "r.enter(x, y, h, {from:'aerial', view:view" in f
    assert "E.curView?E.curView():null" in f                                      # the view before the fly, handed to the roam
    assert "r.exit(!!stay)" in f and "Stay here" in f
    assert "mapAt:function(cx,cy)" in palace.PALACE_JS and "fly:function(x,y,z,done)" in palace.PALACE_JS
    assert "k==='Enter'" in f and "'dblclick'" in f and "k==='Escape'" in f
    assert "measureZoom" in f                                                      # CSS zoom on <html>


def test_other_parts_are_not_shadowed():
    f = palace_ride_f.JS_F
    assert f.lstrip().startswith("var UIX=(function(){") and f.rstrip().endswith("})();")


@pytest.mark.skipif(not NODE.exists(), reason="node not installed")
def test_the_generated_script_parses(tmp_path):
    out = tmp_path / "ride.js"
    out.write_text(palace_ride.RIDE_JS)
    r = subprocess.run([str(NODE), "--check", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not (QA / "kit" / "py").exists() or not (QA / "sandboxes" / "ride95ui").exists(), reason="QA kit / sandbox ride95ui not on this machine")
@pytest.mark.parametrize("engine", ["webkit", "chromium"])
def test_the_switch_behaves_against_a_fake_roam(engine):
    repo = str(HERE.parent)
    env = {"HOME": str(Path.home()), "PATH": os.environ.get("PATH", ""), "ALTO_REPO": repo}
    rb = subprocess.run([str(QA / "kit" / "py"), str(QA / "kit" / "rebuild_sandbox.py"), "ride95ui"], capture_output=True, text=True, env=env, cwd=str(QA))
    assert rb.returncode == 0, rb.stderr[-800:]
    r = subprocess.run([str(QA / "kit" / "py"), str(HERE / "ride_ui_runtime" / "ui_behave.py"), engine], capture_output=True, text=True, env=env, cwd=str(QA))
    assert r.returncode == 0 and "RESULT PASS" in r.stdout, r.stdout[-2500:] + r.stderr[-800:]
