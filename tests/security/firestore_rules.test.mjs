// Firestore rules, against the emulator. Alice (A) owns data; everyone else
// tries to reach it. Expected: DENY everywhere except `get` on a share key.
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  initializeTestEnvironment, assertFails, assertSucceeds,
} from '@firebase/rules-unit-testing';
import firebase from 'firebase/compat/app';
import 'firebase/compat/firestore';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = 'demo-alto-security';
const FS = process.env.FIRESTORE_EMULATOR_HOST || '127.0.0.1:8080';
const AUTH = process.env.FIREBASE_AUTH_EMULATOR_HOST || '127.0.0.1:9099';
const KEY_A = 'czckq4utebcx5rvgdptrgt';     // Alice's share
const KEY_LEGACY = 'pastkeyabcdefghijk2345';  // made before owner records
const KEY_NEW = 'newkeyabcdefghijk23456';
const KEY_LEGACY_C = 'pastkeycarabcdefghij23';  // Carol's, from before owner records
const ts = () => firebase.firestore.FieldValue.serverTimestamp();
const bytes = (n) => firebase.firestore.Blob.fromUint8Array(new Uint8Array(n));

let env;
const who = {};

before(async () => {
  env = await initializeTestEnvironment({
    projectId: PROJECT,
    firestore: { rules: readFileSync(join(HERE, '../../firestore.rules'), 'utf8'),
                 host: FS.split(':')[0], port: +FS.split(':')[1] },
  });
  const tok = (email, verified = true) => ({ email, email_verified: verified });
  who.anon = env.unauthenticatedContext().firestore();
  who.anonUser = env.authenticatedContext('anon1', { firebase: { sign_in_provider: 'anonymous' } }).firestore();
  who.alice = env.authenticatedContext('alice', tok('alice@example.com')).firestore();
  who.bob = env.authenticatedContext('bob', tok('Bob@Example.COM')).firestore();   // allowlisted, mixed case
  who.carol = env.authenticatedContext('carol', tok('carol@example.com')).firestore(); // signed in, not allowlisted
  who.dave = env.authenticatedContext('dave', tok('dave@example.com', false)).firestore(); // allowlisted, unverified
  who.forged = env.authenticatedContext('bob', { email: 'alice@example.com', email_verified: false }).firestore();
});

after(async () => { await env?.cleanup(); });

beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await db.doc('bass_beta/allowlist').set({ emails: ['alice@example.com', 'bob@example.com', 'dave@example.com'] });
    await db.doc('bass_beta/state_alice').set({ credits: 10 });
    await db.doc('users/alice').set({ theme: 'dark' });
    await db.doc('users/alice/pages/pk1').set({ html: '<p>private</p>', title: 'Mine' });
    await db.doc('users/alice/pagemeta/pk1').set({ title: 'Mine', shareKey: KEY_A });
    await db.doc('users/alice/tl/t1').set({ highlights: '[]' });
    await db.doc('users/alice/tl/t1/reports/r1').set({ data: 'x' });
    await db.doc('users/alice/alto_projects/p1').set({ data: '{}' });
    await db.doc('users/alice/alto_timelines/t1').set({ data: '{}' });
    await db.doc('users/alice/alto_timelines/t1/nodes/n1').set({ data: '{}' });
    await db.doc('users/alice/shared/' + KEY_A).set({ key: KEY_A });
    await db.doc('users/alice/bglib/b1').set({ e: '{}' });
    await db.doc(`shares/${KEY_A}`).set({ html: '<p>shared</p>', title: 'Shared', updatedAt: new Date() });
    await db.doc(`shares/${KEY_A}/private/owner`).set({ owner: 'alice' });
    await db.doc(`shares/${KEY_LEGACY}`).set({ html: '<p>old</p>', title: 'Old', owner: 'alice', updatedAt: new Date() });
    await db.doc(`shares/${KEY_LEGACY_C}`).set({ html: 'x', title: 't', owner: 'carol', updatedAt: new Date() });
    for (const u of ['carol', 'dave']) await db.doc(`users/${u}/pages/p`).set({ html: 'x' });
    await db.doc('terms_acceptance/alice_v1').set({ uid: 'alice', version: 'v1', ageConfirmed: true, acceptedAt: new Date() });
  });
});

