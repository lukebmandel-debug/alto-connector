"""The Bass UI in BETA mode (bass_ui.BETA, brief bass-beta-allowance): no buy or paywall element renders in any state, the meter reads
"Beta credits remaining", a used-up share or pool shows the friendly message and nothing more is sent, a non-allowlisted account sees
no Bass button, and the real door carries the Firebase ID token the proxy needs. Pure `node` on stubs (no browser, no network)."""
import json
import subprocess

import pytest

from test_bass_ui import NODE, _facts
from alto.build import bass_ui

USED = "Your Bass beta credits are used up. Thank you for testing Bass!"
STATES = ("home", "format", "upload", "review", "estimate", "build", "built", "edit", "offtopic", "nocredits", "busy", "paused",
          "refused", "capped", "error", "stopped")
PAYWALL = ("Add credits", "addcr", "Buying credits", "buy", "purchase", "$", "Out of credits", "Stripe", "card number")

STUBS = r"""
const vm=require('vm'), fs=require('fs');
function cl(){ const s=new Set(); return {add:(...a)=>a.forEach(x=>s.add(x)), remove:(...a)=>a.forEach(x=>s.delete(x)), contains:x=>s.has(x),
  toggle:(x,on)=>{ on=on===undefined?!s.has(x):!!on; on?s.add(x):s.delete(x); return on; }}; }
function el(){ return {style:{},classList:cl(),innerHTML:'',appendChild(){},setAttribute(){},getAttribute(){return null},addEventListener(){},
  removeEventListener(){},remove(){},querySelector(){return null},querySelectorAll(){return []}}; }
function mk(src,o){ o=o||{}; const appended=[], fetches=[], store=Object.assign({},o.store||{});
  const doc={createElement:el,head:{appendChild(){}},body:{appendChild(x){appended.push(x)}},documentElement:el(),querySelector(){return null},
    querySelectorAll(){return []},getElementById(){return null},addEventListener(){},removeEventListener(){}};
  const win={setTimeout,clearTimeout,document:doc,location:{hash:''},addEventListener(){},
    localStorage:{setItem(k,v){store[k]=String(v)},getItem(k){return k in store?store[k]:null}}};
  win.window=win;
  if(o.base) win._ALTO_BASS_BASE=o.base;
  if(o.user) win.AltoCloud={user:{uid:'u1',getIdToken:()=>Promise.resolve('tok-1')}};
  win.fetch=(url,init)=>{ const body=JSON.parse(init.body); fetches.push({url,init,action:body.action}); if(o.reject) return Promise.reject(new Error('net'));
    const r=(o.answers||{})[body.action]||{ok:true,status:'ok'}, st=r._http||200;
    return Promise.resolve({ok:st<300,status:st,json:()=>Promise.resolve(r)}); };
  vm.createContext(win); vm.runInContext(src,win);
  return {win,appended,fetches,store,cls:doc.documentElement.classList,html:()=>appended.length?appended[appended.length-1].innerHTML:''};
}
const tick=()=>new Promise(r=>setTimeout(r,30));
"""

