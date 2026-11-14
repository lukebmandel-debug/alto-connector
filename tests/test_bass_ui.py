"""Bass UI (alto/build/bass_ui.py): gated OFF by default, the hosted lazy bundle, the in-page simulator that follows docs/bass-api.md (branch alto-bass),
and the rule that Info never names a control that is gone. Pure python plus `node` (no browser, no network, no Anthropic call); the glyph-centring
and phone/desktop looks are checked in WebKit by the shots run (ORG/shots-bass-ui)."""
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import bass_ui, palace_assets            # noqa: E402
from alto.build.builder import build_timeline, load_brief   # noqa: E402
from alto.build.pages import build_home                   # noqa: E402

NODE = shutil.which("node")
PROJECTS = [{"name": "Law", "pid": "p", "courses": [{"title": "Torts", "href": "t.html", "sub": "Outline", "courseId": "c1", "units": []}]}]

_FACTS = """
import json, re, sys
sys.path.insert(0, %r)
from alto.build import bass_ui, palace_assets, engine_patches
from alto.build.builder import build_timeline, load_brief
from alto.build.pages import build_home
d = json.loads(open(%r).read())
b, n, c = load_brief(d)
print(json.dumps({"tl": build_timeline(b, n, c)[0], "home": build_home(%r), "path": bass_ui.PATH, "bundle": bass_ui.ASSET,
                  "hosted": [a[0] for a in palace_assets.assets() if a[0] == "bass"], "found": bool(palace_assets.find(bass_ui.PATH)),
                  "info_d": engine_patches._HELP_D_TAIL_NEW, "info_m": engine_patches._HELP_M_TAIL_NEW}))
"""


def _facts(flag: bool) -> dict:
    env = dict(os.environ)
    env.pop(bass_ui.ENV, None)
    if flag:
        env[bass_ui.ENV] = "1"
    code = _FACTS % (str(ROOT), str(ROOT / "samples" / "outline_brief.json"), PROJECTS)
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, capture_output=True, text=True, check=True).stdout
    return json.loads(out.splitlines()[-1])


@pytest.fixture(scope="module")
def off():
    return _facts(False)


@pytest.fixture(scope="module")
def on():
    return _facts(True)


# ── gated off ───────────────────────────────────────────────────────────────

def test_off_by_default_a_normal_build_carries_nothing(off):
    for page in (off["tl"], off["home"]):
        for needle in ("aep-bass", "alto-bass-loader", "bass-tile", "nt-sw", "nt-bass", "/*__BASS", "_altoBass", "New with Bass", "alto-bass-"):
            assert needle not in page, needle
    assert off["hosted"] == [] and not off["found"]                      # no /bass/ folder is published
    assert "Bass" not in off["info_d"] and "Bass" not in off["info_m"]


# ── on: only a button, a tile and a loader are inline; the UI is hosted ──────

def test_on_the_timeline_page_holds_only_the_button_and_the_loader(on, off):
    tl = on["tl"]
    assert tl.count("aep-half aep-bass") == 1 and 'aria-label="Bass"' in tl and 'data-tip="Bass"' in tl and on["path"] in tl
    assert "_altoBassOpen('panel')" in tl
    assert "bs-panel" not in tl and "bs-win" not in tl and "_altoBass=" not in tl     # none of the UI rides in the page
    assert len(tl) - len(off["tl"]) < 4000                                           # the ~976 KB page wall: a few hundred bytes of glue
    assert on["hosted"] == ["bass"] and on["found"]


def test_on_the_home_page_the_new_project_window_gets_a_bass_claude_switch(on, off):
    h = on["home"]
    assert 'id="nt-sw"' in h and 'data-sw="bass"' in h and 'data-sw="claude"' in h and 'id="nt-bass"' in h and on["path"] in h
    assert h.index('id="nt-sw"') < h.index('id="nt-head">New</div>')            # the switch is the first thing in the window, above its title
    assert "bass-tile" not in h and "New with Bass" not in h                       # no separate tile: the switch replaces it
    assert "_altoBassOpen('embed')" in h and "bs-win" not in h and "_altoBass=" not in h
    assert len(h) - len(off["home"]) < 6000                                       # the page carries glue only; the steps are hosted