const A_DOCS = ['users/alice', 'users/alice/pages/pk1', 'users/alice/pagemeta/pk1',
  'users/alice/tl/t1', 'users/alice/tl/t1/reports/r1', 'users/alice/alto_projects/p1',
  'users/alice/alto_timelines/t1', 'users/alice/alto_timelines/t1/nodes/n1',
  'users/alice/shared/' + KEY_A, 'users/alice/bglib/b1',
  `shares/${KEY_A}/private/owner`, 'terms_acceptance/alice_v1',
  'bass_beta/allowlist', 'bass_beta/bass_testers', 'bass_beta/state_alice'];
const A_COLLS = ['users', 'users/alice/pages', 'users/alice/pagemeta', 'users/alice/tl',
  'users/alice/alto_projects', 'users/alice/shared', 'shares', `shares/${KEY_A}/private`,
  'terms_acceptance', 'bass_beta'];
const OTHERS = ['anon', 'anonUser', 'bob', 'carol', 'dave', 'forged'];

// ── nobody but Alice reaches Alice's data ───────────────────────────────────

test("others cannot get, list, write or delete any of Alice's documents", async () => {
  for (const w of OTHERS) {
    const db = who[w];
    for (const p of A_DOCS) {
      await assertFails(db.doc(p).get());
      await assertFails(db.doc(p).set({ x: 1 }));
      await assertFails(db.doc(p).set({ x: 1 }, { merge: true }));
      await assertFails(db.doc(p).delete());
    }
    for (const c of A_COLLS) await assertFails(db.collection(c).get());
  }
});

test('no collection-group query reaches any account', async () => {
  for (const w of [...OTHERS, 'alice'])
    for (const g of ['pages', 'pagemeta', 'tl', 'reports', 'alto_projects', 'nodes', 'shared', 'private', 'owner'])
      await assertFails(who[w].collectionGroup(g).get());
});

test('a share is gettable by anyone with its key, and holds content only', async () => {
  for (const w of [...OTHERS, 'alice']) {
    const snap = await assertSucceeds(who[w].doc(`shares/${KEY_A}`).get());
    assert.deepEqual(Object.keys(snap.data()).sort(), ['html', 'title', 'updatedAt']);
    await assertSucceeds(who[w].doc('shares/' + KEY_NEW).get());   // a wrong key reads as missing
  }
});

test("others cannot change, take over or revoke Alice's share", async () => {
  for (const w of OTHERS) {
    const db = who[w];
    await assertFails(db.doc(`shares/${KEY_A}`).set({ html: 'x', title: 't', updatedAt: ts() }));
    await assertFails(db.doc(`shares/${KEY_A}`).delete());
    await assertFails(db.doc(`shares/${KEY_A}/private/owner`).set({ owner: 'bob' }));
    const b = db.batch();
    b.set(db.doc(`shares/${KEY_A}/private/owner`), { owner: 'bob' });
    b.set(db.doc(`shares/${KEY_A}`), { html: 'x', title: 't', updatedAt: ts() });
    await assertFails(b.commit());
    // A share made before owner records: its key is known to recipients.
    await assertFails(db.doc(`shares/${KEY_LEGACY}/private/owner`).set({ owner: 'bob' }));
    await assertFails(db.doc(`shares/${KEY_LEGACY}`).delete());
    await assertFails(db.doc(`shares/${KEY_LEGACY}`).set({ html: 'x', title: 't', updatedAt: ts() }));
  }
});

