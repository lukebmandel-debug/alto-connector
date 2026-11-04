// Firebase Storage holds nothing of Alto's: every client request is denied.
import { test, before, after } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { initializeTestEnvironment, assertFails } from '@firebase/rules-unit-testing';
import 'firebase/compat/storage';

const HERE = dirname(fileURLToPath(import.meta.url));
const ST = process.env.FIREBASE_STORAGE_EMULATOR_HOST || '127.0.0.1:9199';
let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-alto-security',
    storage: { rules: readFileSync(join(HERE, '../../storage.rules'), 'utf8'),
               host: ST.split(':')[0], port: +ST.split(':')[1] },
  });
  await env.withSecurityRulesDisabled(async (ctx) => {
    await ctx.storage().ref('builds/alice/t1/private.html').putString('<p>private</p>');
  });
});

after(async () => { await env?.cleanup(); });

test('no client reads, writes, lists or deletes anything in Storage', async () => {
  const actors = [env.unauthenticatedContext(),
    env.authenticatedContext('alice', { email: 'alice@example.com', email_verified: true }),
    env.authenticatedContext('bob', { email: 'bob@example.com', email_verified: true })];
  for (const ctx of actors) {
    const st = ctx.storage();
    for (const p of ['builds/alice/t1/private.html', 'users/alice/x', 'x']) {
      await assertFails(st.ref(p).getDownloadURL());
      await assertFails(st.ref(p).getMetadata());
      await assertFails(st.ref(p).putString('x'));
      await assertFails(st.ref(p).delete());
    }
    await assertFails(st.ref('builds').listAll());
  }
});
