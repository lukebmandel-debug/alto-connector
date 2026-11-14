"""Bass "Add from Drive" on the page (alto/build/bass_ui_docs.py): the button, its flow and its hiding. Python plus node, no browser, no network, no Anthropic
call, no Google: the Picker is never loaded (the seam `window._altoDrivePick` stands in), and the backend is a fake fetch."""
import json
import re
import subprocess

import pytest

from test_bass_ui import NODE, bass_ui, on, off  # noqa: F401

FLOW = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const sent=[]; let connectOk=true;
const win={setTimeout:setTimeout,clearTimeout:clearTimeout,document:doc,localStorage:{setItem(k,v){ sent.push(['LS',k]); },getItem(){return null}},sessionStorage:{setItem(k){ sent.push(['SS',k]); },getItem(){return null}},location:{hash:''},
  _ALTO_BASS_BASE:'https://bass.example/run', AltoCloud:{user:{uid:'u1',getIdToken(){ return Promise.resolve('id-token'); }}}};
win.fetch=(url,o)=>{ const b=JSON.parse(o.body); sent.push([url,b]);
  const out=b.action==='drive'&&b.args.op==='connect'?(connectOk?{ok:true,status:'ok',connected:true}:{ok:false,status:'refused',code:'drive_bad_token',message:'Bass could not connect to Google Drive. Please try again.'})
   :b.action==='drive'&&b.args.op==='add'?{ok:true,status:'ok',files:[{id:'f1',name:'N.txt'}],failed:0}:{ok:true,status:'ok',connected:false,balance:null};
  return Promise.resolve({ok:true,status:200,json(){return Promise.resolve(out);}}); };
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const B=win._altoBass;
(async()=>{ const out={};
 const p={token:'ya29.SECRET_TOKEN_0123456789abcdef',ids:['aaaaaaaaaa','bbbbbbbbbb']};
 out.ok=await B.drive.flow(p,'sc1'); out.tokenAfter=p.token; out.sent=sent.slice(); sent.length=0;
 connectOk=false; const q={token:'ya29.OTHER_TOKEN_0123456789abcdef',ids:['aaaaaaaaaa']};
 out.bad=await B.drive.flow(q,'sc1'); out.sentBad=sent.slice(); sent.length=0;
 out.none=await B.drive.flow(null,'sc1'); out.empty=await B.drive.flow({token:'ya29.x',ids:[]},'sc1'); out.sentNone=sent.slice();
 console.log(JSON.stringify(out)); })();
"""

SIMD = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const el=()=>({style:{},classList:{add(){},remove(){},contains(){return false}},appendChild(){},setAttribute(){},addEventListener(){},remove(){},querySelector(){return null}});
const doc={createElement:el,head:{appendChild(){}},body:{appendChild(){}},documentElement:el(),querySelector(){return null},addEventListener(){},removeEventListener(){}};
const win={setTimeout:setTimeout,clearTimeout:clearTimeout,document:doc,localStorage:{setItem(){},getItem(){return null}},location:{hash:''}};
win.window=win; vm.createContext(win); vm.runInContext(src,win);
const B=win._altoBass; B.sim.delay=0;
(async()=>{ console.log(JSON.stringify({cfg:await B.call('drive',{op:'config'}), conn:await B.call('drive',{op:'connect',token:'ya29.x'})})); })();
"""


def _node(tmp_path, script, bundle):
    (tmp_path / "b.js").write_text(bundle, encoding="utf-8")
    (tmp_path / "d.js").write_text(script, encoding="utf-8")
    out = subprocess.run([NODE, str(tmp_path / "d.js"), str(tmp_path / "b.js")], capture_output=True, text=True, check=True).stdout
    return json.loads(out.splitlines()[-1])


def test_the_button_hides_without_server_config_and_on_phones(on):
    b = on["bundle"]
    assert "Add from Drive" in b and "d.drv&&d.drv.available&&!phone()" in b          # shown only with the server's config, never on a phone
    assert re.search(r"html\.mobile \.bs-ddrive[^{]*\{display:none", b) and "classList.contains('mobile')" in b


def test_the_page_never_names_a_wider_scope_or_stores_a_token(on):
    b = on["bundle"]
    assert "drive.readonly" not in b and "auth/drive'" not in b and "auth/drive\"" not in b       # the scope comes from the server (drive.file only)
    for m in re.finditer(r"(localStorage|sessionStorage|indexedDB|document\.cookie)[^;]{0,80}", b):
        assert "token" not in m.group(0).lower() or "idtoken" in m.group(0).lower() or "getIdToken" in m.group(0), m.group(0)
    seg = b[b.index("function driveFlow"):b.index("function drivePick")]
    assert "localStorage" not in seg and "sessionStorage" not in seg and "p.token=null" in seg


def test_the_simulator_never_offers_drive(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    out = _node(tmp_path, SIMD, on["bundle"])
    assert out["cfg"]["available"] is False and out["conn"]["code"] == "drive_off"


def test_the_flow_sends_the_token_once_then_ids_then_revokes(on, tmp_path):
    if not NODE:
        pytest.skip("node is not installed")
    out = _node(tmp_path, FLOW, on["bundle"])
    ops = [(s[1]["action"], s[1]["args"]["op"]) for s in out["sent"]]
    assert ops == [("drive", "connect"), ("drive", "add"), ("drive", "disconnect")]
    assert out["sent"][0][1]["args"]["token"].startswith("ya29.")                      # the token rides ONE POST body…
    assert "ya29" not in json.dumps(out["sent"][1:]) and all("ya29" not in s[0] for s in out["sent"])   # …never again, never in an address
    assert out["sent"][1][1]["args"] == {"op": "add", "scope_id": "sc1", "file_ids": ["aaaaaaaaaa", "bbbbbbbbbb"]}      # only ids
    assert out["tokenAfter"] is None and out["ok"]["ok"] and not any(s[0] in ("LS", "SS") for s in out["sent"])
    assert [(s[1]["args"]["op"]) for s in out["sentBad"]] == ["connect", "disconnect"] and out["bad"]["code"] == "drive_bad_token"   # a refused token: no add
    assert out["none"] is None and out["empty"] is None and out["sentNone"] == []