test('a forged owner field is refused', async () => {
  const db = who.bob;
  // An owner field in the public document is not allowed at all.
  const b1 = db.batch();
  b1.set(db.doc(`shares/${KEY_NEW}/private/owner`), { owner: 'bob' });
  b1.set(db.doc(`shares/${KEY_NEW}`), { html: 'x', title: 't', owner: 'bob', updatedAt: ts() });
  await assertFails(b1.commit());
  // Claiming a key in someone else's name.
  await assertFails(db.doc(`shares/${KEY_NEW}/private/owner`).set({ owner: 'alice' }));
  const b2 = db.batch();
  b2.set(db.doc(`shares/${KEY_NEW}/private/owner`), { owner: 'alice' });
  b2.set(db.doc(`shares/${KEY_NEW}`), { html: 'x', title: 't', updatedAt: ts() });
  await assertFails(b2.commit());
  // A token naming Alice's email but not her uid gets nothing of hers.
  await assertFails(who.forged.doc('users/alice').get());
  // Owner field in a user's own docs is meaningless to the rules.
  await assertFails(db.doc('users/alice/pages/pk2').set({ owner: 'bob', html: 'x' }));
});

// ── Alice's own access ──────────────────────────────────────────────────────

test('Alice reads, lists, writes and deletes her own data', async () => {
  const db = who.alice;
  for (const p of A_DOCS.filter(p => p.startsWith('users/'))) await assertSucceeds(db.doc(p).get());
  for (const c of ['users/alice/pages', 'users/alice/pagemeta', 'users/alice/alto_projects', 'users/alice/shared',
                   'users/alice/tl/t1/reports', 'users/alice/alto_timelines/t1/nodes', 'users/alice/bglib'])
    await assertSucceeds(db.collection(c).get());
  await assertSucceeds(db.doc('users/alice').set({ theme: 'light' }, { merge: true }));
  await assertSucceeds(db.doc('users/alice/pages/pk2').set({ html: 'x' }));
  await assertSucceeds(db.doc('users/alice/alto_timelines/t1/meta/connections').set({ data: '[]' }));
  await assertSucceeds(db.doc('users/alice/edits/t1').set({ e: 1 }));
  await assertSucceeds(db.doc('users/alice/bgimg/b1').set({ d: bytes(4) }));
  await assertSucceeds(db.doc('users/alice/alto_snapshots/pk1').set({ z: bytes(4), v: 1 }));
  await assertSucceeds(db.doc('users/alice/pages/pk2').delete());
  await assertSucceeds(db.doc(`shares/${KEY_A}/private/owner`).get());
  // ...but not the users collection, nor anything outside the known layout.
  await assertFails(db.collection('users').get());
  await assertFails(db.doc('users/alice/credits/c').set({ n: 100 }));
  await assertFails(db.doc('users/alice/ledger/l').set({ n: 1 }));
  await assertFails(db.doc('users/alice/tl/t1/other/x').set({ n: 1 }));
  await assertFails(db.doc('users/alice/alto_timelines/t1/other/x').set({ n: 1 }));
  await assertFails(db.doc('bass_beta/allowlist').get());
});

test("a timeline's chip bar choice (chips, chipsAt) syncs for its owner only", async () => {
  // alto-cloud.js merges { chips, chipsAt, updatedAt } into users/{uid}/tl/{tid}
  // next to bg/bgAt; a whole-timeline save carries them too.
  const fields = { chips: 'off', chipsAt: 1762380000000, updatedAt: ts() };
  await assertSucceeds(who.alice.doc('users/alice/tl/t1').set(fields, { merge: true }));
  await assertSucceeds(who.alice.doc('users/alice/tl/t2').set({ highlights: '[]', bg: 'h-rain', bgAt: 1, ...fields }));
  const got = await assertSucceeds(who.alice.doc('users/alice/tl/t1').get());
  assert.equal(got.data().chips, 'off');
  assert.equal(got.data().highlights, '[]');
  for (const w of OTHERS) {
    await assertFails(who[w].doc('users/alice/tl/t1').set(fields, { merge: true }));
    await assertFails(who[w].doc('users/alice/tl/t1').update({ chips: 'on', chipsAt: 2 }));
    await assertFails(who[w].doc('users/alice/tl/t1').get());
  }
  // Bob writes his own, not Alice's; Carol (off the allowlist) writes neither.
  await assertSucceeds(who.bob.doc('users/bob/tl/t1').set(fields, { merge: true }));
  await assertFails(who.carol.doc('users/carol/tl/t1').set(fields, { merge: true }));
});

