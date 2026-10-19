"""2.0.1: the first-person tab froze on Market Street in Old City (world ~(10590, 7800), west of 1.9 Summary Judgement), in stock 1.9.102.

Cause: palace_ride_credit.py swaps the palace district at the end of the HUD's aria-live line for the real neighbourhood, from a MutationObserver that also watches
that line. Where the real neighbourhood has the district's own name ("Old City" == "Old City") the swap wrote back the SAME text; a textContent write is a
childList mutation even when nothing changes, so the observer re-fired itself in one endless microtask chain and the page never painted again.
Fix: crLiveText returns null when nothing changes (no write), a burst guard disconnects any observer feedback loop (one warning), and the real-world gather
has a watchdog (palace_ride_e.py RW_WD: a sliced gather over 250 ms is abandoned, the old world kept, retried smaller).

The runtime checks reuse the 1.9.100 FPV test's synthetic city in WebKit and Chromium (skipped without Playwright); no network, no ALTO_* settings.
"""
import os
import sys
import time

from alto.build import palace_ride, palace_ride_credit as pc, palace_ride_e as pe

sys.path.insert(0, os.path.dirname(__file__))
import test_palace_2000_fpv as F  # noqa: E402

page = F.page
roam = F.roam


def test_source_no_rewrite_of_unchanged_text_and_a_burst_guard():
    j = pc.JS_CREDIT
    assert "function crLiveText(t, pa, ar)" in j and "return nu===t?null:nu;" in j
    assert "if(nu!==null) lv.textContent=nu;" in j and "lv.textContent=t.slice" not in j
    assert "var CR_BURST=40;" in j and "CR.mo.disconnect()" in j
    assert j in palace_ride.RIDE_JS


def test_source_gather_watchdog():
    e = pe._JS_E
    assert "var RW_WD=250, RW_RMIN=180, RW_WAIT=1000;" in e and "RW.gen.return()" in e and "RW.Rnow=Math.max(RW_RMIN" in e
    assert "if(!sync && RW.wdAt && performance.now()<RW.wdAt) return;" in e


def test_the_swap_is_a_pure_function(roam):
    pg = roam
    r = pg.evaluate("""() => { var L=window._palRide.real.credit.live;
      return [L('Market Street. Old City','Old City','Old City'), L('Market Street. Old City','Old City','Society Hill'), L('Market Street. Old City','Old City',''), L('Market Street','Old City','X'), L('','Old City','X')]; }""")
    assert r == [None, "Market Street. Society Hill", "Market Street", None, None]


def test_same_name_neighbourhood_does_not_freeze_the_tab(roam):
    """The live position, reduced to what froze it: the real neighbourhood equals the palace district, the HUD writes both lines."""
    pg = roam
    F.stand(pg, 30, 3.14159)
    pg.evaluate("() => { var C=window._palRide.real.credit; C.tick(); C.cr.force={x:0, y:0, real:true, ar:'Old City'}; window.__done=0; }")
    t0 = time.time()
    pg.evaluate("""() => { setTimeout(function(){ var ar=document.querySelector('#pal-ride .rm-ar'), lv=document.querySelector('#pal-ride .rm-live');
      ar.textContent='Old City'; lv.textContent='Market Street. Old City'; window._palRide.roam.draw(); setTimeout(function(){ window.__done=1; }, 30); }, 0); }""")      # after this call returns: a frozen page fails the wait below
    pg.wait_for_function("() => window.__done === 1", timeout=5000)           # a feedback loop never lets the timer run: this would time out
    assert time.time() - t0 < 2.0
    r = pg.evaluate("() => { var C=window._palRide.real.credit; var o=[document.querySelector('#pal-ride .rm-live').textContent, C.cr.warned]; C.cr.force=null; return o; }")
    assert r == ["Market Street. Old City", 0]                                 # nothing to change, nothing written, the guard never needed


def test_a_gather_that_runs_long_is_abandoned_and_retried_smaller(roam):
    pg = roam
    F.stand(pg, 30, 3.14159)
    r = pg.evaluate("""() => { var R=window._palRide.roam, REAL=window._palRide.real, keep=REAL.gatherG, ver=R.state().ver, t0=performance.now();
      REAL.gatherG=function*(){ for(;;){ var t=performance.now(); while(performance.now()-t<20){} yield; } };
      for(var i=0;i<40 && !R.real.stats().aborts;i++) R.real.step(false);
      var s1=R.real.stats(), ms=performance.now()-t0;
      REAL.gatherG=function*(x,y,Rr){ yield; return {solids:[], tiles:[], parks:[], water:[], roads:[], props:[], poles:[], labels:[], dashes:[], meshes:[], movers:[], set:{}, real:{R:Rr}}; };
      var n0=R.real.stats().n; for(var k=0;k<5 && R.real.stats().n===n0;k++) R.real.step(false); var s2=R.real.stats(); REAL.gatherG=keep;
      return {aborts:s1.aborts, Rnow:s1.Rnow, R:s1.R, kept:R.state().ver!==ver, ms:ms, Rnow2:s2.Rnow, n2:s2.n-n0}; }""")
    assert r["aborts"] == 1 and r["Rnow"] == round(r["R"] * .7)                # abandoned once, smaller next time
    assert r["ms"] < 600                                                       # ~250 ms of work at most, sliced
    assert r["n2"] == 1 and r["Rnow2"] == min(r["R"], round(r["Rnow"] * 1.25))                  # a gather that finishes lets the radius grow back
    pg.evaluate("() => window._palRide.roam.exit(false)")
