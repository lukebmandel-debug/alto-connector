/* ────────────────────────────────────────────────────────────────────────────
   alto-cloud.js — v3 (per-timeline merge sync) for the Alto connector site.

   Derived from Terrarium-Alto's v2 with the SAME merge semantics (highlight
   union by id+quote-hash, tombstone ledger, longer-note wins; reports one doc
   per id with {deleted} tombstones, 25-newest cap; theme last-change-wins),
   generalized to many timelines per user:

     users/{uid}                      — { theme }           (account-wide)
     users/{uid}/tl/{tid}             — { highlights, hl_removed, updatedAt }
     users/{uid}/tl/{tid}/reports/{id}— { data, deleted, ts }

   Which timeline this page belongs to:
     timeline pages:  <script src="/alto-cloud.js" data-tid="{tid}">
     reports page:    ?course={tid}
     homepage:        none (theme + account only)

   OFFLINE-SAFE: no-op unless served over http(s).
   ──────────────────────────────────────────────────────────────────────────── */
(async () => {
  if (location.protocol !== 'http:' && location.protocol !== 'https:') return;

  // Filled in at publish time from the PUBLISHER's own Firebase project — see
  // alto/cloud/__init__.py. Empty here on purpose: a project baked into this
  // file would collect every reader of every published timeline into one
  // Auth tenant, Firestore and free-tier quota. Empty = sync off, highlights
  // stay in localStorage.
  const firebaseConfig = {
    apiKey:            "",
    authDomain:        "",
    projectId:         "",
    storageBucket:     "",
    messagingSenderId: "",
    appId:             "",
  };
  const configured = !!firebaseConfig.apiKey && !firebaseConfig.apiKey.startsWith('PASTE_');

  // Which timeline is this page about?
  const scriptEl = document.querySelector('script[src*="alto-cloud.js"]');
  const TID = (scriptEl && scriptEl.dataset && scriptEl.dataset.tid)
    || new URLSearchParams(location.search).get('course') || null;

  let _resolveReady;
  const ready = new Promise(r => { _resolveReady = r; });
  const cloud = {
    enabled: configured,
    user: null,
    tid: TID,
    signIn:  async () => { await ready; return _signIn(); },
    signOut: async () => { await ready; return _signOut(); },
    sync:    async () => { await ready; return requestSync('manual'); },
  };
  window.AltoCloud = cloud;

  if (!configured) { console.warn('[AltoCloud] not configured — local-only.'); return; }

  const _note = document.querySelector('.acct-note');
  if (_note) _note.textContent = 'Your highlights, notes, and reports sync securely across your devices.';

  const V = '10.12.5';
  const [{ initializeApp },
         { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect,
           getRedirectResult, signOut, onAuthStateChanged, browserLocalPersistence,
           setPersistence },
         { getFirestore, doc, collection, setDoc, onSnapshot, serverTimestamp }] =
    await Promise.all([
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-app.js`),
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-auth.js`),
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-firestore.js`),
    ]);

  const app  = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db   = getFirestore(app);
  try { await setPersistence(auth, browserLocalPersistence); } catch (e) {}

  const HL_KEY = TID ? `alto-hl-${TID}` : null;
  const RP_KEY = TID ? `alto-rp-${TID}` : null;
  const TH_KEY = 'alto-theme-v1';
  const META_KEY = TID ? `alto-cloud-meta-v3-${TID}` : 'alto-cloud-meta-v3';
  const RP_CAP = 25, TOMB_CAP = 800;

  const origSet = localStorage.setItem.bind(localStorage);
  const origGet = localStorage.getItem.bind(localStorage);

  const meta = (() => { try { return JSON.parse(origGet(META_KEY) || '{}'); } catch (e) { return {}; } })();
  const saveMeta = () => { try { origSet(META_KEY, JSON.stringify(meta)); } catch (e) {} };

  const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); };
  const parseArr = s => { try { const a = JSON.parse(s || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } };
  const hlKey = h => ((h && h.id) || 'x') + '§' + hash(String((h && h.quote) || ''));
  const rpTs = id => { const n = parseInt(String(id || '').replace(/^r/, ''), 10); return isNaN(n) ? 0 : n; };

  function mergeHl(localArr, remoteArr, removed) {
    const out = [], seen = new Set();
    const rmap = new Map(remoteArr.map(h => [hlKey(h), h]));
    for (const h of localArr) {
      const k = hlKey(h);
      if (removed.has(k) || seen.has(k)) continue;
      seen.add(k);
      const r = rmap.get(k);
      out.push(r && String(r.note || '').length > String(h.note || '').length ? r : h);
    }
    for (const h of remoteArr) {
      const k = hlKey(h);
      if (removed.has(k) || seen.has(k)) continue;
      seen.add(k); out.push(h);
    }
    return out;
  }

  function mergeReports(localArr, remoteMap, tombs) {
    const byId = new Map();
    for (const e of localArr) if (e && e.id && !tombs.has(e.id)) byId.set(e.id, e);
    for (const [id, e] of remoteMap) if (!tombs.has(id) && !byId.has(id)) byId.set(id, e);
    return [...byId.values()].sort((a, b) => rpTs(b.id) - rpTs(a.id)).slice(0, RP_CAP);
  }

  function applyHighlightsLocally(mergedArr, mergedStr) {
    origSet(HL_KEY, mergedStr);
    try { window.highlights = mergedArr; } catch (e) {}
    if (typeof window.loadHighlights === 'function') {
      const keep = new Set(mergedArr.map(h => h.id));
      document.querySelectorAll('mark[data-hl-id]').forEach(m => {
        if (!keep.has(m.getAttribute('data-hl-id'))) {
          const p = m.parentNode;
          while (m.firstChild) p.insertBefore(m.firstChild, m);
          p.removeChild(m);
        }
      });
      try { window.loadHighlights(); } catch (e) {}
      if (typeof window.updateNotesToggle === 'function') { try { window.updateNotesToggle(); } catch (e) {} }
    }
  }

  let lastReload = 0;
  function scheduleReload() {
    if (!/\/reports/i.test(location.pathname)) return;
    if (document.querySelector('input:focus, textarea:focus')) { setTimeout(scheduleReload, 5000); return; }
    const now = Date.now();
    if (now - lastReload < 4000) return;
    lastReload = now;
    location.reload();
  }

  function applyTheme(theme) {
    origSet(TH_KEY, theme);
    try { document.documentElement.classList.toggle('dark', theme === 'dark'); } catch (e) {}
  }

  let remoteUser = undefined;      // users/{uid} (theme)
  let remoteMain = undefined;      // users/{uid}/tl/{tid}
  let remoteReports = undefined;   // Map id -> entry
  let remoteTombs = new Set();
  let syncing = false, rerun = false, pushTimer = null;

  function requestSync(trigger) {
    clearTimeout(pushTimer);
    pushTimer = setTimeout(() => { syncNow(trigger).catch(e => console.warn('[AltoCloud] sync failed', e)); }, 250);
  }

  async function syncNow(trigger) {
    if (!cloud.user || remoteUser === undefined) return;
    if (TID && (remoteMain === undefined || remoteReports === undefined)) return;
    if (syncing) { rerun = true; return; }
    syncing = true;
    try {
      const uid = cloud.user.uid;
      const userRef = doc(db, 'users', uid);

      /* ---- theme (account-wide) ---- */
      const localTheme = origGet(TH_KEY);
      const remoteTheme = remoteUser ? (remoteUser.theme || null) : null;
      let pushTheme = null;
      if (localTheme !== meta.lastTheme && localTheme != null) pushTheme = localTheme;
      else if (remoteTheme != null && remoteTheme !== localTheme) applyTheme(remoteTheme);
      const themeAfter = pushTheme || origGet(TH_KEY);
      if (pushTheme && pushTheme !== remoteTheme) {
        await setDoc(userRef, { theme: themeAfter, updatedAt: serverTimestamp() }, { merge: true });
      }
      meta.lastTheme = themeAfter;

      if (TID) {
        const mainRef = doc(db, 'users', uid, 'tl', TID);

        /* ---- highlights ---- */
        const localArr = parseArr(origGet(HL_KEY));
        const localStr = JSON.stringify(localArr);
        const remoteArr = parseArr(remoteMain ? remoteMain.highlights : '[]');
        const removed = new Set(Array.isArray(remoteMain && remoteMain.hl_removed) ? remoteMain.hl_removed : []);
        const prevArr = parseArr(meta.lastHl);
        const nowKeys = new Set(localArr.map(hlKey));
        for (const h of prevArr) { const k = hlKey(h); if (!nowKeys.has(k)) removed.add(k); }
        const merged = mergeHl(localArr, remoteArr, removed);
        const mergedStr = JSON.stringify(merged);
        const tombs = [...removed].slice(-TOMB_CAP);

        if (mergedStr !== localStr) applyHighlightsLocally(merged, mergedStr);
        else origSet(HL_KEY, mergedStr);

        const remoteTombsStr = JSON.stringify(Array.isArray(remoteMain && remoteMain.hl_removed) ? remoteMain.hl_removed : []);
        const needMainPush = !remoteMain
          || mergedStr !== (remoteMain.highlights || '[]')
          || JSON.stringify(tombs) !== remoteTombsStr;
        if (needMainPush) {
          await setDoc(mainRef, { highlights: mergedStr, hl_removed: tombs,
                                  updatedAt: serverTimestamp() }, { merge: true });
        }
        meta.lastHl = mergedStr;

        /* ---- reports ---- */
        const localRp = parseArr(origGet(RP_KEY)).filter(e => e && e.id);
        const remoteRp = new Map(remoteReports);
        const tombsRp = new Set(remoteTombs);
        const prevIds = new Set(Array.isArray(meta.lastRpIds) ? meta.lastRpIds : []);
        const localIds = new Set(localRp.map(e => e.id));
        const newlyDeleted = [...prevIds].filter(id => !localIds.has(id) && !tombsRp.has(id));
        const mergedRp = mergeReports(localRp, remoteRp, new Set([...tombsRp, ...newlyDeleted]));
        const mergedRpStr = JSON.stringify(mergedRp);
        const localRpStr = JSON.stringify(localRp);
        if (mergedRpStr !== localRpStr) { origSet(RP_KEY, mergedRpStr); scheduleReload(); }

        const writes = [];
        for (const id of newlyDeleted)
          writes.push(setDoc(doc(db, 'users', uid, 'tl', TID, 'reports', id),
                             { deleted: true, ts: rpTs(id) }, { merge: true }));
        for (const e of mergedRp) {
          const have = remoteRp.get(e.id);
          if (!have || JSON.stringify(have) !== JSON.stringify(e))
            writes.push(setDoc(doc(db, 'users', uid, 'tl', TID, 'reports', e.id),
              { data: JSON.stringify(e), deleted: false, ts: rpTs(e.id) }));
        }
        if (writes.length) await Promise.all(writes);
        meta.lastRpIds = mergedRp.map(e => e.id);
      }
      saveMeta();
    } finally {
      syncing = false;
      if (rerun) { rerun = false; requestSync('rerun'); }
    }
  }

  localStorage.setItem = function (k, v) {
    origSet(k, v);
    if (cloud.user && (k === HL_KEY || k === RP_KEY || k === TH_KEY)) requestSync('local-change');
  };

  window.addEventListener('storage', ev => {
    if (!ev || ev.storageArea !== localStorage) return;
    if (HL_KEY && ev.key === HL_KEY && ev.newValue != null) {
      applyHighlightsLocally(parseArr(ev.newValue), ev.newValue);
    } else if (RP_KEY && ev.key === RP_KEY) {
      scheduleReload();
    } else if (ev.key === TH_KEY && ev.newValue != null) {
      try { document.documentElement.classList.toggle('dark', ev.newValue === 'dark'); } catch (e) {}
    }
  });

  const provider = new GoogleAuthProvider();
  async function _signIn() {
    try { return await signInWithPopup(auth, provider); }
    catch (e) {
      if (e && (e.code === 'auth/popup-blocked' || e.code === 'auth/operation-not-supported-in-this-environment'))
        return signInWithRedirect(auth, provider);
      throw e;
    }
  }
  const _signOut = () => signOut(auth);
  try { await getRedirectResult(auth); } catch (e) {}

  let unsubUser = null, unsubMain = null, unsubRp = null;

  onAuthStateChanged(auth, (user) => {
    cloud.user = user || null;
    for (const u of [unsubUser, unsubMain, unsubRp]) { try { u && u(); } catch (e) {} }
    unsubUser = unsubMain = unsubRp = null;
    remoteUser = undefined; remoteMain = undefined; remoteReports = undefined; remoteTombs = new Set();

    if (user) {
      const session = {
        provider: 'google', name: user.displayName || '', email: user.email || '',
        uid: user.uid, photo: user.photoURL || '', ts: new Date().toISOString(), v: 1,
      };
      try { origSet('alto-account-v1', JSON.stringify(session)); } catch (e) {}
      if (typeof window.renderAccount === 'function') { try { window.renderAccount(); } catch (e) {} }

      unsubUser = onSnapshot(doc(db, 'users', user.uid), snap => {
        if (snap.metadata.hasPendingWrites) return;
        remoteUser = snap.exists() ? snap.data() : null;
        requestSync('user-snapshot');
      }, e => console.warn('[AltoCloud] user listener', e));

      if (TID) {
        unsubMain = onSnapshot(doc(db, 'users', user.uid, 'tl', TID), snap => {
          if (snap.metadata.hasPendingWrites) return;
          remoteMain = snap.exists() ? snap.data() : null;
          requestSync('main-snapshot');
        }, e => console.warn('[AltoCloud] main listener', e));

        unsubRp = onSnapshot(collection(db, 'users', user.uid, 'tl', TID, 'reports'), snap => {
          if (snap.metadata.hasPendingWrites) return;
          const live = new Map(); const tombs = new Set();
          snap.forEach(dnap => {
            const d = dnap.data() || {};
            if (d.deleted) { tombs.add(dnap.id); return; }
            try { const e = JSON.parse(d.data); if (e && e.id) live.set(dnap.id, e); } catch (e2) {}
          });
          remoteReports = live; remoteTombs = tombs;
          requestSync('reports-snapshot');
        }, e => console.warn('[AltoCloud] reports listener', e));
      }
    } else {
      try { localStorage.removeItem('alto-account-v1'); } catch (e) {}
      if (typeof window.renderAccount === 'function') { try { window.renderAccount(); } catch (e) {} }
    }
  });

  _resolveReady();
})();
