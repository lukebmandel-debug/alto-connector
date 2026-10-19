"""The test browsers are silenced (tests/conftest.py _silence_test_browsers): audio sent to a context's destination goes through a zero-gain node."""
import pytest


def test_audio_to_the_destination_goes_through_a_zero_gain_node():
    sp = pytest.importorskip("playwright.sync_api")
    with sp.sync_playwright() as p:
        try:
            br = p.webkit.launch()
        except Exception:
            pytest.skip("no WebKit")
        pg = br.new_page()
        pg.goto("about:blank")
        r = pg.evaluate("""()=>{ var AC=window.AudioContext||window.webkitAudioContext; if(!AC) return {ac:false};
          var cx=new AC(), o=cx.createOscillator(); var ret=o.connect(cx.destination); o.start();
          return {ac:true, muted: !!cx.__altoMute, gain: cx.__altoMute?cx.__altoMute.gain.value:null, returnsDestination: ret===cx.destination}; }""")
        br.close()
    if not r["ac"]:
        pytest.skip("no AudioContext")
    assert r["muted"] and r["gain"] == 0 and r["returnsDestination"]
