// Bass Documents originals (storage.rules users/{uid}/bass/{fid}) and the server-only library in Firestore, on the emulator.
// Luke's rule: no user may ever see or reach another user's files. Every refusal below must hold.
import { test, before, after } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import 'firebase/compat/storage';
import 'firebase/compat/firestore';

const HERE = dirname(fileURLToPath(import.meta.url));
const ST = process.env.FIREBASE_STORAGE_EMULATOR_HOST || '127.0.0.1:9199';
const FS = process.env.FIRESTORE_EMULATOR_HOST || '127.0.0.1:8080';
const PDF = { contentType: 'application/pdf' };
const bytes = (n) => { const b = new Uint8Array(n); b.set([0x25, 0x50, 0x44, 0x46]); return b; };
let env, A, B, N, AF, BF;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-alto-security',
    storage: { rules: readFileSync(join(HERE, '../../storage.rules'), 'utf8'), host: ST.split(':')[0], port: +ST.split(':')[1] },
    firestore: { rules: readFileSync(join(HERE, '../../firestore.rules'), 'utf8'), host: FS.split(':')[0], port: +FS.split(':')[1] },
  });
  // what the proxy writes (admin): alice has f1 (live, 2,000 bytes), f2 (deleted, recoverable), f3 (listed bigger than 5 MB), f4 (100 bytes)
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await db.doc('bass_docs/alice').set({ scopes: { s1: { kind: 'class', name: 'Torts' } }, files: {
      f1: { scope: 's1', bytes: 2000 }, f2: { scope: 's1', bytes: 2000, deleted: '2026-10-30T13:00:00Z' },
      f3: { scope: 's1', bytes: 6000000 }, f4: { scope: 's1', bytes: 100 }, f5: { scope: 's1', bytes: 5000 } } });
    await db.doc('bass_docs/bob').set({ scopes: {}, files: { b1: { scope: 'x', bytes: 2000 } } });
    await db.doc('bass_doc_text/alice_f1').set({ uid: 'alice', text: 'secret notes' });
    await db.doc('bass_beta_meta/alice_2026-11-03').set({ uid: 'alice', lines: [] });
    const st = ctx.storage();
    await st.ref('users/alice/bass/f2').put(bytes(100), PDF);
    await st.ref('users/bob/bass/b1').put(bytes(100), PDF);
    await st.ref('users/alice/other/x').put(bytes(10), PDF);
  });
  const ver = (e) => ({ email: e, email_verified: true });
  const alice = env.authenticatedContext('alice', ver('alice@example.com')), bob = env.authenticatedContext('bob', ver('bob@example.com'));
  A = alice.storage(); B = bob.storage(); N = env.unauthenticatedContext().storage(); AF = alice.firestore(); BF = bob.firestore();
});

after(async () => { await env?.cleanup(); });

test('the owner uploads a listed file once and reads it back', async () => {
  await assertSucceeds(A.ref('users/alice/bass/f1').put(bytes(1500), PDF));
  await assertSucceeds(A.ref('users/alice/bass/f1').getMetadata());
  await assertFails(A.ref('users/alice/bass/f1').put(bytes(10), PDF));          // no overwrite
  await assertFails(A.ref('users/alice/bass/f1').delete());                      // no delete from the page
});

test('a second user, and a signed-out caller, are refused every way', async () => {
  for (const st of [B, N]) {
    await assertFails(st.ref('users/alice/bass/f1').getDownloadURL());
    await assertFails(st.ref('users/alice/bass/f1').getMetadata());
    await assertFails(st.ref('users/alice/bass/f1').put(bytes(10), PDF));
    await assertFails(st.ref('users/alice/bass/b1').put(bytes(10), PDF));
    await assertFails(st.ref('users/alice/bass/f1').delete());
    await assertFails(st.ref('users/alice/bass').listAll());
  }
  await assertFails(A.ref('users/bob/bass/b1').getDownloadURL());
});

test("the owner's own limits", async () => {
  await assertFails(A.ref('users/alice/bass').listAll());                        // nothing is listable
  await assertFails(A.ref('users/alice/bass/zz').put(bytes(10), PDF));            // never listed by the proxy
  await assertFails(A.ref('users/alice/bass/f2').getDownloadURL());               // deleted (in recovery): unreadable, owner too
  await assertFails(A.ref('users/alice/bass/f4').put(bytes(500), PDF));           // bigger than the size the proxy recorded
  await assertFails(A.ref('users/alice/bass/f3').put(bytes(5000001), PDF));       // over 5 MB
  await assertFails(A.ref('users/alice/bass/f5').put(bytes(100), { contentType: 'text/html' }));
  await assertFails(A.ref('users/alice/other/x').getDownloadURL());              // any other path, owner too
  await assertFails(A.ref('users/alice/x').put(bytes(10), PDF));
});

test('the library index, texts and metadata log are server only', async () => {
  for (const p of ['bass_docs/alice', 'bass_doc_text/alice_f1', 'bass_beta_meta/alice_2026-11-03']) {
    await assertFails(AF.doc(p).get());
    await assertFails(BF.doc(p).get());
    await assertFails(AF.doc(p).set({ files: {} }));
  }
});