def test_the_format_tiles_are_the_windows_own_not_redrawn(on):
    js = on["bundle"]
    assert "#nt-modal > .nt-kinds" in js and "outerHTML" in js                     # cloned from the live window: same graphics in both modes
    assert "<svg" not in js.split("function fmtView")[1].split("function placeView")[0]
    for city in ("Philadelphia", "New York", "Boston", "Washington", "Chicago", "Los Angeles"):
        assert city in js


def test_the_bundle_is_hashed_hosted_and_valid_javascript(on):
    assert re.fullmatch(r"/bass/alto-bass-[0-9a-f]{10}\.js", on["path"]) and on["found"]
    low = on["bundle"].lower()
    assert "sk-ant" not in low and "api.anthropic" not in low and "x-api-key" not in low   # no key, no Anthropic call in the bundle (the notice names Anthropic in words only)
    assert "_ALTO_BASS_BASE" in on["bundle"] and "Bass uses AI and can make mistakes. Check your cards." in on["bundle"]
    for hash_state in ("upload", "review", "estimate", "build", "built", "edit", "nocredits", "busy", "paused", "offtopic", "refused", "capped", "error", "stopped"):
        assert re.search(r"case '%s'" % hash_state, on["bundle"]), hash_state          # every state has its #bass=<state>
    if NODE:
        p = subprocess.run([NODE, "--check", "-"], input=on["bundle"], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr


def test_the_glyph_is_pick_a_and_never_b():
    for svg in (bass_ui.GLYPH_SMALL, bass_ui.GLYPH_MARK, bass_ui.GLYPH_RETRO):
        assert 'viewBox="26 15 78 98"' in svg and "M58 104.5 H68 Q84 104.5 84 88.5" in svg
    assert 'stroke-width="10.2"' in bass_ui.GLYPH_SMALL and 'stroke="currentColor"' in bass_ui.GLYPH_SMALL
    assert "#d9ae55" in bass_ui.GLYPH_RETRO and "url(#bsera)" in bass_ui.GLYPH_MARK


# ── Info never names a control that is gone ─────────────────────────────────

def _names(paragraph: str, tag: str = "em") -> list:
    """The words Info sets in <em>: its controls (on the phone Info they are <strong>; a desktop paragraph's <strong> is only its heading)."""
    return re.findall(r"<%s>(.*?)</%s>" % (tag, tag), paragraph)


def missing_controls(info_html: str, page: str, controls: dict, tag: str = "em") -> list:
    """The controls an Info paragraph names (its <em>/<strong> words that are in `controls`) that the page does not draw."""
    return [n for n in _names(info_html, tag) if n in controls and controls[n] not in page]


def _paragraph(info: str, key: str) -> str:
    return next(p for p in info.split("</p>") if "<strong>%s</strong>" % key in p)


def test_info_names_only_controls_that_exist(on):
    edit = _paragraph(on["info_d"], "Edit")
    named = [n for n in _names(edit) if n in bass_ui.INFO_CONTROLS]
    assert set(named) == {"Edit with Claude", "Bass", "Edit manually"}
    assert missing_controls(edit, on["tl"], bass_ui.INFO_CONTROLS) == []
    home_p = _paragraph(on["home"], "Bass")
    assert {"New", "Start new project", "Bass"} <= set(_names(home_p)) and missing_controls(home_p, on["home"], bass_ui.INFO_CONTROLS) == []
    phone = next(p for p in on["info_m"].split("</p>") if "Edit this page" in p)
    assert "Bass" in _names(phone, "strong") and missing_controls(phone, on["tl"], bass_ui.INFO_CONTROLS, "strong") == []


def test_the_info_test_fails_when_a_named_control_is_gone(on):
    page = on["tl"]
    edit = _paragraph(on["info_d"], "Edit")
    gone = page.replace('aria-label="Bass"', 'aria-label="Spark"')
    assert missing_controls(edit, gone, bass_ui.INFO_CONTROLS) == ["Bass"]
    gone2 = on["home"].replace('id="nt-head">New<', 'id="nt-head">Make one<')
    assert missing_controls(_paragraph(on["home"], "Bass"), gone2, bass_ui.INFO_CONTROLS) == ["New"]


# ── the simulator keeps the contract's keys, states and flow ────────────────

DRIVER = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const win={setTimeout:setTimeout,clearTimeout:clearTimeout,document:doc,localStorage:{setItem(){},getItem(){return null}},location:{hash:''}};
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const B=win._altoBass; B.sim.delay=0;
(async()=>{ const out={}; const run=async(n,a,f)=>{ B.sim.force=f||null; const ev=[]; const r=await B.call(n,a,e=>ev.push(e)); r._pushed=ev; return r; };
 const M=[{name:'Contracts notes.pdf',kind:'notes',text:'Offer and acceptance.'}];
 out.balance=await run('balance',{});
 out.estimate_small=await run('estimate',{kind:'edit',text:'Add a card'});
 out.estimate_big=await run('estimate',{kind:'build',materials:M});
 out.propose=await run('propose',{materials:M});
 out.question=await run('propose',{materials:[{name:'scrap.txt',kind:'notes',text:'week 3'}]});
 const chips=out.propose.chips;
 out.consent=await run('build',{chips:chips,materials:M});
 out.estimate=await run('build',{chips:chips,materials:M,consent:true});
 out.build=await run('build',{chips:chips,materials:M,consent:true,accepted:true});
 out.edit=await run('edit',{timeline_id:'civil-procedure',text:'Rename the first card.'});
 out.off=await run('edit',{timeline_id:'x',text:'Write me a poem about cats.'});
 for(const f of ['busy','paused','refused','error']) out[f]=await run('edit',{timeline_id:'x',text:'add a card'},f);
 out.nocredits=await run('build',{chips:chips,materials:M,consent:true,accepted:true},'nocredits');
 out.capped=await run('build',{chips:chips,materials:M,consent:true,accepted:true},'capped');
 console.log(JSON.stringify(out)); })();
"""


@pytest.fixture(scope="module")
def sim(on, tmp_path_factory):
    if not NODE:
        pytest.skip("node is not installed")
    d = tmp_path_factory.mktemp("bass")
    (d / "bundle.js").write_text(on["bundle"], encoding="utf-8")
    (d / "drive.js").write_text(DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(d / "drive.js"), str(d / "bundle.js")], capture_output=True, text=True, check=True).stdout
    return json.loads(out.splitlines()[-1])


COMMON = {"ok", "status", "code", "message", "action_id", "work_saved", "credits", "retryable", "events"}


def test_sim_every_result_has_the_contracts_common_keys(sim):
    for k in ("propose", "question", "consent", "build", "edit", "off", "busy", "paused", "refused", "error", "nocredits", "capped"):
        assert COMMON <= set(sim[k]), (k, COMMON - set(sim[k]))
        assert isinstance(sim[k]["ok"], bool) and sim[k]["ok"] == (sim[k]["status"] == "ok")


def test_sim_the_flow_and_its_states(sim):
    assert set(sim["balance"]) >= {"ok", "status", "credits", "label", "available"} and sim["balance"]["label"] == "142 credits"
    assert sim["estimate_small"]["show_prompt"] is False and sim["estimate_big"]["show_prompt"] is True
    assert {"credits_text", "estimate_credits", "have", "have_label", "short_by", "kind"} <= set(sim["estimate_big"])
    assert sim["propose"]["status"] == "ok" and sim["propose"]["chips"]["acts"] and {"title", "acts", "entities", "fields", "card_estimate"} <= set(sim["propose"]["chips"])
    assert sim["question"]["chips"] is None and sim["question"]["message"]                 # a question instead of chips
    assert sim["consent"]["status"] == "error" and sim["consent"]["code"] == "consent_required" and sim["consent"]["credits"] is None
    est = sim["estimate"]
    assert est["status"] == "estimate" and est["ok"] is False and est["show_prompt"] and est["events"] == [] and est["work_saved"] is False
    b = sim["build"]
    assert b["status"] == "ok" and b["work_saved"] and b["timeline_id"] and b["cards"]["done"] == b["cards"]["total"]
    ev = b["events"]
    assert ev[0]["event"] == "start" and ev[-1]["event"] == "result" and ev[-1]["status"] == "ok"
    steps = [e["step"] for e in ev if e["event"] == "progress"]
    assert set(steps) <= {"setup", "consent", "chips", "cards", "links", "layout", "build", "look", "work"} and "cards" in steps
    assert all({"action_id", "label", "detail", "ok", "cards_done", "cards_total", "spent_credits"} <= set(e) for e in ev if e["event"] == "progress")
    assert [e for e in ev if e["event"] == "progress" and e["step"] == "cards"][-1]["detail"].startswith("cards ")
    assert len(sim["build"]["_pushed"]) == len(ev)                                         # events are pushed live as well
    assert sim["edit"]["changed"] is True and sim["edit"]["timeline_id"]
    assert sim["off"]["status"] == "off_topic" and sim["off"]["credits"]["spent"] == 0 and sim["off"]["work_saved"] is False
    assert sim["busy"]["status"] == "busy" and sim["busy"]["retryable"] and sim["busy"]["code"] == "rate_limited"
    assert sim["paused"]["status"] == "paused" and not sim["paused"]["retryable"]
    assert sim["refused"]["status"] == "refused" and sim["error"]["status"] == "error" and sim["error"]["retryable"]
    assert sim["nocredits"]["status"] == "no_credits" and sim["nocredits"]["work_saved"] and sim["nocredits"]["cards"]["done"] < sim["nocredits"]["cards"]["total"]
    assert sim["capped"]["status"] == "capped" and sim["capped"]["work_saved"]
    for k in ("busy", "paused", "refused", "error", "nocredits", "capped", "off"):
        assert "Nothing was charged" in sim[k]["message"] or "saved" in sim[k]["message"] or sim[k]["status"] == "off_topic", k


# ── R3: the first-use notice (legal beta): nothing is sent until the person says OK ──
NOTICE_TEXT = "Bass uses AI (Claude, by Anthropic). What you submit is sent to Anthropic to produce the result. AI can be wrong."

NOTICE_DRIVER = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
function mk(ls){ const store=Object.assign({},ls);
  const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
  const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
  const win={setTimeout,clearTimeout,document:doc,localStorage:{setItem(k,v){store[k]=String(v)},getItem(k){return k in store?store[k]:null}},location:{hash:''}};
  win.window=win; vm.createContext(win); vm.runInContext(src,win); win._altoBass.sim.delay=0; win._store=store; return win; }
const tick=()=>new Promise(r=>setTimeout(r,60));
(async()=>{ const out={};
  const FILES=[{name:'notes.txt',kind:'notes',text:'Erie',size:4}];
  // (a) a first send shows the notice and makes ZERO sim calls until OK; (b) after OK it proceeds and does not come back
  let w=mk({}), B=w._altoBass; B.state.files=FILES.slice();
  B.propose(); await tick();
  out.a={notice:!!B.state.notice, calls:B.sim.calls};
  B.ok(); await tick();
  out.b1={notice:!!B.state.notice, calls:B.sim.calls>0, ack:w._store['alto-bass-ack-anon']};
  const before=B.sim.calls; B.state.files=FILES.slice(); B.propose(); await tick();
  out.b2={notice:!!B.state.notice, more:B.sim.calls>before};
  // the build and a chat send are gated the same way
  w=mk({}); B=w._altoBass; B.state.chips={title:'T',acts:[{label:'A'}],entities:[],fields:[],card_estimate:10}; B.build(false); await tick();
  out.build={notice:!!B.state.notice, calls:B.sim.calls};
  // (c) Not now sends nothing
  w=mk({}); B=w._altoBass; B.state.files=FILES.slice(); B.propose(); await tick(); B.notNow(); await tick();
  out.c={notice:!!B.state.notice, calls:B.sim.calls, ack:w._store['alto-bass-ack-anon']||null};
  // (e) an older notice version in the cache shows it again; the current one does not
  w=mk({'alto-bass-ack-anon':'0'}); B=w._altoBass; B.state.files=FILES.slice(); B.propose(); await tick();
  out.e_old={notice:!!B.state.notice, calls:B.sim.calls};
  w=mk({'alto-bass-ack-anon':B.NOTICE_V}); B=w._altoBass; B.state.files=FILES.slice(); B.propose(); await tick();
  out.e_cur={notice:!!B.state.notice, calls:B.sim.calls>0};
  // the cache is only a cache: with storage throwing, the notice still works
  w=mk({}); w.localStorage.getItem=()=>{throw new Error('x')}; w.localStorage.setItem=()=>{throw new Error('x')}; B=w._altoBass; B.state.files=FILES.slice(); B.propose(); await tick(); B.ok(); await tick();
  out.nostorage={calls:B.sim.calls>0};
  out.text=B.NOTICE_TEXT; out.v=B.NOTICE_V;
  console.log(JSON.stringify(out)); })();
"""


@pytest.fixture(scope="module")
def notice(on, tmp_path_factory):
    if not NODE:
        pytest.skip("node is not installed")
    d = tmp_path_factory.mktemp("bassn")
    (d / "bundle.js").write_text(on["bundle"], encoding="utf-8")
    (d / "drive.js").write_text(NOTICE_DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(d / "drive.js"), str(d / "bundle.js")], capture_output=True, text=True, check=True).stdout
    return json.loads(out.splitlines()[-1])