test('Alice creates, updates and revokes a share; the owner never changes', async () => {
  const db = who.alice;
  const b = db.batch();
  b.set(db.doc(`shares/${KEY_NEW}/private/owner`), { owner: 'alice' });
  b.set(db.doc(`shares/${KEY_NEW}`), { z: bytes(10), enc: 'gzip', title: 'T', updatedAt: ts() });
  await assertSucceeds(b.commit());
  await assertSucceeds(db.doc(`shares/${KEY_NEW}`).set({ html: '<p>v2</p>', title: 'T2', updatedAt: ts() }));
  await assertFails(db.doc(`shares/${KEY_NEW}/private/owner`).set({ owner: 'bob' }));
  await assertFails(db.doc(`shares/${KEY_NEW}/private/owner`).delete());
  await assertSucceeds(db.doc(`shares/${KEY_NEW}`).delete());
  const gone = await assertSucceeds(who.anon.doc(`shares/${KEY_NEW}`).get());
  assert.equal(gone.exists, false);
  // A revoked key stays its owner's: nobody else can publish under it.
  for (const w of ['bob', 'carol']) {
    const r = who[w].batch();
    r.set(who[w].doc(`shares/${KEY_NEW}`), { html: 'x', title: 't', updatedAt: ts() });
    await assertFails(r.commit());
  }
});

test('share content: exact keys, types, sizes and key shape', async () => {
  const db = who.alice;
  const claimAnd = (key, data) => {
    const b = db.batch();
    b.set(db.doc(`shares/${key}/private/owner`), { owner: 'alice' });
    b.set(db.doc(`shares/${key}`), data);
    return b.commit();
  };
  const ok = { html: 'x', title: 't', updatedAt: ts() };
  await assertFails(claimAnd(KEY_NEW, { ...ok, extra: 1 }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, kind: 'project' }));
  await assertFails(claimAnd(KEY_NEW, { html: 'x', updatedAt: ts() }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, title: 5 }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, title: 'x'.repeat(301) }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, html: 5 }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, updatedAt: new Date(0) }));
  await assertFails(claimAnd(KEY_NEW, { ...ok, z: bytes(4), enc: 'gzip' }));
  await assertFails(claimAnd(KEY_NEW, { z: bytes(4), enc: 'br', title: 't', updatedAt: ts() }));
  await assertFails(claimAnd(KEY_NEW, { z: 'notbytes', enc: 'gzip', title: 't', updatedAt: ts() }));
  await assertFails(claimAnd(KEY_NEW, { z: bytes(4), title: 't', updatedAt: ts() }));
  for (const bad of ['short', KEY_NEW + 'a', 'NEWKEYABCDEFGHIJK23456', 'newkeyabcdefghijk2345l', 'newkeyabcdefghijk2345o', 'newkeyabcdefghijk2345_'])
    await assertFails(claimAnd(bad, ok));
  await assertSucceeds(claimAnd(KEY_NEW, ok));
});

test('a share made before owner records keeps working and can be migrated or revoked by its owner', async () => {
  const db = who.alice;
  await assertSucceeds(who.anon.doc(`shares/${KEY_LEGACY}`).get());
  // Updating it without claiming is refused; claiming it with the update works.
  await assertFails(db.doc(`shares/${KEY_LEGACY}`).update({ owner: firebase.firestore.FieldValue.delete(), updatedAt: ts() }));
  const b = db.batch();
  b.set(db.doc(`shares/${KEY_LEGACY}/private/owner`), { owner: 'alice' });
  b.update(db.doc(`shares/${KEY_LEGACY}`), { owner: firebase.firestore.FieldValue.delete(), updatedAt: ts() });
  await assertSucceeds(b.commit());
  const snap = await who.anon.doc(`shares/${KEY_LEGACY}`).get();
  assert.deepEqual(Object.keys(snap.data()).sort(), ['html', 'title', 'updatedAt']);
  assert.equal(snap.data().html, '<p>old</p>');
});

