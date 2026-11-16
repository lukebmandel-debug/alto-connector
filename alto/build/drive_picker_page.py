"""/drive-picker/ — the one page that loads Google's Picker (Bass "Add from Drive", alto/bass/drive.py).

Why a page of its own: Google's Picker needs script, frame and connect origins that no other page of the site may have. Instead of widening the
site-wide CSP (or the timeline's), the Documents sheet opens THIS page in a popup, and only this path carries the wider policy
(publish_static._headers). It is the same idea as /connect/, the one page whose CSP lets a form go to the user's own computer.

What the page does: it asks its opener (same origin only) for the three public Picker identifiers, signs the student in to Google for the scope
drive.file ONLY (hard-coded here: a message cannot widen it), shows the Picker, and posts {token, ids} back to the opener (same origin only), then
closes. The token lives in a JS variable of this page only: never stored, never in an address or the DOM. The Alto pages never load a Google script.

Two modes, chosen by the opener's config message. "docs" (the default): posts {token, ids} for the Documents sheet. "ref" (manual edit, "Edit
this page"): posts ONLY {files:[{id,name,mimeType}]} and never the token; it revokes the token at Google (google.accounts.oauth2.revoke) the moment
a file is picked or the Picker is cancelled, so the token lives and dies inside this window. A chip made from it is a reference; Alto never reads the file.

CSP of this path (PICKER_CSP): no 'unsafe-inline', no 'unsafe-eval', no wildcard. The page's own script is a file (picker.js, 'self'), so it needs
no inline script; the origins are the ones Google documents for GIS (accounts.google.com/gsi/*) and the Picker (apis.google.com for gapi,
docs.google.com for the Picker frame). If a real run shows another origin is needed it is added here after a review, never as a wildcard.
"""
from __future__ import annotations

from ..drive_common import SCOPE, REF_MIMES, MAX_PICK, _ID as _ID_RE

FOLDER = "drive-picker"
ORIGINS = {
    "script-src": ("https://apis.google.com", "https://accounts.google.com/gsi/client"),
    "frame-src": ("https://docs.google.com", "https://accounts.google.com/gsi/"),
    # the revoke: Google's own script (accounts.google.com/gsi/client, read 14 Nov 2026) sends google.accounts.oauth2.revoke as an XHR POST to
    # https://oauth2.googleapis.com/revoke ("Making revoke request without credentials"); /gsi/revoke is google.accounts.id.revoke, which this page never calls.
    # The exact path, nothing wider. tests/test_drive_picker_ref.py and test_drive_edit_e2e.py pin it.
    "connect-src": ("https://accounts.google.com/gsi/", "https://oauth2.googleapis.com/revoke"),
    "style-src": ("https://accounts.google.com/gsi/style",),
}
PICKER_CSP = "; ".join([
    "default-src 'none'",
    "script-src 'self' " + " ".join(ORIGINS["script-src"]),
    "style-src 'self' " + " ".join(ORIGINS["style-src"]),
    "frame-src " + " ".join(ORIGINS["frame-src"]),
    "connect-src " + " ".join(ORIGINS["connect-src"]),
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
])