def test_notice_first_send_shows_it_and_sends_nothing_until_ok(notice):                      # (a)
    assert notice["a"] == {"notice": True, "calls": 0}
    assert notice["build"] == {"notice": True, "calls": 0}


def test_notice_after_ok_calls_proceed_and_it_does_not_come_back(notice):                     # (b)
    assert notice["b1"]["notice"] is False and notice["b1"]["calls"] is True and notice["b1"]["ack"] == notice["v"]
    assert notice["b2"] == {"notice": False, "more": True}
    assert notice["nostorage"]["calls"] is True                                              # the page works without storage


def test_notice_not_now_sends_nothing_and_remembers_nothing(notice):                          # (c)
    assert notice["c"] == {"notice": False, "calls": 0, "ack": None}


def test_notice_text_is_exact_and_links_the_privacy_policy(notice, on):                       # (d)
    assert notice["text"] == NOTICE_TEXT and NOTICE_TEXT in on["bundle"]
    assert "Privacy Policy" in on["bundle"] and "OK, continue" in on["bundle"] and "Not now" in on["bundle"]
    assert bass_ui.PRIVACY_URL == "/privacy" and "var NOTICE_V='" + bass_ui.NOTICE_VERSION + "'" in on["bundle"]
    link = on["bundle"].split('class="bs-link"')[1].split("Privacy Policy")[0]
    assert "href=" in link and 'target="_blank"' in link and 'rel="noopener"' in link          # opens in a new tab, so the Bass state is kept
    assert "PRIVACY_URL='/privacy'" in on["bundle"]                                         # relative, same host