test('a legacy share is revoked together with its owner record, even off the allowlist', async () => {
  const db = who.carol;
  await assertFails(db.doc(`shares/${KEY_LEGACY_C}`).delete());     // needs the owner record
  const b = db.batch();
  b.set(db.doc(`shares/${KEY_LEGACY_C}/private/owner`), { owner: 'carol' });
  b.delete(db.doc(`shares/${KEY_LEGACY_C}`));
  await assertSucceeds(b.commit());
  await assertFails(who.bob.doc(`shares/${KEY_LEGACY_C}/private/owner`).set({ owner: 'bob' }));
});

// ── the beta allowlist ──────────────────────────────────────────────────────

test('writes need a verified email on the allowlist; reads of your own data do not', async () => {
  const claimAnd = (db, uid) => {
    const b = db.batch();
    b.set(db.doc(`shares/${KEY_NEW}/private/owner`), { owner: uid });
    b.set(db.doc(`shares/${KEY_NEW}`), { html: 'x', title: 't', updatedAt: ts() });
    return b.commit();
  };
  for (const [w, uid] of [['carol', 'carol'], ['dave', 'dave']]) {
    const db = who[w];
    await assertSucceeds(db.doc(`users/${uid}/pages/p`).get());
    await assertSucceeds(db.doc(`users/${uid}/pages/p`).delete());
    await assertFails(db.doc(`users/${uid}`).set({ theme: 'dark' }));
    await assertFails(db.doc(`users/${uid}/pages/p2`).set({ html: 'x' }));
    await assertFails(db.doc(`users/${uid}/tl/t/reports/r`).set({ data: 'x' }));
    await assertFails(db.doc(`shares/${KEY_NEW}/private/owner`).set({ owner: uid }));
    await assertFails(claimAnd(db, uid));
    await assertFails(db.doc(`terms_acceptance/${uid}_v1`).set({ uid, version: 'v1', ageConfirmed: true, acceptedAt: ts() }));
  }
  // An anonymous account has no email at all.
  await assertFails(who.anonUser.doc('users/anon1').set({ theme: 'dark' }));
  // Mixed-case email on the token matches the lowercase list.
  await assertSucceeds(who.bob.doc('users/bob').set({ theme: 'dark' }));
  await assertSucceeds(claimAnd(who.bob, 'bob'));
});

test('no client can read or write the allowlist', async () => {
  for (const w of [...OTHERS, 'alice']) {
    await assertFails(who[w].doc('bass_beta/allowlist').get());
    await assertFails(who[w].doc('bass_beta/allowlist').set({ emails: ['carol@example.com'] }));
    await assertFails(who[w].doc('bass_beta/allowlist').update({ emails: firebase.firestore.FieldValue.arrayUnion('carol@example.com') }));
    await assertFails(who[w].doc('bass_beta/allowlist').delete());
    await assertFails(who[w].doc('bass_beta/other').set({ x: 1 }));
  }
});

// Bass server-only collections (alto/store/erase.py BASS_COLLECTIONS): the Add-from-Drive token record and its token index, the tester
// list, the credit ledger, the Documents index and text, the day / period counters and the per-call metadata. Only the Bass proxy (admin)
// touches them; no client, not even the owner, may get, list, query or write one.
const BASS_SERVER_DOCS = ['bass_drive/alice', 'bass_drive_tok/9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
  'bass_beta/bass_testers', 'bass_credits/alice', 'bass_docs/alice', 'bass_doc_text/alice_f1', 'bass_beta_days/2026-11-03',
  'bass_beta_period_counters/2026-11', 'bass_beta_periods/2026-11', 'bass_beta_meta/alice_2026-11-03',
  'bass_research_consent/alice', 'bass_research_purge/t1'];

test('no client, not even the owner, can read, list, query or write a Bass server collection (bass_drive*, bass_testers, ledger)', async () => {
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    for (const d of BASS_SERVER_DOCS) await db.doc(d).set({ uid: 'alice', emails: ['alice@example.com'], refresh: 'opaque' });
  });
  for (const w of [...OTHERS, 'alice']) {
    const db = who[w];
    for (const d of BASS_SERVER_DOCS) {
      await assertFails(db.doc(d).get());
      await assertFails(db.doc(d).set({ x: 1 }));
      await assertFails(db.doc(d).set({ x: 1 }, { merge: true }));
      await assertFails(db.doc(d).delete());
      const coll = d.split('/')[0];
      await assertFails(db.collection(coll).get());
      await assertFails(db.collection(coll).where('uid', '==', 'alice').get());
    }
    await assertFails(db.doc('bass_drive/' + (w === 'alice' ? 'alice' : 'bob')).set({ refresh: 'x' }));     // nor create one's own
    await assertFails(db.doc('bass_drive_tok/new').set({ uid: w }));
  }
});

