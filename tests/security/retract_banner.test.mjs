// A tester whose beta access is withdrawn: the rules refuse their writes (permission-denied). The real alto-cloud.js
// in Chromium, against the Auth and Firestore emulators, must say so once and stop pushing; and must say nothing
// for a lost network. Rules here are the allowlist gate only (the full rules live in firestore.rules).
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
const RULES = `rules_version = '2';
service cloud.firestore { match /databases/{database}/documents {
  function allowlisted() { return request.auth != null && request.auth.token.email.lower()
    in get(/databases/$(database)/documents/bass_beta/allowlist).data.emails; }
  match /users/{uid}/{document=**} {
    allow read: if request.auth != null && request.auth.uid == uid;
    allow write: if request.auth != null && request.auth.uid == uid && allowlisted();
  }
} }`;
const TEXT = 'Saving to the Alto cloud is off for this account (it is not on the beta list, or its beta access has ended). Your changes are not being saved there. Your work stays here to read, and Save on the Home page keeps a copy.';
const BANNER = '#alto-beta-ended';

let env, server, base, browser, cloudJs;

before(async () => {
  const out = join(mkdtempSync(join(tmpdir(), 'alto-cloud-')), 'alto-cloud.js');
  execFileSync(process.env.PYTHON || 'python3', [join(HERE, 'cloud_fixture.py'), out, SDK_V]);
  cloudJs = readFileSync(out, 'utf8');
  env = await initializeTestEnvironment({ projectId: PROJECT, firestore: { rules: RULES, host: '127.0.0.1', port: 8080 } });
  server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    if (url.pathname === '/alto-cloud.js') { res.writeHead(200, { 'Content-Type': 'text/javascript' }); return res.end(cloudJs); }
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<!DOCTYPE html><title>t</title><script type="module" src="/alto-cloud.js" data-tid="biology"></script>');
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch(process.env.ALTO_CHROMIUM ? { executablePath: process.env.ALTO_CHROMIUM } : {});
});

after(async () => { await browser?.close(); server?.close(); await env?.cleanup(); });

beforeEach(async () => {
  await env.clearFirestore();
  await fetch(`http://127.0.0.1:9099/emulator/v1/projects/${PROJECT}/accounts`, { method: 'DELETE' });
  await setAllowlist(['alice@example.com']);
});

const admin = async (fn) => { let out; await env.withSecurityRulesDisabled(async (ctx) => { out = await fn(ctx.firestore()); }); return out; };
const setAllowlist = (emails) => admin(db => db.doc('bass_beta/allowlist').set({ emails }));
const note = (text) => JSON.stringify([{ id: 'n1', quote: 'q', note: text, kind: 'highlight', ts: 1, mod: Date.now() }]);
const until = async (fn, ms = 8000) => { const t0 = Date.now(); for (;;) { const v = await fn(); if (v || Date.now() - t0 > ms) return v; await new Promise(r => setTimeout(r, 200)); } };
const stored = async (uid) => { const s = await admin(db => db.doc(`users/${uid}/tl/biology`).get()); return s.exists ? String(s.data().highlights || '') : ''; };

async function session() {
  const ctx = await browser.newContext();
  await ctx.route(/^https:\/\/www\.gstatic\.com\/firebasejs\/[^/]+\/([a-z-]+\.js)$/, (route) => {
    route.fulfill({ status: 200, contentType: 'text/javascript', body: readFileSync(join(SDK_DIR, route.request().url().split('/').pop()), 'utf8') });
  });
  const page = await ctx.newPage();
  await page.goto(base + '/');
  await page.waitForFunction(() => window.__test && window.AltoCloud && window.AltoCloud.known);
  await page.evaluate(() => window.__test.signIn('alice', 'alice@example.com')).catch(() => {});
  await page.waitForFunction(() => window.AltoCloud.user && window.AltoCloud.user.email === 'alice@example.com');
  const uid = await page.evaluate(() => window.AltoCloud.user.uid);
  return { ctx, page, uid };
}
const write = (page, text) => page.evaluate((v) => localStorage.setItem('alto-hl-biology', v), note(text));
const banners = (page) => page.locator(BANNER).count();

test('an allowlisted account saves; once removed, ONE banner appears and nothing more is pushed', async () => {
  const { ctx, page, uid } = await session();
  await write(page, 'before removal');
  assert.ok(await until(async () => (await stored(uid)).includes('before removal')), 'an allowlisted write never landed');
  assert.equal(await banners(page), 0, 'a banner showed while access was fine');
  await setAllowlist([]);                                   // the tester is removed
  await write(page, 'after removal one');
  assert.ok(await until(async () => (await banners(page)) === 1), 'no banner after a refused write');
  assert.equal((await page.locator(BANNER).textContent()), TEXT);
  await write(page, 'after removal two'); await page.evaluate(() => window.AltoCloud.sync());
  await new Promise(r => setTimeout(r, 1500));
  assert.equal(await banners(page), 1, 'the banner must show once');
  const s = await stored(uid);
  assert.ok(s.includes('before removal') && !s.includes('after removal'), 'a refused account must not keep pushing');
  await ctx.close();
});

test('losing the network never shows the banner, and the save lands when it returns', async () => {
  const { ctx, page, uid } = await session();
  await ctx.setOffline(true);
  await write(page, 'written offline');
  await new Promise(r => setTimeout(r, 2500));
  assert.equal(await banners(page), 0, 'offline must not look like a withdrawn beta');
  await ctx.setOffline(false);
  assert.ok(await until(async () => (await stored(uid)).includes('written offline'), 15000), 'the offline write never landed');
  assert.equal(await banners(page), 0);
  await ctx.close();
});