def test_notice_a_new_version_shows_it_again(notice):                                         # (e)
    assert notice["e_old"] == {"notice": True, "calls": 0}
    assert notice["e_cur"] == {"notice": False, "calls": True}


def test_notice_adds_nothing_to_the_pages(on, off):                                           # (f) flag-off carries none of it; flag-on pages carry no notice text
    for page in (off["tl"], off["home"]):
        assert "Bass uses AI" not in page and "alto-bass-ack" not in page
    assert "Bass uses AI (Claude" not in on["tl"] and "Bass uses AI (Claude" not in on["home"]    # it lives in the hosted bundle only


# ── "Turn into another format…": Bass's route for the homepage sheet (home_template.html) ──

def test_the_home_page_registers_bass_as_a_route_for_the_four_formats_it_can_make_only_when_the_ui_is_on(on, off):
    h = on["home"]
    assert "window._altoConvertRoutes" in h and "formats: ['timeline', 'outline', 'system', 'lanes']" in h and "label: 'Make it with Bass'" in h
    assert "window._altoBass.convert(pg, fmt, ui)" in h and on["path"] in h and "alto-bass-off" in h       # the route hides with the rest of Bass
    # flag off: Bass registers nothing. (Main's own sheet names window._altoConvertRoutes in a comment, so the name alone proves nothing.)
    assert "window._altoBass" not in off["home"] and "Make it with Bass" not in off["home"] and on["path"] not in off["home"]


