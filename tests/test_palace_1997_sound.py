"""1.9.97: the battleship's guns are heard — synthesised with Web Audio, no audio files (alto/build/palace_sound.py).

Source assertions + a node syntax check always run. The browser checks (an OfflineAudioContext rendered in WebKit and Chromium; the real palace page
in a QA sandbox) run through the QA kit's python when it is on this machine. Nobody can HEAR these tests: they assert levels, timing, silence at
the end, that nothing throws, and that the plumbing (gesture-made context, toggle, Esc, hidden tab) works."""
import gzip
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from alto.build import palace, palace_sound

QA = Path.home() / "Desktop" / "Alto Development" / "_qa"
NODE = Path.home() / ".local" / "node" / "bin" / "node"
HERE = Path(__file__).parent
KITPY = QA / "kit" / "py"
JS = palace_sound.SOUND_JS
PJS = palace.PALACE_JS


def test_the_module_is_small_and_no_audio_files_or_network():
    assert len(gzip.compress(JS.encode())) < 3000
    for bad in ("fetch(", "XMLHttpRequest", "decodeAudioData", ".mp3", ".wav", ".ogg", "http://", "https://", "<audio", "new Audio"):
        assert bad not in JS


def test_the_page_hooks_are_one_liners_tied_to_the_real_shots():
    assert "CONSTRUCT_JS + SOUND_JS + PANIC_JS + TRANSIT_JS" in Path(palace.__file__).read_text()
    assert "SND=window._palSnd" in PJS
    assert "FXARM=on; SND.bar(b, on);" in PJS                                    # arming / standing down (Esc, ×, the ship again)
    assert "function fxBoom(x, y){\n  SND.b(x, y);" in PJS                            # at the moment of impact
    assert "FXLAST=now; SND.u(b.x, b.y);" in PJS                                    # inside the firing click, with the ship's place
    assert re.search(r"ms=Math\.max\(700, Math\.min\(1500, 500\+d\*\.6\)\); SND\.f\(ms\);\n\s+fxShell\(mx, my,", PJS)   # at each mount's own shot, whistle = flight time


def test_what_the_synthesis_is_made_of():
    for needle in ("createDynamicsCompressor", "'lowpass',6000,150", "sn(t,90,30", "'bandpass',2800,900", "createDelay", "createBiquadFilter", "sawtooth", "[800,1200]", "[600,2300]", "sc:sc",
                   "webkitAudioContext", "document.hidden", "'alto-palace-sound'", "visibilitychange", "c.close()", "'Mute battleship sound'", "'Unmute battleship sound'"):
        assert needle in JS, needle
    assert "autoplay" not in JS.lower()
    # the context is only made in u(), which the arming / firing clicks call; nothing creates one at load
    assert JS.count("new A()") == 1 and "function u(" in JS
    assert "try{ var A=window.AudioContext" in JS                                  # never throws when Web Audio is missing


def test_the_impact_screams_once_per_strike_and_scream_is_exposed():
    assert "if(t-Z>.9){ Z=t; sc(a,t-C.currentTime+.12); }" in JS     # one crowd per landing, not one per shell
    assert "function sc(v,w){ if(!ok()) return;" in JS               # the same toggle / hidden / no-audio rules


@pytest.mark.skipif(not NODE.exists(), reason="node not installed")
def test_the_module_parses():
    p = HERE / "_snd97_check.js"
    p.write_text("new Function(" + json.dumps(JS) + ");")
    try:
        r = subprocess.run([str(NODE), str(p)], capture_output=True, text=True)
    finally:
        p.unlink()
    assert r.returncode == 0, r.stderr


def _run(script):
    env = {"HOME": str(Path.home()), "PATH": os.environ["PATH"], "ALTO_REPO": str(HERE.parent)}
    r = subprocess.run([str(KITPY), str(HERE / script)], capture_output=True, text=True, env=env, timeout=600)
    line = [x for x in r.stdout.splitlines() if x.startswith("RESULT ")]
    assert line, r.stdout[-1500:] + r.stderr[-1500:]
    return json.loads(line[0][7:])