_JS = r"""(function(){
'use strict';
var OWN=location.origin, op=window.opener, SCOPE='%(scope)s', done=false, started=false, m=document.getElementById('m');
function say(t){ if(m) m.textContent=t; }
function send(r){ if(done) return; done=true; try{ if(op) op.postMessage({alto:'drive-picked',result:r},OWN); }catch(e){} r=null; setTimeout(function(){ window.close(); },60); }
function load(src,ready){ return new Promise(function(res,rej){ if(ready()) return res(); var x=document.createElement('script'); x.src=src; x.async=true;
  x.onload=function(){ res(); }; x.onerror=function(){ rej(new Error('load')); }; document.head.appendChild(x); }); }
var REF_MIMES='%(mimes)s', MAXN=%(maxn)d, ID=/^[A-Za-z0-9_-]{10,100}$/, MAIL=/^[^\s@<>"']{1,64}@[^\s@<>"']{1,200}$/;
function rev(t){ try{ google.accounts.oauth2.revoke(t,function(){}); }catch(e){} }
function refFiles(d){ return (d.docs||[]).slice(0,MAXN).map(function(x){ var id=x&&x.id; if(typeof id!=='string'||!ID.test(id)) return null;
  var nm=String((x&&x.name)||'').replace(/[\u0000-\u001f\u007f<>"]/g,'').slice(0,200); var mt=String((x&&x.mimeType)||'').replace(/[^A-Za-z0-9.+\/-]/g,'').slice(0,100);
  return {id:id,name:nm,mimeType:mt}; }).filter(function(x){ return x; }); }
function ok(s,n){ return typeof s==='string'&&s.length>0&&s.length<=n&&/^[A-Za-z0-9._-]+$/.test(s); }
function run(c){
  var ref=c.mode==='ref';
  return load('https://accounts.google.com/gsi/client',function(){ return window.google&&google.accounts&&google.accounts.oauth2; })
   .then(function(){ return load('https://apis.google.com/js/api.js',function(){ return window.gapi; }); })
   .then(function(){ return new Promise(function(res){ gapi.load('picker',res); }); })
   .then(function(){ return new Promise(function(res,rej){
     var tc={client_id:c.client_id,scope:SCOPE,callback:function(t){ if(!t||!t.access_token) return rej(new Error('token')); res(t.access_token); },error_callback:function(){ res(null); }};
     if(c.login_hint) tc.login_hint=c.login_hint;
     google.accounts.oauth2.initTokenClient(tc).requestAccessToken({prompt:''}); }); })
   .then(function(tok){ if(!tok) return null; return new Promise(function(res){
     var v=new google.picker.DocsView(google.picker.ViewId.DOCS).setIncludeFolders(false).setSelectFolderEnabled(false)
       .setMimeTypes(ref?REF_MIMES:'application/vnd.google-apps.document,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain');
     var pb=new google.picker.PickerBuilder().addView(v).enableFeature(google.picker.Feature.MULTISELECT_ENABLED).setOAuthToken(tok).setDeveloperKey(c.api_key).setAppId(c.app_id);
     if(ref) pb.setMaxItems(MAXN);
     pb.setCallback(function(d){ var A=google.picker.Action;
       if(d.action===A.PICKED){ if(ref){ var files=refFiles(d); rev(tok); tok=null; res({files:files}); } else res({token:tok,ids:(d.docs||[]).map(function(x){ return x.id; })}); }
       else if(d.action===A.CANCEL){ if(ref){ rev(tok); tok=null; } res(null); } }).build().setVisible(true); }); });
}
window.addEventListener('message',function(e){
  if(started||!op||e.origin!==OWN||e.source!==op||!e.data||e.data.alto!=='drive-config'||!e.data.cfg) return;
  var c=e.data.cfg;
  if(c.login_hint!==undefined&&!(typeof c.login_hint==='string'&&MAIL.test(c.login_hint))) delete c.login_hint;
  if(!ok(c.client_id,200)||!ok(c.api_key,200)||!ok(c.app_id,100)){ say('Google Drive could not be opened.'); return send(null); }
  started=true; say('Opening Google Drive…');
  run({client_id:c.client_id,api_key:c.api_key,app_id:c.app_id,mode:c.mode==='ref'?'ref':'docs',login_hint:c.login_hint||''}).then(send,function(){ send(null); });
});
if(!op||OWN==='null'){ say('Close this window and choose "Add from Drive" again.'); }
else { try{ op.postMessage({alto:'drive-ready'},OWN); }catch(e){ say('Close this window and try again.'); } }
})();
"""


def picker_js() -> str:
    return _JS % {"scope": SCOPE, "mimes": ",".join(REF_MIMES), "maxn": MAX_PICK}


def picker_page() -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Google Drive</title></head>'
            '<body><p id="m">Opening Google Drive…</p>'
            '<script src="picker.js"></script></body></html>')