CONVERT_DRIVER = NOTICE_DRIVER.split("const tick=")[0] + r"""
const tick=()=>new Promise(r=>setTimeout(r,60));
function ui(yes){ const u={log:[],asked:[]}; u.status=t=>u.log.push(t); u.confirm=(t,l)=>{ u.asked.push([t,l]); return Promise.resolve(yes); }; u.close=()=>u.log.push('closed'); return u; }
(async()=>{ const out={};
  const w0=mk({}), V=w0._altoBass.NOTICE_V;
  let w=mk({'alto-bass-ack-anon':V}), B=w._altoBass, u=ui(true);
  await B.convert({tid:'t1'},'timeline',u);
  out.ok={calls:B.sim.calls, asked:u.asked, last:u.log[u.log.length-1]};
  w=mk({'alto-bass-ack-anon':V}); B=w._altoBass; u=ui(false);
  await B.convert({tid:'t1'},'outline',u);
  out.no={calls:B.sim.calls, log:u.log};
  w=mk({}); B=w._altoBass; u=ui(true);
  await B.convert({tid:'t1'},'timeline',u);
  out.unacked={calls:B.sim.calls, log:u.log};
  w=mk({'alto-bass-ack-anon':V}); B=w._altoBass; u=ui(true);
  await B.convert({},'timeline',u);
  out.notid={calls:B.sim.calls, log:u.log};
  console.log(JSON.stringify(out)); })();
"""