// ── terms acceptance ────────────────────────────────────────────────────────

test('terms: own record created once; no second write, update, delete, list or reading others', async () => {
  const db = who.bob;
  const rec = { uid: 'bob', version: 'v2', ageConfirmed: true, acceptedAt: ts() };
  await assertSucceeds(db.doc('terms_acceptance/bob_v2').set(rec));
  await assertSucceeds(db.doc('terms_acceptance/bob_v2').get());
  await assertFails(db.doc('terms_acceptance/bob_v2').set(rec));
  await assertFails(db.doc('terms_acceptance/bob_v2').update({ ageConfirmed: true }));
  await assertFails(db.doc('terms_acceptance/bob_v2').delete());
  await assertFails(db.collection('terms_acceptance').get());
  await assertFails(db.collection('terms_acceptance').where('uid', '==', 'bob').get());
  await assertFails(db.doc('terms_acceptance/alice_v1').get());
  await assertFails(db.doc('terms_acceptance/alice_v3').set({ ...rec, uid: 'alice', version: 'v3' }));
  await assertFails(db.doc('terms_acceptance/bob_v3').set({ ...rec, version: 'v4' }));
  await assertFails(db.doc('terms_acceptance/bob_v3').set({ ...rec, version: 'v3', ageConfirmed: false }));
  await assertFails(db.doc('terms_acceptance/bob_v3').set({ ...rec, version: 'v3', extra: 1 }));
  await assertFails(db.doc('terms_acceptance/bob_v3').set({ ...rec, version: 'v3', acceptedAt: new Date(0) }));
});

// ── over REST, with real and broken ID tokens ───────────────────────────────

const REST = `http://${FS}/v1/projects/${PROJECT}/databases/(default)/documents`;

async function idToken(email) {
  const base = `http://${AUTH}/identitytoolkit.googleapis.com/v1`;
  const r = await fetch(`${base}/accounts:signUp?key=fake`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'pw-123456', returnSecureToken: true }),
  });
  const j = await r.json();
  assert.ok(j.idToken, 'auth emulator did not sign up: ' + JSON.stringify(j));
  return j.idToken;
}

function forgeToken(claims) {
  const enc = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  return enc({ alg: 'none', typ: 'JWT' }) + '.' + enc({
    iss: `https://securetoken.google.com/${PROJECT}`, aud: PROJECT,
    iat: now - 7200, auth_time: now - 7200, exp: now - 3600, ...claims,
  }) + '.';
}

async function rest(token, method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const r = await fetch(`${REST}/${path}`, { method, headers, body: body && JSON.stringify(body) });
  return r.status;
}

test("over REST, B's real ID token reaches none of Alice's data", async () => {
  const tok = await idToken('bob-rest@example.com');
  for (const p of A_DOCS) {
    assert.equal(await rest(tok, 'GET', p), 403, 'GET ' + p);
    assert.equal(await rest(tok, 'PATCH', p, { fields: { x: { integerValue: '1' } } }), 403, 'PATCH ' + p);
    assert.equal(await rest(tok, 'DELETE', p), 403, 'DELETE ' + p);
  }
  for (const c of A_COLLS) assert.equal(await rest(tok, 'GET', c), 403, 'LIST ' + c);
  const q = await fetch(`${REST}:runQuery`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + tok },
    body: JSON.stringify({ structuredQuery: { from: [{ collectionId: 'pages', allDescendants: true }] } }),
  });
  assert.equal(q.status, 403, 'collection-group query');
  assert.equal(await rest(tok, 'GET', `shares/${KEY_A}`), 200);
  assert.equal(await rest(null, 'GET', `shares/${KEY_A}`), 200);
  assert.equal(await rest(null, 'GET', 'users/alice'), 403);
});

