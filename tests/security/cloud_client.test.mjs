// The real alto-cloud.js in Chromium, against the Auth and Firestore
// emulators: what one account leaves in a browser never reaches the next,
// and the share flows write what the rules expect.
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { initializeTestEnvironment } from '@firebase/rules-unit-testing';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const SDK_DIR = dirname(require.resolve('firebase/package.json'));
const SDK_V = require('firebase/package.json').version;
const PROJECT = 'demo-alto-security';
const NOTE = "ALICE'S PRIVATE NOTE";

let env, server, base, browser, cloudJs;

before(async () => {
  const out = join(mkdtempSync(join(tmpdir(), 'alto-cloud-')), 'alto-cloud.js');
  execFileSync(process.env.PYTHON || 'python3', [join(HERE, 'cloud_fixture.py'), out, SDK_V]);
  cloudJs = readFileSync(out, 'utf8');
  env = await initializeTestEnvironment({
    projectId: PROJECT,
    firestore: { rules: readFileSync(join(HERE, '../../firestore.rules'), 'utf8'), host: '127.0.0.1', port: 8080 },
  });
  server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    if (url.pathname === '/alto-cloud.js') {
      res.writeHead(200, { 'Content-Type': 'text/javascript' }); return res.end(cloudJs);
    }
    const tid = url.searchParams.get('tid') || 'biology';
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`<!DOCTYPE html><title>t</title><script type="module" src="/alto-cloud.js" data-tid="${tid}"></script>`);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch(process.env.ALTO_CHROMIUM ? { executablePath: process.env.ALTO_CHROMIUM } : {});
});

after(async () => { await browser?.close(); server?.close(); await env?.cleanup(); });

beforeEach(async () => {
  await env.clearFirestore();
  await fetch(`http://127.0.0.1:9099/emulator/v1/projects/${PROJECT}/accounts`, { method: 'DELETE' });
  await env.withSecurityRulesDisabled(async (ctx) => {
    await ctx.firestore().doc('bass_beta/allowlist').set({ emails: ['alice@example.com', 'bob@example.com'] });
  });
});

async function profile() {
  const ctx = await browser.newContext();
  await ctx.route(/^https:\/\/www\.gstatic\.com\/firebasejs\/[^/]+\/([a-z-]+\.js)$/, (route) => {
    const f = route.request().url().split('/').pop();
    route.fulfill({ status: 200, contentType: 'text/javascript', body: readFileSync(join(SDK_DIR, f), 'utf8') });
  });
  return ctx;
}

async function open(ctx, tid = 'biology') {
  const page = await ctx.newPage();
  if (process.env.ALTO_DEBUG) page.on('console', m => console.log('[page]', m.type(), m.text().slice(0, 300)));
  await page.goto(`${base}/?tid=${tid}`);
  await page.waitForFunction(() => window.__test && window.AltoCloud && window.AltoCloud.known);
  return page;
}

async function signIn(page, who) {
  // Signing in may reload the page (when it held data that is not this account's).
  await page.evaluate((w) => window.__test.signIn(w, w + '@example.com'), who).catch(() => {});
  await page.waitForFunction((w) => window.AltoCloud && window.AltoCloud.user && window.AltoCloud.user.email === w + '@example.com', who);
  return page.evaluate(() => window.AltoCloud.user.uid);
}

async function signOut(page) {
  await Promise.all([page.waitForEvent('load'), page.evaluate(() => window.AltoCloud.signOut())]);
  await page.waitForFunction(() => window.AltoCloud && window.AltoCloud.known && !window.AltoCloud.user);
}

async function admin(fn) {
  let out;
  await env.withSecurityRulesDisabled(async (ctx) => { out = await fn(ctx.firestore()); });
  return out;
}

async function tlNotes(uid, tid = 'biology') {
  const snap = await admin(db => db.doc(`users/${uid}/tl/${tid}`).get());
  return snap.exists ? String(snap.data().highlights || '') : '';
}

async function until(fn, ms = 8000) {
  const t0 = Date.now();
  for (;;) { const v = await fn(); if (v || Date.now() - t0 > ms) return v; await new Promise(r => setTimeout(r, 200)); }
}

const note = (text) => JSON.stringify([{ id: 'n1', quote: 'q', note: text, kind: 'highlight', ts: 1, mod: 1 }]);

