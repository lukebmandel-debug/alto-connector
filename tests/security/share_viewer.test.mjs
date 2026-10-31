// The share viewer (/s/{key}/) renders HTML its owner wrote, on the same site
// a reader may be signed in to. These tests serve the real shell under the
// real CSP and check that a shared page's script reaches none of that site's
// state, while a real shared timeline still works.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const HERE = dirname(fileURLToPath(import.meta.url));
const KEY = 'czckq4utebcx5rvgdptrgt';
const SECRET = 'app-origin-secret-7f3a';

let server, base, browser, fx, shareHtml;

// What a hostile share runs: it tries every route to the app origin's state
// and writes what it got into its own title for the test to read.
const HOSTILE = `<!DOCTYPE html><html><head><script>
(async function(){
  var got = {};
  function tryIt(name, fn){ try{ var v = fn(); got[name] = (v === undefined || v === null) ? null : String(v); }catch(e){ got[name] = 'ERR'; } }
  tryIt('origin', function(){ return location.origin; });
  tryIt('ls', function(){ return localStorage.getItem('firebase:authUser:demo:[DEFAULT]'); });
  tryIt('cookie', function(){ return document.cookie; });
  tryIt('parentDoc', function(){ return parent.document.cookie; });
  tryIt('parentLs', function(){ return parent.localStorage.getItem('firebase:authUser:demo:[DEFAULT]'); });
  tryIt('parentCloud', function(){ return parent.AltoCloud && parent.AltoCloud.user && parent.AltoCloud.user.uid; });
  tryIt('topLoc', function(){ return top.location.href; });
  got.idb = await new Promise(function(res){
    try{
      var r = indexedDB.open('firebaseLocalStorageDb');
      r.onsuccess = function(){
        try{
          var tx = r.result.transaction('firebaseLocalStorage', 'readonly');
          var q = tx.objectStore('firebaseLocalStorage').getAll();
          q.onsuccess = function(){ res(JSON.stringify(q.result)); };
          q.onerror = function(){ res('ERR'); };
        }catch(e){ res('ERR'); }
      };
      r.onerror = function(){ res('ERR'); };
    }catch(e){ res('ERR'); }
  });
  document.title = 'DONE:' + JSON.stringify(got);
})();
</script></head><body>hostile</body></html>`;

// Stands in for alto-cloud.js: hands the shell a share, signed in as "victim".
const CLOUD_STUB = `window.AltoCloud = { enabled: true, known: true, user: { uid: 'victim-uid' },
  getShare: async function(){ return window.__share; }, refreshShared: async function(){ return false; } };`;

before(async () => {
  const out = mkdtempSync(join(tmpdir(), 'alto-share-'));
  execFileSync(process.env.PYTHON || 'python3', [join(HERE, 'fixtures.py'), out, KEY]);
  fx = {
    shell: readFileSync(join(out, 'shell.html'), 'utf8'),
    csp: readFileSync(join(out, 'csp.txt'), 'utf8'),
    page: readFileSync(join(out, 'page.html'), 'utf8'),
  };
  server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    const send = (type, body) => {
      res.writeHead(200, { 'Content-Type': type, 'Content-Security-Policy': fx.csp });
      res.end(body);
    };
    if (url.pathname === '/alto-cloud.js')
      return send('text/javascript', CLOUD_STUB + 'window.__share = ' +
                  JSON.stringify({ html: shareHtml, title: 'T' }).replace(/</g, '\\u003c') + ';');
    if (url.pathname.startsWith('/s/')) return send('text/html', fx.shell);
    if (url.pathname === '/seed') return send('text/html', '<!DOCTYPE html><title>seed</title>');
    res.writeHead(404); res.end();
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch(process.env.ALTO_CHROMIUM ? { executablePath: process.env.ALTO_CHROMIUM } : {});
});

after(async () => {
  await browser?.close();
  server?.close();
});