DRIVER = STUBS + r"""
const src=fs.readFileSync(process.argv[2],'utf8'), STATES=JSON.parse(process.argv[3]);
(async()=>{ const out={renders:{}};
  // every state, in each of the three places the UI is drawn
  const w=mk(src), B=w.win._altoBass; B.sim.delay=0;
  for(const mode of ['wizard','panel','embed']) for(const s of STATES){ B.dev(s,mode); out.renders[mode+':'+s]=w.html(); }
  const BASE='https://px.test/bass', OK_BAL={ok:true,status:'ok',credits:900,label:'900 beta credits remaining',available:true,beta:true};
  const ACK={'alto-bass-ack-u1':B.NOTICE_V};
  // (a) the real door: Bearer token, no cookies; an allowed balance un-hides the buttons
  let r=mk(src,{base:BASE,user:true,answers:{balance:OK_BAL},store:ACK}); r.cls.add('alto-bass-off'); r.win._altoBass.open('panel'); await tick();
  const f0=r.fetches[0];
  out.door={n:r.fetches.length,url:f0.url,auth:f0.init.headers.authorization,creds:f0.init.credentials||null,off:r.cls.contains('alto-bass-off'),html:r.html()};
  // (b) a build answered "used up": the friendly message, and the next tries send nothing
  const USED={ok:false,status:'no_credits',code:'beta_credits_used',message:'Your Bass beta credits are used up. Thank you for testing Bass!',
    action_id:null,work_saved:false,credits:null,retryable:false,events:[]};
  r=mk(src,{base:BASE,user:true,answers:{balance:OK_BAL,build:USED},store:ACK}); let X=r.win._altoBass; X.open('wizard'); await tick();
  X.state.chips={title:'T',acts:[{label:'A'}],entities:[],fields:[],card_estimate:6}; X.build(true); await tick();
  const n=r.fetches.length; X.state.files=[{name:'n.txt',kind:'notes',text:'x'}]; X.propose(); await tick();
  const again=await X.call('edit',{timeline_id:'t',text:'add a card'});
  out.used={n_before:n,n_after:r.fetches.length,html:r.html(),again:again.code,alert:X.state.alert};
  // (c) the pool or share already used up: shown the moment Bass opens
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{available:false,code:'beta_credits_used',message:USED.message})},store:ACK});
  r.win._altoBass.open('panel'); await tick(); const m=r.fetches.length; await r.win._altoBass.call('propose',{materials:[]});
  out.open_used={html:r.html(),more:r.fetches.length-m};
  // (c2) today's beta limit: the server's own words, not the generic pause text
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{available:false,code:'beta_daily_full',status:'ok',message:"Today's beta limit has been reached. Nothing was charged. Please try again tomorrow."})},store:ACK});
  r.win._altoBass.open('panel'); await tick(); out.daily={html:r.html()};
  // (c3) the chip on the real path: used up on open reads 0; a build answered "used up" moves it 142 -> 0; a daily limit leaves it alone
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{available:false,code:'beta_credits_used',credits:0,message:USED.message})},store:ACK});
  r.win._altoBass.open('panel'); await tick(); out.chip_open_used={bal:r.win._altoBass.state.bal,stored:r.store['alto-bass-bal']||null};
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{credits:142}),build:USED},store:ACK}); X=r.win._altoBass; X.open('wizard'); await tick();
  X.state.chips={title:'T',acts:[{label:'A'}],entities:[],fields:[],card_estimate:6}; const before=X.state.bal; X.build(true); await tick();
  out.chip_mid_used={before:before,after:X.state.bal,stored:r.store['alto-bass-bal']||null};
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{credits:142}),build:{ok:false,status:'capped',code:'beta_daily_full',message:'Today\'s beta limit has been reached.',credits:null,retryable:false,events:[]}},store:ACK}); X=r.win._altoBass; X.open('wizard'); await tick();
  X.state.chips={title:'T',acts:[{label:'A'}],entities:[],fields:[],card_estimate:6}; const b2=X.state.bal; X.build(true); await tick();
  out.chip_daily={before:b2,after:X.state.bal};
  // (c4) the chip is the simulator's 142 only without a backend: with a base it stays blank until the first real answer
  r=mk(src,{base:BASE,user:true,reject:true,store:ACK}); r.win._altoBass.open('panel'); await tick();
  out.chip_unreachable={bal:r.win._altoBass.state.bal,html:r.html()};
  r=mk(src,{base:BASE,user:true,answers:{balance:Object.assign({},OK_BAL,{credits:777})},store:ACK}); r.win._altoBass.open('panel'); await tick();
  out.chip_real={bal:r.win._altoBass.state.bal,html:r.html()};
  r=mk(src,{user:true,store:ACK}); r.win._altoBass.open('panel'); await tick();
  out.chip_sim={bal:r.win._altoBass.state.bal,html:r.html()};
  // (d) not on the allowlist: buttons hidden, a plain note, nothing more is sent
  const OFF={ok:false,status:'paused',code:'bass_off',message:'Bass is not switched on for this account yet.',available:false,action_id:null,work_saved:false,credits:null,retryable:false,events:[]};
  r=mk(src,{base:BASE,user:true,answers:{balance:OFF},store:ACK}); r.win._altoBass.open('panel'); await tick();
  const k=r.fetches.length; await r.win._altoBass.call('build',{}); await r.win._altoBass.call('estimate',{kind:'build'});
  out.off={off:r.cls.contains('alto-bass-off'),more:r.fetches.length-k,html:r.html(),cached:r.store['alto-bass-ok-u1']||null};
  // (d2) the Beta Terms not accepted: the server's own message, no button, nothing more is sent
  const TERMS={ok:false,status:'paused',code:'terms_required',message:'Please accept the Beta Terms to use Bass. Sign in again to see the box.',available:false,beta:true,action_id:null,work_saved:false,credits:null,retryable:false,events:[]};
  r=mk(src,{base:BASE,user:true,answers:{balance:TERMS},store:ACK}); r.win._altoBass.open('panel'); await tick();
  const k2=r.fetches.length; await r.win._altoBass.call('build',{});
  out.terms={more:r.fetches.length-k2,off:r.cls.contains('alto-bass-off'),html:r.html()};
  // (e) signed out: nothing is sent at all
  r=mk(src,{base:BASE,user:false}); const so=await r.win._altoBass.call('balance',{});
  out.signedout={n:r.fetches.length,code:so.code};
  console.log(JSON.stringify(out)); })();
"""

