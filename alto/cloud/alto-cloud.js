/* ────────────────────────────────────────────────────────────────────────────
   alto-cloud.js — v3 (per-timeline merge sync) for the Alto connector site.

   Derived from Terrarium-Alto's v2 with the SAME merge semantics (highlight
   union by id+quote-hash, tombstone ledger, longer-note wins; reports one doc
   per id with {deleted} tombstones, 25-newest cap; theme last-change-wins),
   generalized to many timelines per user:

     users/{uid}                      — { theme }           (account-wide)
     users/{uid}/tl/{tid}             — { highlights, hl_removed, updatedAt }
     users/{uid}/tl/{tid}/reports/{id}— { data, deleted, ts }
     users/{uid}/pages/{key}          — { html, updatedAt }
     users/{uid}/pagemeta/{key}       — { title, heading, project, units,
                                          search, shareKey, updatedAt }

   That last one is a whole private timeline page, filed under the opaque key
   in its /pv/{key}/ URL rather than under a timeline id, so nothing about it
   is legible from outside. It is covered by the same users/{uid} rule as
   everything else here — which is what actually keeps it private.

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

  let _resolveReady, _isReady = false;
  const ready = new Promise(r => { _resolveReady = () => { _isReady = true; r(); }; });
  const cloud = {
    enabled: configured,
    user: null,
    known: false,
    tid: TID,
    // Synchronous once Firebase is up: the popup must open inside the tap that
    // asked for it, and even an already-resolved await gives Safari on iOS a
    // reason to call it unprompted and block it.
    signIn:  () => _isReady ? _signIn() : ready.then(() => _signIn()),
    signOut: async () => { await ready; return _signOut(); },
    sync:    async () => { await ready; return requestSync('manual'); },
    // Private timelines: the page itself lives in Firestore under the owner's
    // uid, so the rules decide who may read it. `ready` never resolves when the
    // publisher has no Firebase project, hence the check before the await.
    getPage: async (key) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _getPage(key);
    },
    putPage: async (key, html, title) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _putPage(key, html, title);
    },
    // Everything this account has published privately. This is what lets the
    // homepage show you your own private timelines — without it they are
    // reachable only by a 22-character URL you have to have kept.
    listPages: async () => {
      if (!configured) return [];
      await ready; return _listPages();
    },
    // Backfill for pages uploaded before titles were stored. Without it every
    // timeline published up to now lists as "Untitled" forever, because the
    // list deliberately never fetches the 600 KB the title could be read from.
    ensureTitle: async (key, title, tid) => {
      if (!configured) return false;
      await ready; return _ensureTitle(key, title, tid);
    },
    // The listing record for a page, (re)written from the html in hand when it
    // is missing or older than this code — the private shell calls it each
    // time it opens a page, which is what heals pages uploaded before it.
    ensureMeta: async (key, html) => {
      if (!configured) return false;
      await ready; return _ensureMeta(key, html);
    },
    // Just the listing record — a few KB, where getPage is the whole page.
    // The private shell uses its updatedAt to decide whether a cached copy
    // is still current without downloading the page to find out.
    getPageMeta: async (key) => {
      if (!configured) return null;
      await ready; return _getPageMeta(key);
    },
    metaOf: (html) => _metaOf(html),
    /* ── shares ──────────────────────────────────────────────────────────
       A share is opened by someone signed in to nothing, so getShare must
       work with no user at all — the rules allow `get` on shares/{key} and
       nothing else. Everything that WRITES one needs the owner. */
    getShare: async (key) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _getShare(key);
    },
    /* The three things an owner does with a share. A share is a SNAPSHOT: it
       is written by shareCreate and does not move again until sharePush is
       called, so republishing a timeline never changes what a recipient sees.
       That is the point — the owner decides when their work goes out. */
    shareCreate: async (pageKey, title) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _sharePush(pageKey, title, true);
    },
    sharePush: async (pageKey, title) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _sharePush(pageKey, title, false);
    },
    shareRevoke: async (pageKey) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _shareRevoke(pageKey);
    },
    shareUrl: (shareKey) => location.origin + '/s/' + shareKey + '/',
    reidentify: (html, shareKey) => _reidentify(html, shareKey),
    /* Shares someone has kept. A REFERENCE, never a copy: if this stored the
       html, revoking a share would leave every recipient still reading it. */
    saveShare: async (key, title, html) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _saveShare(key, title, html);
    },
    // Adds colours + search terms to a share this account already kept.
    // Never creates one: keeping a share is the reader's decision.
    refreshShared: async (key, html) => {
      if (!configured) return false;
      await ready; return _refreshShared(key, html);
    },
    listShared: async () => {
      if (!configured) return [];
      await ready; return _listShared();
    },
    forgetShare: async (key) => {
      if (!configured) return false;
      await ready; return _forgetShare(key);
    },
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
         { getFirestore, doc, collection, setDoc, getDoc, getDocs, deleteDoc,
           onSnapshot, serverTimestamp }] =
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

  /* ── private pages ─────────────────────────────────────────────────────────
     users/{uid}/pages/{tid} = { html, tid, title, updatedAt }. Covered by the
     SAME rule as everything else under users/{uid}, so no rules change was
     needed: a reader who is not the owner is refused by Firestore itself.
     Firestore caps a document at 1 MiB; stop short of it with a message the
     author can act on. ─────────────────────────────────────────────────────── */
  const MAX_PAGE_BYTES = 1000000;   // Firestore's document limit is 1 MiB; see private_shell.py

  /* ── listing records ──────────────────────────────────────────────────────
     Firestore always returns whole documents, so listing users/{uid}/pages
     downloaded every private timeline in full (600 KB apiece) just to print
     their titles — the homepage cost more than opening a timeline. The list
     reads users/{uid}/pagemeta instead: one small document per page, holding
     what a chip and the homepage search need and nothing else. ─────────── */
  const META_V = 1;
  const SEARCH_CAP = 600, DESC_CAP = 280;

  const _unq = s => String(s || '').replace(/\\'/g, "'").replace(/\\\\/g, '\\');
  const _unent = s => String(s || '').replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

  function _metaOf(html) {
    const h = String(html || '');
    const lm = /<meta name="alto-label" content="([^"]*)"/i.exec(h);
    const project = lm ? _unent(lm[1]).trim() : '';
    const tm = /<title>([^<]*)<\/title>/i.exec(h);
    const heading = tm ? _unent(tm[1]).replace(/\s*\u2014\s*Alto(\s+Timeline)?\s*$/, '').trim() : '';
    const units = [];
    const ps = h.indexOf('const PHASE_META = [');
    if (ps >= 0) {
      const pe = h.indexOf('\n];', ps);
      const block = h.slice(ps, pe < 0 ? ps + 20000 : pe);
      const re = /colorRaw:'(#[0-9a-fA-F]{3,8})'/g;
      let m;
      while ((m = re.exec(block))) units.push(m[1]);
    }
    const search = [];
    const ns = h.indexOf('const NODES_SRC=[');
    if (ns >= 0) {
      const ne = h.indexOf('\n];', ns);
      const block = h.slice(ns, ne < 0 ? ns + 400000 : ne);
      const re = /\{id:'((?:[^'\\]|\\.)*)'[\s\S]*?title:'((?:[^'\\]|\\.)*)'\s*,\s*desc:'((?:[^'\\]|\\.)*)'/g;
      let m;
      while ((m = re.exec(block)) && search.length < SEARCH_CAP)
        search.push({ id: _unq(m[1]), t: _unq(m[2]), d: _unq(m[3]).slice(0, DESC_CAP) });
    }
    return { title: project || heading, heading, project, tid: _identityOf(h),
             units, search, v: META_V };
  }

  async function _getPageMeta(key) {
    const u = auth.currentUser;
    if (!u || !key) return null;
    const snap = await getDoc(doc(db, 'users', u.uid, 'pagemeta', key));
    if (!snap.exists()) return null;
    const v = snap.data() || {};
    return Object.assign({}, v, { updatedAt: (v.updatedAt && v.updatedAt.seconds) || 0 });
  }

  async function _ensureMeta(key, html) {
    const u = auth.currentUser;
    if (!u || !key || !html) return false;
    const ref = doc(db, 'users', u.uid, 'pagemeta', key);
    const snap = await getDoc(ref);
    if (snap.exists() && ((snap.data() || {}).v || 0) >= META_V) return false;
    const page = await getDoc(doc(db, 'users', u.uid, 'pages', key));
    const pv = page.exists() ? (page.data() || {}) : {};
    await setDoc(ref, Object.assign(_metaOf(html),
                 { shareKey: pv.shareKey || '', updatedAt: pv.updatedAt || serverTimestamp() }),
                 { merge: true });
    return true;
  }

  // One pass per account, recorded on users/{uid}: build the listing record
  // for every page uploaded before records existed. This is the one time the
  // whole pages collection is read.
  async function _migrateMeta(uid) {
    const snap = await getDocs(collection(db, 'users', uid, 'pages'));
    const writes = [];
    snap.forEach(d => {
      const v = d.data() || {};
      const m = _metaOf(v.html || '');
      if (!m.title) m.title = v.title || '';
      if (!m.tid) m.tid = v.tid || '';
      writes.push(setDoc(doc(db, 'users', uid, 'pagemeta', d.id),
        Object.assign(m, { shareKey: v.shareKey || '', updatedAt: v.updatedAt || serverTimestamp() })));
    });
    await Promise.all(writes);
    await setDoc(doc(db, 'users', uid), { pagemetaV: META_V }, { merge: true });
  }

  async function _getPage(key) {
    const u = auth.currentUser;
    if (!u || !key) return null;
    const snap = await getDoc(doc(db, 'users', u.uid, 'pages', key));
    return snap.exists() ? (snap.data().html || null) : null;
  }

  async function _putPage(key, html, title) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    if (!key) throw new Error('no page key');
    const bytes = new TextEncoder().encode(html || '').length;
    if (bytes > MAX_PAGE_BYTES)
      throw new Error(Math.round(bytes / 1024) + ' KB exceeds the ' +
                      Math.round(MAX_PAGE_BYTES / 1024) + ' KB limit');
    // The title IS stored, deliberately, and only here. The opaque key keeps
    // the public URL from announcing its subject; this document is inside
    // users/{uid}, which the rules make readable to nobody but the owner. A
    // list you cannot read the names in is not a list you can use.
    await setDoc(doc(db, 'users', u.uid, 'pages', key),
                 { html, title: title || '', tid: _identityOf(html),
                   updatedAt: serverTimestamp() });
    // merge: shareKey belongs to the share flow, not to an upload.
    await setDoc(doc(db, 'users', u.uid, 'pagemeta', key),
                 Object.assign(_metaOf(html), { updatedAt: serverTimestamp() },
                               title ? { title } : {}),
                 { merge: true });
    return true;
  }

  async function _ensureTitle(key, title, tid) {
    const u = auth.currentUser;
    if (!u || !key) return false;
    const ref = doc(db, 'users', u.uid, 'pages', key);
    const snap = await getDoc(ref);
    if (!snap.exists()) return false;
    const have = snap.data() || {};
    const add = {};
    // Never overwrite what is already there — this heals old documents, it
    // does not get an opinion about current ones.
    if (title && !have.title) add.title = title;
    // The timeline id, which the homepage needs to point the chip's reports
    // button and notes lookup at the right course. Recovered from the page
    // because the listing never downloads it.
    if (tid && !have.tid) add.tid = tid;
    if (!Object.keys(add).length) return false;
    await setDoc(ref, add, { merge: true });
    return true;
  }

  async function _listPages() {
    const u = auth.currentUser;
    if (!u) return [];
    const acct = await getDoc(doc(db, 'users', u.uid));
    if (((acct.exists() && acct.data()) || {}).pagemetaV !== META_V) await _migrateMeta(u.uid);
    const snap = await getDocs(collection(db, 'users', u.uid, 'pagemeta'));
    const out = [];
    snap.forEach(d => {
      const v = d.data() || {};
      out.push({ key: d.id, title: v.title || '', heading: v.heading || '',
                 project: v.project || '', tid: v.tid || '',
                 units: Array.isArray(v.units) ? v.units : [],
                 search: Array.isArray(v.search) ? v.search : [],
                 shareKey: v.shareKey || '',
                 updatedAt: (v.updatedAt && v.updatedAt.seconds) || 0 });
    });
    out.sort((a, b) => (b.updatedAt - a.updatedAt) ||
                       String(a.title).localeCompare(String(b.title)));
    return out;
  }

  /* ── shares: a copy anyone with the link can read ────────────────────────
     shares/{key} is the one world-readable collection in Alto. `get` is
     allowed and `list` is not, so the 22-character key is the whole of the
     access control — see firestore.rules. ─────────────────────────────────── */

  // Every place a page records WHICH timeline it is. MUST stay identical to
  // ID_PATTERNS in alto/build/blocks.py — tests/test_share_links.py asserts it,
  // because two copies of this list quietly disagreeing would hand a share
  // some of the master's storage and look completely normal while doing it.
  const ID_PATTERNS = [
    ["course_id_lit", "courseId:'{tid}'"],
    ["course_id_var", "var COURSE_ID = '{tid}';"],
    ["doc_save_key", "alto-doc-{tid}"],
    ["hl_key", "alto-hl-{tid}"],
    ["rp_key", "alto-rp-{tid}"]
  ];

  // A srcdoc iframe inherits this origin, so a share that kept the master's id
  // would write to the master's localStorage keys and, for a signed-in reader,
  // the master's users/{uid}/tl/{tid} document. Re-stamp it first, always.
  function _identityOf(html) {
    const m = /var COURSE_ID = '([^']*)';/.exec(html || '');
    return m ? m[1] : '';
  }

  function _reidentify(html, shareKey) {
    const m = /var COURSE_ID = '([^']*)';/.exec(html || '');
    if (!m) throw new Error('not an Alto timeline page');
    const oldId = m[1], newId = 's-' + shareKey;
    if (oldId === newId) return html;
    let out = html;
    for (const [, tmpl] of ID_PATTERNS)
      out = out.split(tmpl.replace('{tid}', oldId))
               .join(tmpl.replace('{tid}', newId));
    // A partial rewrite is worse than none: it shares SOME storage with the
    // master and gives no sign of it.
    for (const [name, tmpl] of ID_PATTERNS)
      if (out.includes(tmpl.replace('{tid}', oldId)))
        throw new Error('share still carries the original identity: ' + name);
    return out;
  }

  async function _getShare(key) {
    if (!key) return null;
    const snap = await getDoc(doc(db, 'shares', key));
    return snap.exists() ? snap.data() : null;
  }

  async function _putShare(key, data) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    if (!key) throw new Error('no share key');
    const bytes = new TextEncoder().encode((data && data.html) || '').length;
    if (bytes > MAX_PAGE_BYTES)
      throw new Error(Math.round(bytes / 1024) + ' KB exceeds the ' +
                      Math.round(MAX_PAGE_BYTES / 1024) + ' KB limit');
    // owner is what the rules check on every later update and delete, so it is
    // written here and never taken from the caller.
    await setDoc(doc(db, 'shares', key),
                 Object.assign({}, data, { owner: u.uid,
                                           updatedAt: serverTimestamp() }));
    return true;
  }

  async function _revokeShare(key) {
    const u = auth.currentUser;
    if (!u || !key) return false;
    await deleteDoc(doc(db, 'shares', key));
    return true;
  }

  // Same alphabet as the connector's _share_slug: 32 symbols with no look-alike
  // glyphs, 22 of them, so a key is unguessable and also dictatable over the
  // phone without an O/0 or l/1 argument.
  const KEY_ALPHABET = 'abcdefghijkmnpqrstuvwxyz23456789';
  function _mintKey() {
    const a = new Uint8Array(22);
    crypto.getRandomValues(a);
    let out = '';
    // 256 % 32 === 0, so the modulo is uniform — no rejection sampling needed.
    for (const b of a) out += KEY_ALPHABET[b % KEY_ALPHABET.length];
    return out;
  }

  // Create, or push the current master out to an existing link. One shared
  // link per timeline: the same URL goes to everyone, so "update the shared
  // copies" is one write and every recipient moves together.
  async function _sharePush(pageKey, title, mustBeNew) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    const ref = doc(db, 'users', u.uid, 'pages', pageKey);
    const snap = await getDoc(ref);
    if (!snap.exists()) throw new Error('nothing published here yet');
    const page = snap.data() || {};
    if (!page.html) throw new Error('nothing published here yet');
    const existing = page.shareKey || '';
    if (mustBeNew && existing) return { shareKey: existing, reused: true };
    const shareKey = existing || _mintKey();
    // Re-identify BEFORE writing. A share that kept the master's identity
    // would write a recipient's highlights into the owner's own records.
    const html = _reidentify(page.html, shareKey);
    await _putShare(shareKey, { html, title: title || page.title || '' });
    if (!existing) {
      await setDoc(ref, { shareKey }, { merge: true });
      await setDoc(doc(db, 'users', u.uid, 'pagemeta', pageKey), { shareKey }, { merge: true });
    }
    return { shareKey, reused: false };
  }

  async function _shareRevoke(pageKey) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    const ref = doc(db, 'users', u.uid, 'pages', pageKey);
    const snap = await getDoc(ref);
    const shareKey = snap.exists() ? ((snap.data() || {}).shareKey || '') : '';
    if (!shareKey) return false;
    // Delete the readable copy FIRST. If this throws, the owner still sees the
    // share on their homepage and can try again; clearing our end first would
    // leave a live public document nobody knew about any more.
    await _revokeShare(shareKey);
    await setDoc(ref, { shareKey: '' }, { merge: true });
    await setDoc(doc(db, 'users', u.uid, 'pagemeta', pageKey), { shareKey: '' }, { merge: true });
    return true;
  }

  // Colours and the timeline's own title only — never the html, and never its
  // text. A kept share is a
  // reference, and card titles copied here as search terms would outlive the
  // owner revoking it, in the one place they cannot see: someone else's
  // homepage search. So a kept share is found by its title, not its contents.
  function _sharedMetaOf(html) {
    const m = _metaOf(html);
    return { units: m.units, heading: m.heading, v: META_V };
  }

  async function _saveShare(key, title, html) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    if (!key) throw new Error('no share key');
    await setDoc(doc(db, 'users', u.uid, 'shared', key),
                 Object.assign({ key, title: title || '', savedAt: serverTimestamp() },
                               html ? _sharedMetaOf(html) : {}));
    return true;
  }

  async function _refreshShared(key, html) {
    const u = auth.currentUser;
    if (!u || !key || !html) return false;
    const ref = doc(db, 'users', u.uid, 'shared', key);
    const snap = await getDoc(ref);
    if (!snap.exists()) return false;
    await setDoc(ref, _sharedMetaOf(html), { merge: true });
    return true;
  }

  async function _listShared() {
    const u = auth.currentUser;
    if (!u) return [];
    const snap = await getDocs(collection(db, 'users', u.uid, 'shared'));
    const out = [];
    snap.forEach(d => {
      const v = d.data() || {};
      out.push({ key: d.id, title: v.title || '', heading: v.heading || '',
                 units: Array.isArray(v.units) ? v.units : [],
                 savedAt: (v.savedAt && v.savedAt.seconds) || 0 });
    });
    out.sort((a, b) => (b.savedAt - a.savedAt) ||
                       String(a.title).localeCompare(String(b.title)));
    return out;
  }

  async function _forgetShare(key) {
    const u = auth.currentUser;
    if (!u || !key) return false;
    await deleteDoc(doc(db, 'users', u.uid, 'shared', key));
    return true;
  }

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
  // Not awaited. It used to gate the auth listener on every page load — a
  // network round-trip before anything could learn who you are, on every
  // navigation, to finish a redirect sign-in that almost never happened.
  // onAuthStateChanged reports a completed redirect on its own.
  getRedirectResult(auth).catch(() => {});

  let unsubUser = null, unsubMain = null, unsubRp = null;

  onAuthStateChanged(auth, (user) => {
    cloud.user = user || null;
    // Pages draw from what this browser remembers until this is set; after it,
    // cloud.user is the truth, including a null that means signed out.
    cloud.known = true;
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
      // Cached listings and pages belong to the account that just left.
      try { localStorage.removeItem('alto-pages-cache-v1'); } catch (e) {}
      try { indexedDB.deleteDatabase('alto-pv-cache'); } catch (e) {}
      if (typeof window.renderAccount === 'function') { try { window.renderAccount(); } catch (e) {} }
    }
  });

  _resolveReady();
})();
