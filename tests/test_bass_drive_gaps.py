"""Bass "Add from Drive": the three code gaps of the first head (ORG/it/bass-drive-deploy.md). MOCK ONLY: no Google call, no real id/key/token, no browser.
(a) the Picker's wider CSP exists on ONE path only; (b) sign-out and account deletion revoke + delete the Drive token; (c) the three env vars fail closed."""
import json
import re
import subprocess
import sys

import pytest

from bass_support import ROOT
from test_bass_drive import A, MockGoogle, TOK_A, connected, drive, stack, DriveConfig, DriveService, CID  # noqa: F401
from test_bass_ui import NODE, bass_ui, on, off  # noqa: F401
from alto import publish_static as ps
from alto.build import drive_picker_page as PK

BASE = "https://bass-proxy-123456789012.us-central1.run.app"


def _env(monkeypatch, ui, base=BASE):
    for k, v in (("ALTO_BASS_UI", ui), ("ALTO_BASS_BASE", base)):
        monkeypatch.delenv(k, raising=False) if v is None else monkeypatch.setenv(k, v)


def _by_source(rules):
    return {r["source"]: {h["key"]: h["value"] for h in r["headers"]} for r in rules}


# -- (a) CSP -----------------------------------------------------------------------------------------------------------------
def test_the_picker_csp_is_exactly_the_google_origins_and_nothing_loose():
    d = dict(p.split(" ", 1) for p in PK.PICKER_CSP.split("; "))
    assert d["script-src"] == "'self' https://apis.google.com https://accounts.google.com/gsi/client"
    assert d["frame-src"] == "https://docs.google.com https://accounts.google.com/gsi/"
    assert d["connect-src"] == "https://accounts.google.com/gsi/" and d["style-src"] == "'self' https://accounts.google.com/gsi/style"
    assert d["default-src"] == "'none'" and d["object-src"] == "'none'" and d["base-uri"] == "'none'" and d["form-action"] == "'none'"
    assert d["frame-ancestors"] == "'none'"
    assert "unsafe-inline" not in PK.PICKER_CSP and "unsafe-eval" not in PK.PICKER_CSP and "*" not in PK.PICKER_CSP and "wasm" not in PK.PICKER_CSP
    assert set(re.findall(r"https://[a-z.]+", PK.PICKER_CSP)) == {"https://apis.google.com", "https://accounts.google.com", "https://docs.google.com"}


def test_only_the_picker_path_gets_it_and_the_site_wide_csp_is_untouched(monkeypatch):
    _env(monkeypatch, None, None)
    base = ps._security_headers()
    assert "/drive-picker/**" not in _by_source(base)                              # no Bass in the build: no rule at all
    _env(monkeypatch, "1", BASE)
    on_rules = ps._security_headers()
    src = _by_source(on_rules)
    assert src["/drive-picker/**"] == {"Content-Security-Policy": PK.PICKER_CSP}
    wide = src["**"]["Content-Security-Policy"]
    for o in ("accounts.google.com", "docs.google.com"):
        assert o not in wide                                                       # never site-wide
    assert wide.replace(" " + BASE, "") == _by_source(base)["**"]["Content-Security-Policy"]    # the only change: the Bass proxy's connect-src origin (already tested)
    assert "accounts.google.com" not in src["/connect/**"]["Content-Security-Policy"]
    assert [s for s in src if "picker" in s] == ["/drive-picker/**"]


def test_no_picker_rule_without_a_proxy_base(monkeypatch):
    _env(monkeypatch, "1", None)
    assert ps._picker_csp() is None and "/drive-picker/**" not in _by_source(ps._security_headers())
    _env(monkeypatch, None, BASE)
    assert ps._picker_csp() is None


def test_the_picker_page_has_no_inline_code_and_pins_the_scope():
    h, js = PK.picker_page(), PK.picker_js()
    assert re.findall(r"<script[^>]*>", h) == ['<script src="picker.js">'] and "</script>" in h and " style=" not in h and "<style" not in h
    assert not re.search(r"\son[a-z]+=", h) and "javascript:" not in h
    assert "'https://www.googleapis.com/auth/drive.file'" in js and "drive.readonly" not in js and "auth/drive'" not in js
    assert "e.origin!==OWN" in js and "e.source!==op" in js and "postMessage({alto:'drive-picked',result:r},OWN)" in js and "'*'" not in js
    assert "localStorage" not in js and "sessionStorage" not in js and "eval(" not in js
    assert set(re.findall(r"https://[a-z.]+/[\w/.]*", js)) <= {"https://accounts.google.com/gsi/client", "https://apis.google.com/js/api.js", "https://www.googleapis.com/auth/drive.file"}