GATE_DRIVER = STUBS + r"""
const src=fs.readFileSync(process.argv[2],'utf8');
(async()=>{ const out={}; const BASE='https://px.test/bass';
  let r=mk(src,{}); await tick(); out.nobase={off:r.cls.contains('alto-bass-off'),n:r.fetches.length};
  r=mk(src,{base:BASE}); await tick(); out.signedout={off:r.cls.contains('alto-bass-off'),n:r.fetches.length};
  r=mk(src,{base:BASE,user:true,answers:{balance:{ok:false,status:'paused',code:'bass_off'}}}); await tick();
  out.stranger={off:r.cls.contains('alto-bass-off'),n:r.fetches.length,auth:r.fetches[0].init.headers.authorization};
  r=mk(src,{base:BASE,user:true,answers:{balance:{ok:true,status:'ok',credits:900}}}); await tick();
  out.tester={off:r.cls.contains('alto-bass-off'),n:r.fetches.length};
  r=mk(src,{base:BASE,user:true,answers:{balance:{ok:false,status:'no_credits',code:'beta_credits_used'}}}); await tick();
  out.used_up={off:r.cls.contains('alto-bass-off')};                         // a tester who is used up still sees Bass (and its message)
  r=mk(src,{base:BASE,user:true,store:{'alto-bass-ok-u1':JSON.stringify({ok:true,t:Date.now()})}}); await tick();
  out.cached={off:r.cls.contains('alto-bass-off'),n:r.fetches.length};
  r=mk(src,{base:BASE,user:true,answers:{balance:{_http:401,ok:false,message:'Please sign in again.'}}}); await tick();
  out.badtoken={off:r.cls.contains('alto-bass-off')};
  console.log(JSON.stringify(out)); })();
"""