def test_the_bundles_convert_asks_before_it_spends_then_says_the_cards_in_and_out(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    (tmp_path / "bundle.js").write_text(on["bundle"], encoding="utf-8")
    (tmp_path / "drive.js").write_text(CONVERT_DRIVER, encoding="utf-8")
    out = json.loads(subprocess.run([NODE, str(tmp_path / "drive.js"), str(tmp_path / "bundle.js")], capture_output=True, text=True, check=True).stdout.splitlines()[-1])
    assert out["ok"]["calls"] == 2 and len(out["ok"]["asked"]) == 1                       # an estimate, then (after the yes) the conversion
    q, label = out["ok"]["asked"][0]
    assert q == "Bass will make a new timeline from this one\u2019s own 61 cards and add nothing. About 200 credits. Go on?" and label == "Make it (about 200 credits)"
    assert out["ok"]["last"] == "Done: 61 cards in, 61 out. It is a new timeline in this project; the original is unchanged."
    assert out["no"]["calls"] == 1 and not any("Done" in t for t in out["no"]["log"])    # a no after the estimate spends nothing
    assert out["unacked"]["calls"] == 0 and "short notice" in out["unacked"]["log"][0]    # the first-use notice comes first
    assert out["notid"]["calls"] == 0 and "cannot find" in out["notid"]["log"][0]


# ── the Upload step's "or paste your notes" field: pasted text is a text material, Next is enabled by it ──
PASTE_DRIVER = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const win={setTimeout,clearTimeout,document:doc,localStorage:{setItem(){},getItem(){return null}},location:{hash:''}};
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const B=win._altoBass; B.sim.delay=0; const tick=()=>new Promise(r=>setTimeout(r,60));
(async()=>{ const out={};
  B.ok(); B.state.files=[]; B.state.paste='  Hearsay: an out-of-court statement offered for its truth.  '; B.propose(); await tick(); B.ok(); await tick();
  out.chips=B.state.chips && B.state.chips.title; out.step=B.state.step;
  console.log(JSON.stringify(out)); })();
"""


def test_paste_a_pasted_text_alone_is_proposed_as_a_text_material(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    (tmp_path / "bundle.js").write_text(on["bundle"], encoding="utf-8")
    (tmp_path / "drive.js").write_text(PASTE_DRIVER, encoding="utf-8")
    out = json.loads(subprocess.run([NODE, str(tmp_path / "drive.js"), str(tmp_path / "bundle.js")], capture_output=True, text=True, check=True).stdout.splitlines()[-1])
    assert out["chips"] == "Pasted Notes"                                   # the sim titles the plan from the first material's name: pasted-notes.txt


def test_paste_the_upload_step_carries_the_field_and_it_enables_next(on):
    b = on["bundle"]
    assert 'id="bs-paste"' in b and "Or paste your notes" in b and "Bass writes only from what you add" in b
    assert "name:'pasted-notes.txt',kind:'notes'" in b
    assert "S.files.length||pasted()||(S.using&&S.using.files.length)" in b       # Next is enabled by pasted text alone
    assert b.count("materials:mats()") == 1 and "materials:ms" in b                  # build and propose both send it
    css = bass_ui.CSS if hasattr(bass_ui, "CSS") else b
    assert "font-size:16px" in b or "font-size:16px" in css                          # iOS does not zoom the page on focus
