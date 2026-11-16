"""The /drive-picker/ page in "ref" mode (manual edit's Drive chip): it posts ONLY [{id, name, mimeType}], never the token, and revokes the token
itself. Run in node with stubbed google/gapi objects. Plain venv, no SDK, nothing skipped."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import drive_common as DC  # noqa: E402
from alto.build import drive_picker_page as PK  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
TOKEN = "ya29.TOKEN-SECRET-abcdefghijklmnop"
HARNESS = r"""
const vm=require('vm'); const code=process.argv[1]; const mode=process.argv[2]; const action=process.argv[3]; const docs=JSON.parse(process.argv[4]); const hint=process.argv[5]||undefined;
const posted=[], revoked=[], seen={mimes:null,max:null,scope:null,hint:null,tokenArg:null}; let listener=null, closed=false;
const op={postMessage:(m,o)=>{ posted.push([JSON.parse(JSON.stringify(m)),o]); }};
function chain(o){ return new Proxy(o,{get:(t,k)=>k in t?t[k]:()=>chain(o)}); }
const ctx={location:{origin:'https://alto.test'},document:{getElementById:()=>({textContent:''}),head:{appendChild(){}},createElement:()=>({})},
  setTimeout:(f,ms)=>setTimeout(f,ms), Promise, console, JSON, Array, String, Error};
ctx.window=ctx; ctx.opener=op; ctx.addEventListener=(t,f)=>{ if(t==='message') listener=f; }; ctx.close=()=>{closed=true;};
ctx.google={accounts:{oauth2:{initTokenClient:(tc)=>{ seen.scope=tc.scope; seen.hint=tc.login_hint===undefined?null:tc.login_hint;
    return {requestAccessToken:()=>setImmediate(()=>tc.callback({access_token:process.env.TOK}))}; },
  revoke:(t,cb)=>{ revoked.push(t); if(cb) cb(); }}},
 picker:{ViewId:{DOCS:'DOCS'},Feature:{MULTISELECT_ENABLED:'MS'},Action:{PICKED:'picked',CANCEL:'cancel'},
  DocsView:function(){ const s=this; this.setIncludeFolders=()=>s; this.setSelectFolderEnabled=()=>s; this.setMimeTypes=(m)=>{seen.mimes=m;return s;}; },
  PickerBuilder:function(){ const s=this, st={}; this.addView=()=>s; this.enableFeature=()=>s; this.setOAuthToken=(t)=>{seen.tokenArg=t;return s;}; this.setDeveloperKey=()=>s; this.setAppId=()=>s;
    this.setMaxItems=(n)=>{seen.max=n;return s;}; this.setCallback=(cb)=>{st.cb=cb;return s;};
    this.build=()=>({setVisible:()=>setImmediate(()=>st.cb(action==='cancel'?{action:'cancel'}:{action:'picked',docs}))}); }}};