// The emulator does not check a token's expiry (production Firebase rejects an
// expired token before any rule runs), so this checks what the rules decide
// for one: an expired token naming B still reaches nothing of Alice's.
test("an expired token naming B reaches none of Alice's data", async () => {
  const tok = forgeToken({ user_id: 'bob', sub: 'bob', email: 'bob@example.com', email_verified: true,
                           firebase: { sign_in_provider: 'password' } });
  for (const p of A_DOCS) {
    assert.equal(await rest(tok, 'GET', p), 403, 'GET ' + p);
    assert.equal(await rest(tok, 'PATCH', p, { fields: { x: { integerValue: '1' } } }), 403, 'PATCH ' + p);
    assert.equal(await rest(tok, 'DELETE', p), 403, 'DELETE ' + p);
  }
  for (const c of A_COLLS) assert.equal(await rest(tok, 'GET', c), 403, 'LIST ' + c);
});

// ── pictures: users/{uid}/pics|picbig and shares/{key}/pics|picbig ──────────

const PIC = 'pic-abcd1234';
const KEY_C = 'cartkeyabcdefghijk2345';   // Carol's share (owner record, not allowlisted)
const pic = (n = 4) => ({ d: bytes(n), type: 'image/jpeg', t: 1, w: 10, h: 10 });
const PICS = ['pics', 'picbig'];

async function seedPics() {
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    for (const c of PICS) {
      await db.doc(`users/alice/${c}/${PIC}`).set(pic());
      await db.doc(`shares/${KEY_A}/${c}/${PIC}`).set(pic());
    }
    await db.doc(`shares/${KEY_C}`).set({ html: 'x', title: 't', updatedAt: new Date() });
    await db.doc(`shares/${KEY_C}/private/owner`).set({ owner: 'carol' });
  });
}

test("another user's, anonymous and unverified accounts cannot get or list Alice's pictures", async () => {
  await seedPics();
  for (const c of PICS) {
    for (const w of OTHERS) {
      await assertFails(who[w].doc(`users/alice/${c}/${PIC}`).get());
      await assertFails(who[w].collection(`users/alice/${c}`).get());
      await assertFails(who[w].doc(`users/alice/${c}/${PIC}`).set(pic()));
      await assertFails(who[w].doc(`users/alice/${c}/pic-zzzzzzzz`).set(pic()));
      await assertFails(who[w].doc(`users/alice/${c}/${PIC}`).delete());
    }
    await assertSucceeds(who.alice.doc(`users/alice/${c}/${PIC}`).get());
    await assertSucceeds(who.alice.collection(`users/alice/${c}`).get());
  }
  for (const w of OTHERS) await assertFails(who[w].collectionGroup('pics').get());
  await assertFails(who.alice.collectionGroup('picbig').get());
});

test("an owner's own picture write needs the allowlist (verified, listed email)", async () => {
  await seedPics();
  for (const c of PICS) {
    await assertSucceeds(who.alice.doc(`users/alice/${c}/pic-newnew01`).set(pic()));
    await assertSucceeds(who.bob.doc(`users/bob/${c}/${PIC}`).set(pic()));
    await assertFails(who.carol.doc(`users/carol/${c}/${PIC}`).set(pic()));     // signed in, not allowlisted
    await assertFails(who.dave.doc(`users/dave/${c}/${PIC}`).set(pic()));       // allowlisted, unverified
    await assertFails(who.anon.doc(`users/anon1/${c}/${PIC}`).set(pic()));
    await assertFails(who.anonUser.doc(`users/anon1/${c}/${PIC}`).set(pic()));
    await assertFails(who.forged.doc(`users/bob/${c}/${PIC}`).set(pic()));      // forged email, unverified
    await assertSucceeds(who.carol.doc(`users/carol/${c}/${PIC}`).delete());    // deleting one's own never needs it
    await assertSucceeds(who.alice.doc(`users/alice/${c}/${PIC}`).delete());
  }
});

