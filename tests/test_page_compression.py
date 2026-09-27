"""Private pages and shares are stored gzipped (private_shell.MAX_PAGE_BYTES).

The cap is Firestore's 1 MiB document limit, and it applies to what is
stored: the `z` Bytes field, not the html. alto-cloud.js packs on upload and
unpacks on read, and the connector writes the same form itself (store/cloud.py)
— so the two must agree byte for byte on the format, and every reader must
still open a document written before compression (a plain `html` string).

The browser half is exercised for real: the functions are cut out of
alto-cloud.js and run under node, which has the same CompressionStream."""
from __future__ import annotations

import base64
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alto.build.private_shell import (MAX_PAGE_BYTES, PAGE_ENCODING, pack_page,
                                      shell, stored_bytes, unpack_page)

ROOT = Path(__file__).resolve().parent.parent
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
HAVE_NODE = Path(NODE).is_file()

# Repetitive like a real page (one engine, many similar nodes), and well over
# the cap as html.
BIG = ("<!DOCTYPE html><html><head><title>Big — Alto</title></head><body>"
       + "".join(f"<div class='node' id='n{i}'>Node {i}: the same engine markup "
                 f"again — ünïcödé ✓ {i % 97}</div>\n" for i in range(16000))
       + "</body></html>")


# ── the Python half ─────────────────────────────────────────────────────────

def test_a_page_round_trips_and_is_measured_compressed():
    assert unpack_page(pack_page(BIG)) == BIG
    assert len(BIG.encode()) > MAX_PAGE_BYTES > stored_bytes(BIG)
    assert stored_bytes(BIG) == len(pack_page(BIG))


def test_packing_is_deterministic():
    """mtime=0: the same page stores the same bytes, whenever it is built."""
    assert pack_page(BIG) == pack_page(BIG)
    assert PAGE_ENCODING == "gzip"
    assert gzip.decompress(pack_page("x")) == b"x"


def test_the_shell_no_longer_caps_the_raw_file():
    """A 1.2 MB private.html that stores at 300 KB must upload; the raw-size
    check the file picker used to make would refuse it."""
    s = shell()
    assert "file.size > MAX" not in s and "__MAX__" not in s


def test_publish_measures_the_stored_bytes():
    src = (ROOT / "alto" / "mcp_server.py").read_text(encoding="utf-8")
    fn = src[src.index('if visibility == "private-web" and store_mode() == "cloud":'):]
    fn = fn[:fn.index("st.put_page(")]
    assert "stored = stored_bytes(page)" in fn and "if stored > MAX_PAGE_BYTES:" in fn
    assert "len(page.encode(\"utf-8\")) > MAX_PAGE_BYTES" not in fn


# ── the browser half, run under node ────────────────────────────────────────

# Everything from the cap to the share writer: the pack/unpack helpers and
# every function that reads or writes a page or a share. Firestore is stubbed
# with a dict; Bytes with the smallest class that has the SDK's two methods.
_HARNESS = r"""
const fs = require('fs');
const store = {};
class Bytes {
  constructor(u8){ this.u8 = u8; }
  static fromUint8Array(u8){ return new Bytes(u8); }
  toUint8Array(){ return this.u8; }
}
const auth = { currentUser: { uid: 'U1' } }, db = {};
const doc = (_db, ...p) => p.join('/');
const collection = (_db, ...p) => p.join('/');
const serverTimestamp = () => ({ seconds: 1 });
async function setDoc(ref, v, opt){ store[ref] = (opt && opt.merge) ? Object.assign({}, store[ref], v) : v; }
async function getDoc(ref){ const v = store[ref]; return { exists: () => !!v, data: () => v }; }
async function getDocs(){ return { docs: [], forEach(){} }; }
const f = new Function('auth','db','doc','collection','serverTimestamp','setDoc','getDoc','getDocs','Bytes',
  SRC + '; return { _packPage, _unpackPage, _putPage, _getPage, _putShare, _getShare, _sharePush };');
const api = f(auth, db, doc, collection, serverTimestamp, setDoc, getDoc, getDocs, Bytes);
const b64 = u8 => Buffer.from(u8).toString('base64');
const fromB64 = s => new Uint8Array(Buffer.from(s, 'base64'));

(async () => {
  const cmd = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const out = {};
  try {
    if (cmd.op === 'pack') {
      const p = await api._packPage(cmd.html);
      out.z = b64(p.fields.z.toUint8Array()); out.enc = p.fields.enc; out.bytes = p.bytes;
      out.hasHtml = 'html' in p.fields;
    } else if (cmd.op === 'unpack') {
      out.html = await api._unpackPage(cmd.z ? { z: Bytes.fromUint8Array(fromB64(cmd.z)), enc: cmd.enc }
                                             : { html: cmd.html });
    } else if (cmd.op === 'put-get') {
      await api._putPage('k1', cmd.html, 'T');
      const d = store['users/U1/pages/k1'];
      out.stored = Object.keys(d).sort();
      out.zBytes = d.z ? d.z.toUint8Array().length : 0;
      out.back = (await api._getPage('k1')) === cmd.html;
    } else if (cmd.op === 'share') {
      store['users/U1/pages/k1'] = { html: cmd.html, title: 'T' };   // written before compression
      const r = await api._sharePush('k1', 'T', false);
      const d = store['shares/' + r.shareKey];
      out.stored = Object.keys(d).sort();
      const got = await api._getShare(r.shareKey);
      out.reidentified = got.html.includes("var COURSE_ID = 's-" + r.shareKey + "';");
      out.gotKeys = Object.keys(got).sort();
      await api._putShare('P', { items: [{ key: 'a' }], title: 'Proj' });
      out.projectShare = Object.keys(store['shares/P']).sort();
    }
  } catch (e) { out.error = String(e && e.message || e); }
  process.stdout.write(JSON.stringify(out));
})();
"""