test("on a shared browser, one account's notes never reach the next account", async () => {
  const ctx = await profile();
  const page = await open(ctx);
  const alice = await signIn(page, 'alice');
  await page.evaluate((v) => localStorage.setItem('alto-hl-biology', v), note(NOTE));
  assert.ok(await until(async () => (await tlNotes(alice)).includes(NOTE)), "Alice's note never synced");
  await signOut(page);
  const left = await page.evaluate(() => Object.keys(localStorage).filter(k => /^alto-(hl|rp|doc)-/.test(k)));
  assert.deepEqual(left, [], 'sign-out left account data behind');
  const bob = await signIn(page, 'bob');
  await page.evaluate(() => window.AltoCloud.sync());
  await new Promise(r => setTimeout(r, 2500));
  assert.ok(!(await tlNotes(bob)).includes(NOTE), "Alice's note reached Bob's account");
  assert.ok(!(await page.evaluate(() => localStorage.getItem('alto-hl-biology') || '')).includes(NOTE));
  await ctx.close();
});

test("another account's data is never merged, even without a sign-out", async () => {
  const ctx = await profile();
  const page = await open(ctx);
  await page.evaluate((v) => { localStorage.setItem('alto-local-owner-v1', 'alice');
                               localStorage.setItem('alto-hl-biology', v); }, note(NOTE));
  let asked = false;
  page.on('dialog', d => { asked = true; d.accept(); });
  const bob = await signIn(page, 'bob');
  await page.evaluate(() => window.AltoCloud.sync());
  await new Promise(r => setTimeout(r, 2500));
  assert.equal(asked, false, 'should not ask about data that is known to be someone else\'s');
  assert.ok(!(await tlNotes(bob)).includes(NOTE));
  await ctx.close();
});

test('notes made signed out are never added to any account, whatever is clicked', async () => {
  for (const answer of ['accept', 'dismiss']) {
    await env.clearFirestore();
    await admin(db => db.doc('bass_beta/allowlist').set({ emails: ['alice@example.com', 'bob@example.com'] }));
    const ctx = await profile();
    const page = await open(ctx);
    await page.evaluate((v) => localStorage.setItem('alto-hl-biology', v), note(NOTE));
    let asked = 0;
    page.on('dialog', d => { asked++; d[answer](); });
    await page.evaluate(() => { window.__heldInMemory = true; });
    const bob = await signIn(page, 'bob');
    // The page started again, so nothing it held in memory can be re-saved.
    assert.equal(await page.evaluate(() => window.__heldInMemory), undefined, 'page kept its memory');
    await page.evaluate(() => window.AltoCloud.sync());
    await new Promise(r => setTimeout(r, 3000));
    assert.equal(asked, 0, 'nothing should be asked');
    assert.ok(!(await tlNotes(bob)).includes(NOTE), 'a signed-out note reached ' + answer);
    await ctx.close();
  }
});

test('notes made signed out stay on the device and are readable signed out again', async () => {
  const ctx = await profile();
  const page = await open(ctx);
  await page.evaluate((v) => localStorage.setItem('alto-hl-biology', v), note(NOTE));
  await signIn(page, 'bob');
  await page.waitForFunction(() => window.AltoCloud && window.AltoCloud.user);
  assert.ok(!(await page.evaluate(() => localStorage.getItem('alto-hl-biology') || '')).includes(NOTE),
            'a signed-out note is visible to the signed-in account');
  await signOut(page);
  assert.ok((await page.evaluate(() => localStorage.getItem('alto-hl-biology') || '')).includes(NOTE),
            'the signed-out note was lost');
  assert.equal(await page.evaluate(() => localStorage.getItem('alto-local-owner-v1')), null);
  await ctx.close();
});

test('another tab open signed out starts again when someone signs in', async () => {
  const ctx = await profile();
  const other = await open(ctx);
  await other.evaluate((v) => { localStorage.setItem('alto-hl-biology', v); window.__heldInMemory = true; }, note(NOTE));
  const page = await open(ctx);
  const bob = await signIn(page, 'bob');
  await other.waitForFunction(() => window.__heldInMemory === undefined && window.AltoCloud && window.AltoCloud.user, null, { timeout: 15000 });
  await other.evaluate(() => window.AltoCloud.sync());
  // Until it has started again, a signed-out tab cannot write account data.
  const third = await open(ctx);
  await third.evaluate(() => { window.AltoCloud.user = null; localStorage.setItem('alto-hl-biology', 'x'); });
  assert.notEqual(await third.evaluate(() => localStorage.getItem('alto-hl-biology')), 'x');
  await new Promise(r => setTimeout(r, 2500));
  assert.ok(!(await tlNotes(bob)).includes(NOTE));
  await ctx.close();
});