@pytest.fixture(scope="module")
def blank():
    if not KITPY.exists():
        pytest.skip("QA kit not on this machine")
    return _run("palace_1997_sound_browser.py")


@pytest.mark.parametrize("eng", ["webkit", "chromium"])
def test_offline_render_levels_silence_and_distance(blank, eng):
    r = blank[eng]
    assert r["errors"] == []
    for k in ("one", "volley", "near", "far", "scream", "all"):
        assert not r[k].get("bad"), k
        assert 0.02 < r[k]["peak"] < 1.0, (k, r[k])                     # audible, never clips
        assert r[k]["tail"] < 0.002, (k, r[k])                          # ends near silence (> 5 s render, last quarter second)
    assert 0.2 < r["one"]["peak"] < 0.45                                # a single report peaks around -10 dBFS
    assert r["volley"]["peak"] < 0.7                                    # the compressor keeps a volley moderate
    assert r["far"]["peak"] < r["near"]["peak"] * 0.8                   # farther is quieter...
    assert r["far"]["first"] > r["near"]["first"] + 0.3                 # ...and later
    assert r["one"]["first"] < 0.02                                     # the report starts at once (no pre-delay)
    assert r["scream"]["peak"] < 0.2 and r["scream"]["peak"] < r["one"]["peak"]   # a crowd, quiet and far away: below a gun report
    assert 0.4 < r["scream"]["loud"] < 2.6                           # about two seconds of panic
    assert r["hidden"]["peak"] == 0                                     # a hidden tab schedules nothing


@pytest.mark.parametrize("eng", ["webkit", "chromium"])
def test_toggle_and_no_web_audio(blank, eng):
    r = blank[eng]
    assert r["noAudio"] is True                                         # AudioContext missing: nothing throws
    t = r["toggle"]
    assert t["l0"] == "Mute battleship sound" and t["l1"] == "Unmute battleship sound" and t["iconSwapped"]
    assert t["stored"] == "0" and t["on1"] is False and t["on2"] is True and t["stored2"] == "1"
    assert t["barClicks"] == 0                                          # the speaker never stands the guns down
    assert t["order"] == "fx-t|fx-x fx-s|fx-x"                          # next to the × button
    assert r["offAfterReload"] is False                                 # remembered


@pytest.fixture(scope="module")
def page():
    if not KITPY.exists() or not (QA / "sandboxes" / "snd97").exists():
        pytest.skip("QA sandbox snd97 not on this machine (copy _qa/sandboxes/w95c, rebuild with kit/rebuild_sandbox.py snd97)")
    return _run("palace_1997_sound_page.py")


@pytest.mark.parametrize("eng", ["webkit", "chromium"])
def test_the_real_page_arm_fire_esc_mute(page, eng):
    r = page[eng]
    assert r["errors"] == []
    assert r["afterArm"]["n"] == 1 and r["afterArm"]["acs"] == ["running"]  # made and resumed inside the arming click
    assert r["bar"]["label"] == "Mute battleship sound" and r["bar"]["kids"] == "fx-t|fx-x fx-s|fx-x"
    kinds = [c[0] for c in r["afterFire"]["calls"]]
    assert kinds.count("f") >= 2 and kinds.count("b") >= 2 and kinds[0] == "u"
    f = [c for c in r["afterFire"]["calls"] if c[0] == "f"]
    b = [c for c in r["afterFire"]["calls"] if c[0] == "b"]
    assert 700 <= f[0][2][0] <= 1500                                    # whistle length = the shell's flight time
    assert f[1][1] - f[0][1] > 80                                       # the mounts' shots are staggered
    assert b[0][1] - f[0][1] > 600                                      # the impact comes at the landing, not the firing
    assert r["afterEsc"]["acs"] == ["closed"] and r["armedAfterEsc"] is False
    m = r["muted"]
    assert m["ls"] == "0" and m["lab"] == "Unmute battleship sound" and m["armed"] is True
    assert r["afterMutedFire"] == ["closed", "closed"]                  # muted: firing makes no new context