def test_the_site_never_loads_a_google_script_on_its_own_pages(on):
    b = on["bundle"]
    assert "accounts.google.com" not in b and "apis.google.com" not in b and "gapi" not in b                 # only /drive-picker/ does
    assert "window.open('/drive-picker/'" in b and "e.origin!==o||e.source!==w" in b and ",o);" in b


PICKER_NODE = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8'); const posted=[]; let closed=0, handler=null, loaded=[];
const opener={postMessage(m,o){ posted.push([m,o]); }};
const doc={getElementById(){return {textContent:''}}, createElement(){ const x={}; setTimeout(()=>{ loaded.push(x.src); },0); return x; }, head:{appendChild(){}}};
const win={opener, document:doc, location:{origin:'https://site.example'}, close(){ closed++; }, addEventListener(t,f){ if(t==='message') handler=f; }, setTimeout:setTimeout};
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const out={ready:posted.slice()};
handler({origin:'https://evil.example',source:opener,data:{alto:'drive-config',cfg:{client_id:'a.b',api_key:'k',app_id:'1'}}});   // wrong origin
handler({origin:'https://site.example',source:{},data:{alto:'drive-config',cfg:{client_id:'a.b',api_key:'k',app_id:'1'}}});          // not our opener
out.afterForeign=posted.length; out.loadedForeign=loaded.length;
handler({origin:'https://site.example',source:opener,data:{alto:'drive-config',cfg:{client_id:'a b<',api_key:'k',app_id:'1'}}});   // malformed
out.bad=posted.slice(out.afterForeign);
setTimeout(()=>{ out.closed=closed; console.log(JSON.stringify(out)); },200);
"""

OPENER_NODE = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const listeners=[]; const sent=[]; const popup={closed:false,postMessage(m,o){ sent.push([m,o]); }}; let opened=[];
const win={setTimeout,clearTimeout,setInterval,clearInterval,document:doc,localStorage:{setItem(){},getItem(){return null}},location:{hash:'',origin:'https://site.example'},
  addEventListener(t,f){ listeners.push(f); },removeEventListener(t,f){ const i=listeners.indexOf(f); if(i>=0) listeners.splice(i,1); },
  open(u,n,f){ opened.push(u); return popup; },_ALTO_BASS_BASE:''};
win.window=win; vm.createContext(win); vm.runInContext(src,win);
(async()=>{ const out={};
 // reach googlePick through the seam-free path: drivePick uses window._altoDrivePick||googlePick, so call the bundle's own through a stub-less state
 const B=win._altoBass; const pick=B.drive.popup;
 const p=pick({client_id:'c1',api_key:'k1',app_id:'a1'});
 const fire=(o,s,d)=>listeners.slice().forEach(f=>f({origin:o,source:s,data:d}));
 fire('https://evil.example',popup,{alto:'drive-ready'}); fire('https://site.example',{},{alto:'drive-ready'});
 out.afterForeign=sent.length;
 fire('https://site.example',popup,{alto:'drive-ready'}); out.config=sent.slice();
 fire('https://evil.example',popup,{alto:'drive-picked',result:{token:'stolen',ids:['x']}});
 fire('https://site.example',popup,{alto:'drive-picked',result:{token:'ya29.good',ids:['i1']}});
 out.res=await p; out.opened=opened; out.listeners=listeners.length;
 const q=pick({client_id:'c1',api_key:'k1',app_id:'a1'}); popup.closed=true; out.closedRes=await q;
 console.log(JSON.stringify(out)); process.exit(0); })();
"""


def _run(tmp_path, script, arg):
    (tmp_path / "s.js").write_text(script, encoding="utf-8")
    return json.loads(subprocess.run([NODE, str(tmp_path / "s.js"), str(arg)], capture_output=True, text=True, check=True).stdout.splitlines()[-1])