ctx.gapi={load:(n,cb)=>cb()}; vm.createContext(ctx); vm.runInContext(code,ctx);
const cfg={client_id:'cid.apps.googleusercontent.com',api_key:'key-1',app_id:'12345',mode:mode}; if(hint!==undefined) cfg.login_hint=hint;
listener({origin:'https://alto.test',source:op,data:{alto:'drive-config',cfg:cfg}});
setTimeout(()=>{ console.log(JSON.stringify({posted,revoked,seen,closed})); process.exit(0); },200);
"""


def run(mode, action="picked", docs=None, hint=None):
    docs = [{"id": "1AbCdEfGhIjK", "name": "Syllabus.pdf", "mimeType": "application/pdf"}] if docs is None else docs
    args = [NODE, "-e", HARNESS, PK.picker_js(), mode, action, json.dumps(docs)] + ([hint] if hint is not None else [])
    env = {"TOK": TOKEN, "PATH": "/usr/bin:/bin"}                      # (no other variable reaches the harness: the token must not be readable from anywhere else)
    for k in ("SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"):      # Windows: node's CSPRNG (ncrypto) needs SYSTEMROOT to start
        if os.environ.get(k):
            env[k] = os.environ[k]
    out = subprocess.run(args, capture_output=True, text=True, timeout=60, env=env)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_ref_posts_only_names_and_ids_never_the_token():
    r = run("ref")
    sent = [m for m, o in r["posted"] if m.get("alto") == "drive-picked"]
    assert len(sent) == 1 and sorted(sent[0]) == ["alto", "result"]
    assert sorted(sent[0]["result"]) == ["files"]
    assert sent[0]["result"]["files"] == [{"id": "1AbCdEfGhIjK", "name": "Syllabus.pdf", "mimeType": "application/pdf"}]
    assert TOKEN not in json.dumps(r["posted"]) and "token" not in json.dumps(sent[0]).lower()
    assert all(o == "https://alto.test" for m, o in r["posted"])                           # same origin only, never "*"


def test_ref_revokes_on_pick_and_on_cancel():
    r = run("ref")
    assert r["revoked"] == [TOKEN]
    c = run("ref", action="cancel")
    assert c["revoked"] == [TOKEN]
    assert [m for m, o in c["posted"] if m.get("alto") == "drive-picked"] == [{"alto": "drive-picked", "result": None}]


def test_the_static_shape_of_the_ref_branch():
    js = PK.picker_js()
    assert "res({files:files})" in js and "refFiles(d)" in js
    ref = js[js.index("if(ref){ var files=refFiles(d);"):]
    ref = ref[:ref.index("else res({token")]
    assert "token" not in ref and "tok" not in ref.replace("rev(tok)", "").replace("tok=null", "")
    assert "google.accounts.oauth2.revoke" in js


def test_mime_list_and_pick_cap():
    r = run("ref")
    assert r["seen"]["mimes"] == ",".join(DC.REF_MIMES) and r["seen"]["max"] == DC.MAX_PICK == 5
    assert "application/vnd.google-apps.document" in DC.REF_MIMES and "application/pdf" in DC.REF_MIMES
    assert all(m.count("/") == 1 and " " not in m for m in DC.REF_MIMES)
    assert r["seen"]["scope"] == DC.SCOPE


def test_junk_in_a_pick_is_dropped_and_names_are_cleaned():
    many = [{"id": "1AbCdEfGhI%02d" % i, "name": "f%d" % i, "mimeType": "text/plain"} for i in range(8)]
    docs = [{"id": "bad id", "name": "x"}, {"id": "<script>alert(1)", "name": "y"}, {"id": "1AbCdEfGhIjK", "name": 'a<b>"c\u0001' + "n" * 300, "mimeType": "x y<z"}] + many
    files = [m for m, o in run("ref", docs=docs)["posted"] if m.get("alto") == "drive-picked"][0]["result"]["files"]
    assert len(files) <= 5
    assert all(DC._ID.match(f["id"]) for f in files)
    assert files[0]["name"] == "abc" + "n" * 197 and files[0]["mimeType"] == "xyz"


def test_login_hint_only_when_it_looks_like_an_address():
    assert run("ref", hint="lbm@example.com")["seen"]["hint"] == "lbm@example.com"
    assert run("ref", hint="x<script>")["seen"]["hint"] is None
    assert run("ref")["seen"]["hint"] is None


def test_bass_mode_is_unchanged():
    r = run("bass")
    sent = [m for m, o in r["posted"] if m.get("alto") == "drive-picked"][0]
    assert sent["result"] == {"token": TOKEN, "ids": ["1AbCdEfGhIjK"]} and r["revoked"] == []
    assert r["seen"]["mimes"] == "application/vnd.google-apps.document,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
    assert r["seen"]["max"] is None


def test_the_popup_still_refuses_a_foreign_opener_and_bad_config():
    js = PK.picker_js()
    assert "e.origin!==OWN||e.source!==op" in js and "if(c.login_hint!==undefined" in js


def test_the_csp_lets_the_revoke_through_and_nothing_wider():
    """Google's script sends google.accounts.oauth2.revoke as an XHR POST to https://oauth2.googleapis.com/revoke (read in accounts.google.com/gsi/client,
    14 Nov 2026); without that exact address in connect-src the page's own CSP would block the revoke at pick and at cancel. Browser pin: test_drive_edit_e2e."""
    d = dict(p.split(" ", 1) for p in PK.PICKER_CSP.split("; "))
    assert d["connect-src"].split() == ["https://accounts.google.com/gsi/", "https://oauth2.googleapis.com/revoke"]
    assert PK.PICKER_CSP.count("googleapis.com") == 1 and "*" not in PK.PICKER_CSP
    assert "google.accounts.oauth2.revoke(" in PK.picker_js() and "google.accounts.id.revoke" not in PK.picker_js()