def _node(tmp, driver, src, *args):
    (tmp / "src.js").write_text(src, encoding="utf-8")
    (tmp / "drive.js").write_text(driver, encoding="utf-8")
    p = subprocess.run([NODE, str(tmp / "drive.js"), str(tmp / "src.js"), *args], capture_output=True, text=True, check=True)
    return json.loads(p.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def on():
    return _facts(True)


@pytest.fixture(scope="module")
def ui(on, tmp_path_factory):
    if not NODE:
        pytest.skip("node is not installed")
    return _node(tmp_path_factory.mktemp("bassbeta"), DRIVER, on["bundle"], json.dumps(STATES))


def test_the_ui_is_built_in_beta_mode():
    assert bass_ui.BETA is True and "var BETA=true;" in bass_ui.ASSET


def test_no_paywall_element_renders_in_any_state_or_place(ui):
    assert len(ui["renders"]) == 3 * len(STATES)
    for key, html in ui["renders"].items():
        assert html, key
        low = html.lower()
        for bad in PAYWALL:
            assert bad.lower() not in low, (key, bad)


def test_the_credit_display_reads_beta_credits_remaining(ui):
    for key in ("panel:edit", "wizard:upload", "embed:upload"):
        assert "Beta credits remaining: 142" in ui["renders"][key], key
    est = ui["renders"]["wizard:estimate"]
    assert "142 beta credits remaining" in est and "bigger than what is left" in est and 'data-a="go"' not in est


def test_used_up_shows_the_friendly_message_in_every_place(ui):
    for mode in ("wizard", "panel", "embed"):
        h = ui["renders"][mode + ":nocredits"]
        assert "Beta credits used up" in h and USED in h and "Your work so far is saved." in h, mode
        assert 'data-a="retry"' not in h


def test_the_real_door_sends_the_firebase_token_and_no_cookies(ui, on):
    d = ui["door"]
    assert d["n"] == 1 and d["url"] == "https://px.test/bass" and d["auth"] == "Bearer tok-1" and d["creds"] is None
    assert d["off"] is False and "Beta credits remaining: 900" in d["html"]
    assert "credentials:'include'" not in on["bundle"]


def test_after_a_used_up_answer_nothing_more_is_sent(ui):
    u = ui["used"]
    assert u["n_after"] == u["n_before"] and u["again"] == "beta_credits_used"
    assert "Beta credits used up" in u["html"] and USED in u["html"] and "Add credits" not in u["html"]
    o = ui["open_used"]
    assert o["more"] == 0 and "Beta credits used up" in o["html"] and USED in o["html"]
    assert "try again tomorrow" in ui["daily"]["html"]


def test_terms_not_accepted_shows_the_servers_message_with_no_paywall_and_sends_nothing_more(ui):
    t = ui["terms"]
    assert t["more"] == 0 and t["off"] is False
    assert "Please accept the Beta Terms to use Bass. Sign in again to see the box." in t["html"] and "Beta Terms" in t["html"]
    assert "Add credits" not in t["html"] and 'data-a="retry"' not in t["html"] and 'data-a="addcr"' not in t["html"]


def test_the_chip_reads_zero_once_used_up_and_keeps_its_value_for_a_daily_limit(ui):
    assert ui["chip_open_used"]["bal"] == 0 and ui["chip_open_used"]["stored"] == "0"            # used up when Bass opens
    m = ui["chip_mid_used"]
    assert m["before"] == 142 and m["after"] == 0 and m["stored"] == "0"                           # a build answered "used up"
    d = ui["chip_daily"]
    assert d["before"] == 142 and d["after"] == 142                                                  # today's limit: nothing was spent


def test_the_chip_never_shows_the_simulator_number_when_a_real_backend_is_set(ui):
    u = ui["chip_unreachable"]                                                                       # proxy unreachable (CSP, offline, error)
    assert u["bal"] is None and "Beta credits remaining" not in u["html"] and "142" not in u["html"]
    r = ui["chip_real"]                                                                                # the first real answer fills it in
    assert r["bal"] == 777 and "142" not in r["html"]
    s = ui["chip_sim"]                                                                                 # no base: the simulator number, as before
    assert s["bal"] == 142 and "Beta credits remaining: 142" in s["html"]


def test_a_non_allowlisted_account_sees_no_bass_and_sends_nothing_more(ui):
    o = ui["off"]
    assert o["off"] is True and o["more"] == 0 and "Bass is for beta testers" in o["html"]
    assert json.loads(o["cached"])["ok"] is False
    assert ui["signedout"] == {"n": 0, "code": "signin"}


def test_the_inline_gate_hides_the_buttons_until_the_proxy_says_yes(tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    g = _node(tmp_path, GATE_DRIVER, bass_ui._GATE)
    assert g["nobase"] == {"off": False, "n": 0}                          # the simulator build: nothing hidden, nothing sent
    assert g["signedout"] == {"off": True, "n": 0}
    assert g["stranger"] == {"off": True, "n": 1, "auth": "Bearer tok-1"}
    assert g["tester"] == {"off": False, "n": 1} and g["used_up"] == {"off": False}
    assert g["cached"] == {"off": False, "n": 0} and g["badtoken"] == {"off": True}


def test_pages_with_a_proxy_url_carry_the_gate_and_the_hiding_css(monkeypatch, on):
    assert "_altoBassGate" not in on["tl"] and "_altoBassGate" not in on["home"]        # no URL: the simulator, no gate
    monkeypatch.setenv(bass_ui.BASE_ENV, "https://px.test/bass")
    f = _facts(True)
    for page in (f["tl"], f["home"]):
        assert 'window._ALTO_BASS_BASE=window._ALTO_BASS_BASE||"https://px.test/bass"' in page and "_altoBassGate" in page
    assert "html.alto-bass-off .aep-bass" in f["tl"] and "html.alto-bass-off #nt-sw" in f["home"]
    assert len(f["tl"]) - len(on["tl"]) < 2000