def test_the_picker_page_talks_to_its_own_opener_only(tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    (tmp_path / "p.js").write_text(PK.picker_js(), encoding="utf-8")
    out = _run(tmp_path, PICKER_NODE, tmp_path / "p.js")
    assert out["ready"] == [[{"alto": "drive-ready"}, "https://site.example"]]
    assert out["afterForeign"] == 1 and out["loadedForeign"] == 0                  # a foreign origin / a foreign window starts nothing
    assert out["bad"] == [[{"alto": "drive-picked", "result": None}, "https://site.example"]] and out["closed"] == 1     # malformed ids: answered null, closed


def test_the_sheet_opens_the_picker_page_and_accepts_only_its_same_origin_answer(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    (tmp_path / "b.js").write_text(on["bundle"], encoding="utf-8")
    out = _run(tmp_path, OPENER_NODE, tmp_path / "b.js")
    assert out["opened"][0] == "/drive-picker/" and out["afterForeign"] == 0
    assert out["config"] == [[{"alto": "drive-config", "cfg": {"client_id": "c1", "api_key": "k1", "app_id": "a1"}}, "https://site.example"]]
    assert out["res"] == {"token": "ya29.good", "ids": ["i1"]} and out["listeners"] == 0       # the foreign "stolen" answer was ignored; no listener left behind
    assert out["closedRes"] is None


SIGNOUT_NODE = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const order=[]; let discOk=true;
const win={setTimeout,clearTimeout,document:doc,localStorage:{setItem(){},getItem(){return null}},location:{hash:''},_ALTO_BASS_BASE:'https://bass.example/run',
  AltoCloud:{user:{uid:'u1',getIdToken(){return Promise.resolve('id-token');}},signOut(){ order.push('signOut'); return Promise.resolve(); }}};
win.fetch=(url,o)=>{ const b=JSON.parse(o.body); order.push(b.args&&b.args.op||b.action);
  const out=b.args.op==='disconnect'?(discOk?{ok:true,status:'ok',connected:false}:{ok:false,status:'error',code:'x',message:'x'}):b.args.op==='add'?{ok:true,status:'ok',files:[],failed:0}:{ok:true,status:'ok',connected:true};
  return Promise.resolve({ok:true,status:200,json(){return Promise.resolve(out);}}); };
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const B=win._altoBass;
(async()=>{ const out={};
 await win.AltoCloud.signOut(); out.clean=order.slice(); order.length=0;                      // nothing live: straight to sign-out
 discOk=false; await B.drive.flow({token:'ya29.SECRET_TOKEN_0123456789abcdef',ids:['aaaaaaaaaa']},'sc1'); order.length=0;   // the last disconnect failed: a token may still be live
 discOk=true; await win.AltoCloud.signOut(); out.live=order.slice(); order.length=0;
 await win.AltoCloud.signOut(); out.after=order.slice();
 console.log(JSON.stringify(out)); process.exit(0); })();
"""


def test_sign_out_on_the_page_revokes_a_still_live_drive_token_first(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    (tmp_path / "b.js").write_text(on["bundle"], encoding="utf-8")
    out = _run(tmp_path, SIGNOUT_NODE, tmp_path / "b.js")
    assert out["clean"] == ["signOut"] and out["live"] == ["disconnect", "signOut"] and out["after"] == ["signOut"]


# -- (b) revoke on sign-out and on account deletion ----------------------------------------------------------------------------
def test_sign_out_revokes_at_google_and_deletes_every_trace(tmp_path):
    s = stack(tmp_path)
    connected(s)
    s.svc.sign_out(A)
    assert s.google.revoked == [TOK_A]
    assert not [k for k in s.store.docs if k.startswith(("bass_drive/", "bass_drive_tok/"))]
    assert "oauth2.googleapis.com/revoke" in [c["url"] for c in s.google.calls][-1]
    s.svc.sign_out(A)                                                              # again: nothing left, nothing breaks, no second revoke
    assert s.google.revoked == [TOK_A]


def test_a_google_outage_on_revoke_still_deletes_the_record(tmp_path):
    s = stack(tmp_path)
    connected(s)
    def boom(*a, **k):
        raise DR_ERR("drive_unavailable")
    from alto.bass.drive import DriveError as DR_ERR
    s.google.request = boom
    s.svc.sign_out(A)
    assert not [k for k in s.store.docs if k.startswith(("bass_drive/", "bass_drive_tok/"))]


def test_the_account_deleted_trigger_revokes_the_drive_token_and_leaves_none(tmp_path, monkeypatch):
    s = stack(tmp_path)
    connected(s)
    sid = [k for k in s.store.docs if k.startswith("bass_docs/")] or [None]
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import main as MAIN
    from alto.bass import drive as DRV
    monkeypatch.setattr(MAIN, "_docs_env", lambda: (s.store, None))
    monkeypatch.setattr(MAIN, "_clock", s.clock)
    monkeypatch.setattr(DRV, "Transport", lambda *a, **k: s.google)               # the revoke endpoint is the mock, never Google
    monkeypatch.delenv("BASS_RESEARCH_BUCKET", raising=False)
    out = MAIN.bass_docs_account_deleted({"uid": A})
    assert out["drive"] is True and s.google.revoked == [TOK_A]
    assert not [k for k in s.store.docs if k.startswith(("bass_drive/", "bass_drive_tok/"))]
    assert TOK_A not in json.dumps(s.store.docs, default=str)
    assert MAIN.bass_docs_account_deleted({"uid": A})["drive"] is False            # a retry of the trigger: nothing left, no error
    assert s.google.revoked == [TOK_A]


def test_the_account_deleted_trigger_also_works_with_drive_unconfigured(tmp_path, monkeypatch):
    s = stack(tmp_path, configured=False)
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import main as MAIN
    from alto.bass import drive as DRV
    monkeypatch.setattr(MAIN, "_docs_env", lambda: (s.store, None))
    monkeypatch.setattr(MAIN, "_clock", s.clock)
    monkeypatch.setattr(DRV, "Transport", lambda *a, **k: s.google)
    for k in DriveConfig.ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("BASS_RESEARCH_BUCKET", raising=False)
    assert MAIN.bass_docs_account_deleted({"uid": A})["drive"] is False and not s.google.calls


# -- (c) the three env vars fail closed ----------------------------------------------------------------------------------------
NAMES = ("ALTO_DRIVE_CLIENT_ID", "ALTO_DRIVE_API_KEY", "ALTO_DRIVE_APP_ID")


def test_the_env_names_are_the_three_and_the_values_come_only_from_the_environment():
    assert DriveConfig.ENV == NAMES
    c = DriveConfig.from_env({NAMES[0]: " cid ", NAMES[1]: "key", NAMES[2]: "app"})
    assert c.available and (c.client_id, c.api_key, c.app_id) == ("cid", "key", "app") and c.missing() == [] and c.problem() == ""
    assert not DriveConfig.from_env({}).partial and DriveConfig.from_env({}).missing() == list(NAMES)


@pytest.mark.parametrize("gone", NAMES)
def test_any_one_missing_turns_it_off_and_names_which(tmp_path, gone, caplog):
    env = {n: "v-" + n for n in NAMES}
    del env[gone]
    c = DriveConfig.from_env(env)
    assert not c.available and c.partial and c.missing() == [gone]
    assert gone in c.problem() and "v-" not in c.problem()                         # the name, never a value
    s = stack(tmp_path, configured=False)
    with caplog.at_level("ERROR", logger="bass.beta"):
        s.svc.drive = DriveService(s.store, s.cfg, s.clock, s.svc.library, config=c, transport=s.google)
    assert gone in caplog.text and "v-" not in caplog.text
    assert drive(s, "config") == {"ok": True, "status": "ok", "available": False}
    for op, a in (("connect", {"token": TOK_A}), ("add", {"scope_id": "x", "file_ids": ["aaaaaaaaaa"]}), ("disconnect", {})):
        assert drive(s, op, **a)["code"] == "drive_off"                            # a plain message to the page, no variable name
    assert not s.google.calls


def test_a_partly_set_proxy_stops_at_cold_start_with_a_clear_message(monkeypatch):
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import main as MAIN
    for k, v in (("GCP_PROJECT", "p"), ("BASS_BETA_TESTERS", "3"), ("ALTO_BUCKET", "b")):
        monkeypatch.setenv(k, v)
    for n in NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv(NAMES[0], "secret-looking-value-123")
    with pytest.raises(RuntimeError) as e:
        MAIN._build()
    msg = str(e.value)
    assert NAMES[1] in msg and NAMES[2] in msg and NAMES[0] not in msg and "secret-looking" not in msg and "all three or none" in msg
    assert MAIN.DRIVE_ENV == NAMES