test('a share picture is gettable with a valid key while the share exists, and never listable', async () => {
  await seedPics();
  for (const c of PICS) {
    for (const w of [...OTHERS, 'alice']) {
      const snap = await assertSucceeds(who[w].doc(`shares/${KEY_A}/${c}/${PIC}`).get());
      assert.deepEqual(Object.keys(snap.data()).sort(), ['d', 'h', 't', 'type', 'w']);
      await assertFails(who[w].collection(`shares/${KEY_A}/${c}`).get());
    }
  }
  for (const w of [...OTHERS, 'alice']) {
    await assertFails(who[w].collectionGroup('pics').get());
    await assertFails(who[w].collectionGroup('picbig').get());
  }
});

test('a share picture is unreadable once its share is deleted, even if the copy is left behind', async () => {
  await seedPics();
  await assertSucceeds(who.alice.doc(`shares/${KEY_A}`).delete());   // the owner stops the link; pic copies remain
  for (const c of PICS) for (const w of [...OTHERS, 'alice'])
    await assertFails(who[w].doc(`shares/${KEY_A}/${c}/${PIC}`).get());
});

test('a bad ref or a bad key never reads or writes a share picture', async () => {
  await seedPics();
  for (const c of PICS) {
    for (const ref of ['bad', 'PIC-ABCD1234', 'pic-abc', 'pic-abcd_1234', 'pic-abcdefghijklmnopq', PIC + '!']) {
      await assertFails(who.anon.doc(`shares/${KEY_A}/${c}/${ref}`).get());
      await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${ref}`).set(pic()));
    }
    for (const key of ['short', KEY_A.toUpperCase(), KEY_A + 'a', KEY_A.replace(/.$/, '1')]) {    // not 22 symbols of the alphabet (1 is outside it)
      await assertFails(who.anon.doc(`shares/${key}/${c}/${PIC}`).get());
      await assertFails(who.alice.doc(`shares/${key}/${c}/${PIC}`).set(pic()));
    }
    await assertFails(who.anon.doc(`shares/${KEY_NEW}/${c}/${PIC}`).get());       // no such share
  }
  await assertFails(who.anon.doc(`shares/${KEY_A}/other/${PIC}`).get());          // not a picture collection
  await assertFails(who.alice.doc(`shares/${KEY_A}/other/${PIC}`).set(pic()));
});

test("only the share's owner writes or deletes its pictures, and only in the exact shape", async () => {
  await seedPics();
  for (const c of PICS) {
    for (const w of ['anon', 'anonUser', 'bob', 'carol', 'dave', 'forged']) {
      await assertFails(who[w].doc(`shares/${KEY_A}/${c}/pic-newnew01`).set(pic()));
      await assertFails(who[w].doc(`shares/${KEY_A}/${c}/${PIC}`).set(pic()));
      await assertFails(who[w].doc(`shares/${KEY_A}/${c}/${PIC}`).delete());
    }
    await assertFails(who.alice.doc(`shares/${KEY_LEGACY}/${c}/${PIC}`).set(pic()));   // legacy share: no owner record
    await assertFails(who.alice.doc(`shares/${KEY_C}/${c}/${PIC}`).set(pic()));        // someone else's share
    await assertFails(who.carol.doc(`shares/${KEY_C}/${c}/${PIC}`).set(pic()));        // owner, but not allowlisted
    await assertSucceeds(who.alice.doc(`shares/${KEY_A}/${c}/pic-newnew01`).set(pic()));
    await assertSucceeds(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set(pic(960000)));
    await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set(pic(960001)));
    await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set({ ...pic(), extra: 1 }));
    await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set({ ...pic(), owner: 'bob' }));
    await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set({ ...pic(), d: 'not bytes' }));
    await assertFails(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set({ type: 'image/jpeg', t: 1, w: 1, h: 1 }));   // no bytes
    await assertSucceeds(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).set({ d: bytes(4) }, { merge: true }));
    await assertSucceeds(who.alice.doc(`shares/${KEY_A}/${c}/${PIC}`).delete());
    await assertSucceeds(who.carol.doc(`shares/${KEY_C}/${c}/${PIC}`).delete());      // revoking never needs the allowlist
  }
});