test('notes some account already synced, with no owner recorded, are never offered', async () => {
  const ctx = await profile();
  const page = await open(ctx);
  await page.evaluate((v) => { localStorage.setItem('alto-hl-biology', v);
                               localStorage.setItem('alto-cloud-meta-v3-biology', '{"hlSig":"x"}'); }, note(NOTE));
  let asked = 0;
  page.on('dialog', d => { asked++; d.accept(); });
  const bob = await signIn(page, 'bob');
  await page.waitForFunction(() => window.AltoCloud && window.AltoCloud.user);
  await page.evaluate(() => window.AltoCloud.sync());
  await new Promise(r => setTimeout(r, 2500));
  assert.equal(asked, 0, 'should not offer notes another account synced');
  assert.ok(!(await tlNotes(bob)).includes(NOTE), 'synced notes reached another account');
  await ctx.close();
});

test('the browser writes shares as content plus an owner record, and revokes them', async () => {
  const ctx = await profile();
  const page = await open(ctx);
  await page.on('dialog', d => d.accept());
  const alice = await signIn(page, 'alice');
  const html = "<!DOCTYPE html><html><head><title>Bio</title></head><body><script>var COURSE_ID = 'biology';</script></body></html>";
  await page.evaluate((h) => window.AltoCloud.putPage('pagekeyalice0000000001', h, 'Bio'), html);
  const r = await page.evaluate(() => window.AltoCloud.shareCreate('pagekeyalice0000000001', 'Bio'));
  assert.match(r.shareKey, /^[a-km-np-z2-9]{22}$/);
  const pub = await admin(db => db.doc(`shares/${r.shareKey}`).get());
  assert.ok(pub.exists);
  assert.ok(!('owner' in pub.data()), 'public share names its owner');
  assert.equal((await admin(db => db.doc(`shares/${r.shareKey}/private/owner`).get())).data().owner, alice);
  await page.evaluate(() => window.AltoCloud.sharePush('pagekeyalice0000000001', 'Bio 2'));
  assert.equal((await admin(db => db.doc(`shares/${r.shareKey}`).get())).data().title, 'Bio 2');
  assert.equal(await page.evaluate(() => window.AltoCloud.shareRevoke('pagekeyalice0000000001')), true);
  assert.equal((await admin(db => db.doc(`shares/${r.shareKey}`).get())).exists, false);
  assert.ok((await admin(db => db.doc(`shares/${r.shareKey}/private/owner`).get())).exists, 'owner record kept');
  await ctx.close();
});

test("an owner's older shares are migrated in place when they sign in", async () => {
  const K = 'pastkeyabcdefghijk2345';
  const ctx = await profile();
  const page = await open(ctx);
  page.on('dialog', d => d.accept());
  const alice = await signIn(page, 'alice');
  // The first sign-in's pass (nothing to move yet) has finished.
  await page.waitForFunction(() => Object.keys(localStorage).some(k => k.startsWith('alto-shares-owner-v1-')));
  await admin(async db => {
    await db.doc(`shares/${K}`).set({ html: '<p>old</p>', title: 'Old', owner: alice, updatedAt: new Date() });
    await db.doc(`users/${alice}/pagemeta/pk`).set({ shareKey: K });
  });
  await page.evaluate(() => localStorage.removeItem(Object.keys(localStorage).find(k => k.startsWith('alto-shares-owner-v1-')) || 'x'));
  await page.reload();
  await page.waitForFunction(() => window.AltoCloud && window.AltoCloud.user);
  const migrated = await until(async () => !('owner' in ((await admin(db => db.doc(`shares/${K}`).get())).data() || { owner: 1 })));
  assert.ok(migrated, 'owner still in the public share');
  const d = (await admin(db => db.doc(`shares/${K}`).get())).data();
  assert.equal(d.html, '<p>old</p>');
  assert.equal((await admin(db => db.doc(`shares/${K}/private/owner`).get())).data().owner, alice);
  await ctx.close();
});