def _js(tmp_path, cmd: dict) -> dict:
    a = CLOUD_JS.index("  const MAX_PAGE_BYTES")
    b = CLOUD_JS.index("  async function _revokeShare")
    src = CLOUD_JS[a:b] + CLOUD_JS[CLOUD_JS.index("  const KEY_ALPHABET"):
                                   CLOUD_JS.index("  async function _shareRevoke")]
    runner = tmp_path / "h.js"
    runner.write_text("const SRC = " + json.dumps(src) + ";\n" + _HARNESS, encoding="utf-8")
    arg = tmp_path / "cmd.json"
    arg.write_text(json.dumps(cmd), encoding="utf-8")
    return json.loads(subprocess.check_output([NODE, str(runner), str(arg)], timeout=60))


needs_node = pytest.mark.skipif(not HAVE_NODE, reason="needs node")


@needs_node
def test_what_the_browser_stores_the_connector_can_read(tmp_path):
    r = _js(tmp_path, {"op": "pack", "html": BIG})
    assert r["enc"] == PAGE_ENCODING and not r["hasHtml"]
    z = base64.b64decode(r["z"])
    assert unpack_page(z) == BIG
    assert r["bytes"] == len(z) < MAX_PAGE_BYTES
    # Same zlib level as the connector's measure, so the two agree closely.
    assert abs(len(z) - stored_bytes(BIG)) < 0.02 * len(z)


@needs_node
def test_what_the_connector_stores_the_browser_can_read(tmp_path):
    z = base64.b64encode(pack_page(BIG)).decode()
    assert _js(tmp_path, {"op": "unpack", "z": z, "enc": "gzip"})["html"] == BIG


@needs_node
def test_a_page_stored_before_compression_still_opens(tmp_path):
    assert _js(tmp_path, {"op": "unpack", "html": "<html>old</html>"})["html"] == "<html>old</html>"


@needs_node
def test_an_unknown_encoding_is_refused_not_misread(tmp_path):
    z = base64.b64encode(pack_page("x")).decode()
    assert "unknown encoding" in _js(tmp_path, {"op": "unpack", "z": z, "enc": "br"})["error"]


@needs_node
def test_upload_stores_compressed_and_reads_back(tmp_path):
    r = _js(tmp_path, {"op": "put-get", "html": BIG})
    assert r.get("error") is None
    assert r["stored"] == ["enc", "tid", "title", "updatedAt", "z"], "no html copy"
    assert r["zBytes"] < MAX_PAGE_BYTES < len(BIG.encode())
    assert r["back"] is True


@needs_node
def test_the_cap_applies_to_the_stored_bytes(tmp_path):
    import os
    noise = base64.b64encode(os.urandom(1_100_000)).decode()   # does not compress
    r = _js(tmp_path, {"op": "put-get", "html": noise})
    assert "compressed" in r["error"] and "exceeds the 977 KB limit" in r["error"]


@needs_node
def test_a_share_is_packed_and_the_shell_still_gets_html(tmp_path):
    page = "<html><script>var COURSE_ID = 'terr';</script>" + BIG[:200000] + "</html>"
    r = _js(tmp_path, {"op": "share", "html": page})
    assert r.get("error") is None, r
    assert "z" in r["stored"] and "html" not in r["stored"]
    assert r["reidentified"] is True
    assert "html" in r["gotKeys"] and "z" not in r["gotKeys"]
    # A project share has no page to pack.
    assert r["projectShare"] == ["items", "owner", "title", "updatedAt"]