async function seededPage() {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(base + '/seed');
  // The app origin's sign-in state, in each place Firebase Auth may keep it.
  await page.evaluate(async (secret) => {
    localStorage.setItem('firebase:authUser:demo:[DEFAULT]', secret);
    document.cookie = 'session=' + secret + '; path=/';
    await new Promise((res, rej) => {
      const r = indexedDB.open('firebaseLocalStorageDb', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('firebaseLocalStorage', { keyPath: 'fbase_key' });
      r.onsuccess = () => {
        const tx = r.result.transaction('firebaseLocalStorage', 'readwrite');
        tx.objectStore('firebaseLocalStorage').put({ fbase_key: 'firebase:authUser', value: secret });
        tx.oncomplete = () => res();
        tx.onerror = () => rej(tx.error);
      };
      r.onerror = () => rej(r.error);
    });
  }, SECRET);
  return { ctx, page };
}

function stageFrame(page) {
  return page.frames().find(f => f !== page.mainFrame());
}

test('a shared page is framed in an opaque-origin sandbox', async () => {
  shareHtml = HOSTILE;
  const { ctx, page } = await seededPage();
  await page.goto(`${base}/s/${KEY}/`);
  const sandbox = await page.getAttribute('#stage', 'sandbox');
  assert.equal(sandbox, 'allow-scripts');
  await ctx.close();
});

test("a shared page's script cannot reach the app origin's sign-in state", async () => {
  shareHtml = HOSTILE;
  const { ctx, page } = await seededPage();
  await page.goto(`${base}/s/${KEY}/`);
  await page.waitForFunction(() => {
    const f = document.getElementById('stage');
    try { return f.contentDocument === null; } catch (e) { return true; }
  });
  let title = '';
  for (let i = 0; i < 100 && !title.startsWith('DONE:'); i++) {
    const f = stageFrame(page);
    title = f ? await f.title().catch(() => '') : '';
    if (!title.startsWith('DONE:')) await page.waitForTimeout(100);
  }
  assert.ok(title.startsWith('DONE:'), 'hostile page never ran: ' + title);
  const got = JSON.parse(title.slice(5));
  assert.equal(got.origin, 'null', 'framed page must have an opaque origin');
  for (const [k, v] of Object.entries(got))
    assert.ok(!String(v).includes(SECRET), `${k} leaked the app origin's state: ${v}`);
  for (const k of ['parentDoc', 'parentLs', 'parentCloud', 'topLoc', 'cookie', 'idb'])
    assert.equal(got[k], 'ERR', `${k} should be refused, got ${got[k]}`);
  // The parent itself never handed its document over either.
  assert.equal(await page.evaluate(() => document.getElementById('stage').contentDocument), null);
  await ctx.close();
});

test('the frame cannot write any key of the app origin but its own share entry', async () => {
  shareHtml = `<!DOCTYPE html><html><head><script>
    localStorage.setItem('alto-theme-v1', 'pwned');
    localStorage.setItem('alto-hl-victim', '[{"id":"x"}]');
    parent.postMessage({ t: 'store', v: '{"alto-hl-victim":"x"}' }, '*');
    parent.postMessage({ t: 'store', v: 'x'.repeat(500000) }, '*');
    parent.postMessage({ t: 'set', k: 'alto-theme-v1', v: 'pwned' }, '*');
    document.title = 'DONE';
  </script></head><body></body></html>`;
  const { ctx, page } = await seededPage();
  await page.goto(`${base}/s/${KEY}/`);
  await page.waitForTimeout(1500);
  const ls = await page.evaluate(() => Object.assign({}, localStorage));
  assert.equal(ls['alto-theme-v1'], undefined);
  assert.equal(ls['alto-hl-victim'], undefined);
  assert.equal(ls['firebase:authUser:demo:[DEFAULT]'], SECRET);
  const own = Object.keys(ls).filter(k => k.startsWith('alto-share-v1:'));
  assert.deepEqual(own, ['alto-share-v1:' + KEY]);
  assert.ok(ls['alto-share-v1:' + KEY].length < 400000);
  await ctx.close();
});

test('a real shared timeline renders in the sandbox and keeps its highlights', async () => {
  shareHtml = fx.page;
  const { ctx, page } = await seededPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(`${base}/s/${KEY}/`);
  let f = null;
  for (let i = 0; i < 100; i++) {
    f = stageFrame(page);
    if (f && await f.evaluate(() => typeof window.COURSE_ID !== 'undefined' || !!document.querySelector('.node, [data-id]')).catch(() => false)) break;
    await page.waitForTimeout(100);
  }
  assert.ok(f, 'no frame');
  assert.equal(await f.evaluate(() => location.origin), 'null');
  // The page writes its highlights through the stand-in storage; the shell keeps them.
  await f.evaluate((k) => localStorage.setItem('alto-hl-s-' + k, '[{"id":"n1","quote":"q"}]'), KEY);
  await page.waitForTimeout(800);
  const kept = await page.evaluate((k) => localStorage.getItem('alto-share-v1:' + k), KEY);
  assert.ok(kept && JSON.parse(kept)['alto-hl-s-' + KEY], 'highlights were not kept: ' + kept);
  // ...and hands them back on the next visit.
  await page.reload();
  let back = null;
  for (let i = 0; i < 100 && !back; i++) {
    const g = stageFrame(page);
    back = g ? await g.evaluate((k) => localStorage.getItem('alto-hl-s-' + k), KEY).catch(() => null) : null;
    if (!back) await page.waitForTimeout(100);
  }
  assert.ok(back && JSON.parse(back).some(h => h.id === 'n1' && h.quote === 'q'), 'not handed back: ' + back);
  assert.deepEqual(errors, []);
  await ctx.close();
});
