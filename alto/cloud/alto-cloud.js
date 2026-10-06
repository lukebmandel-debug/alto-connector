/* ────────────────────────────────────────────────────────────────────────────
   alto-cloud.js — v3 (per-timeline merge sync) for the Alto connector site.

   Derived from Terrarium-Alto's v2 with the SAME merge semantics (highlight
   union by id+quote-hash, tombstone ledger, longer-note wins; reports one doc
   per id with {deleted} tombstones, 25-newest cap; theme last-change-wins),
   generalized to many timelines per user:

     users/{uid}                      — { theme, homeSort, homeSortAt }   (account-wide)
     users/{uid}/tl/{tid}             — { highlights, hl_removed, hl_trash, hl_trash_purged, fw, study, updatedAt }
     users/{uid}/tl/{tid}/reports/{id}— { data, deleted, ts }
     users/{uid}/pages/{key}          — { html, updatedAt }
     users/{uid}/pagemeta/{key}       — { title, heading, project, units,
                                          search, shareKey, updatedAt,
                                          added, viewedAt }

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
  // `let`: the private shell loads this file before it knows which timeline it
  // is about to show (one shell serves them all), then names it with setTid().
  let TID = (scriptEl && scriptEl.dataset && scriptEl.dataset.tid)
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
    // Tell the sync layer which timeline the page now on screen is. Without it a
    // page shown by the private shell has no id and syncs nothing: highlights and
    // notes stayed on the device that made them.
    setTid:  (tid) => {
      if (!configured) return false;
      return ready.then(() => _setTid(tid));
    },
    /* Manual edit mode (alto/build/manual_edit.py): the owner's edits to one
       timeline, one document beside the notes — users/{uid}/edits/{tid},
       {data: JSON text, updatedAt}. The connector folds them into the draft
       (alto/edits.py) and marks them done. Nothing else reads or writes it. */
    getEdits: async (tid) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _getEdits(tid);
    },
    putEdits: async (tid, obj) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _putEdits(tid, obj);
    },
    watchEdits: (tid, cb) => {
      if (!configured) return () => {};
      let stop = null, off = false;
      ready.then(() => { if (!off) stop = _watchEdits(tid, cb); });
      return () => { off = true; try { stop && stop(); } catch (e) {} };
    },
    // Private timelines: the page itself lives in Firestore under the owner's
    // uid, so the rules decide who may read it. `ready` never resolves when the
    // publisher has no Firebase project, hence the check before the await.
    /* A timeline started on the homepage, without Claude (alto/build/starter.py):
       its draft where the connector keeps drafts (users/{uid}/alto_projects,
       alto_timelines — the same {data: JSON text} documents store/cloud.py
       writes), and its private page, made from the site's starter. */
    createTimeline: async (o) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _createTimeline(o || {});
    },
    cleanTitle: (s) => _cleanTitle(s),
    moveTimeline: async (key, tid, project) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _moveTimeline(key, tid, project);
    },
    binTimeline: async (key) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _binTimeline(key);
    },
    restoreTimeline: async (key) => {
      if (!configured) throw new Error('sync not configured');
      await ready; return _restoreTimeline(key);
    },
    purgeExpired: async () => {
      if (!configured) return 0;
      await ready; return _purgeExpired();
    },
    binDays: 30,
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
    // The owner opened this private timeline: stamp its listing record, which
    // is what the homepage's "recently viewed" order sorts by.
    markViewed: async (key) => {
      if (!configured) return false;
      await ready; return _markViewed(key);
    },
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
           onSnapshot, serverTimestamp, Bytes }] =
    await Promise.all([
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-app.js`),
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-auth.js`),
      import(`https://www.gstatic.com/firebasejs/${V}/firebase-firestore.js`),
    ]);

  const app  = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db   = getFirestore(app);
  try { await setPersistence(auth, browserLocalPersistence); } catch (e) {}

  let HL_KEY = TID ? `alto-hl-${TID}` : null;
  let RP_KEY = TID ? `alto-rp-${TID}` : null;
  let TR_KEY = TID ? `alto-hl-${TID}-trash` : null;   // deleted notes/highlights (the trash)
  let FW_KEY = TID ? `alto-hl-${TID}-fw` : null;      // the Freewrite document: {html, mod}
  let ST_KEY = TID ? `alto-hl-${TID}-st` : null;      // flash-card marks and quiz scores (study.py)
  const TH_KEY = 'alto-theme-v1';
  const SORT_KEY = 'alto-home-sort-v1';       // the homepage's project order
  let META_KEY = TID ? `alto-cloud-meta-v3-${TID}` : 'alto-cloud-meta-v3';
  const RP_CAP = 25, TOMB_CAP = 800, TRASH_CAP = 200;

  // The browser's own setter, kept before the prototype is patched below. origSet
  // writes localStorage (this layer's own keys); the patch itself must write
  // whichever Storage it was called on — sessionStorage included.
  const nativeSet = Storage.prototype.setItem;
  const origSet = (k, v) => nativeSet.call(localStorage, k, v);
  const origGet = localStorage.getItem.bind(localStorage);

  const loadMeta = () => { try { return JSON.parse(origGet(META_KEY) || '{}'); } catch (e) { return {}; } };
  let meta = loadMeta();
  const saveMeta = () => { try { origSet(META_KEY, JSON.stringify(meta)); } catch (e) {} };

  const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); };
  const parseArr = s => { try { const a = JSON.parse(s || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } };
  const hlKey = h => ((h && h.id) || 'x') + '§' + hash(String((h && h.quote) || ''));
  const rpTs = id => { const n = parseInt(String(id || '').replace(/^r/, ''), 10); return isNaN(n) ? 0 : n; };

  // Which copy of one highlight to keep. A highlight carries `mod`, when its note
  // was last edited: the later edit wins, so shortening or clearing a note sticks
  // (the old rule — the longer note wins — put a deleted sentence straight back).
  // Copies with no `mod` (made before it existed) fall back to the longer note.
  function newerNote(local, remote) {
    const lm = Number(local.mod) || 0, rm = Number(remote.mod) || 0;
    if (lm || rm) return rm > lm;
    return String(remote.note || '').length > String(local.note || '').length;
  }

  function mergeHl(localArr, remoteArr, removed) {
    const out = [], seen = new Set();
    const rmap = new Map(remoteArr.map(h => [hlKey(h), h]));
    for (const h of localArr) {
      const k = hlKey(h);
      if (removed.has(k) || seen.has(k)) continue;
      seen.add(k);
      const r = rmap.get(k);
      out.push(r && newerNote(h, r) ? r : h);
    }
    for (const h of remoteArr) {
      const k = hlKey(h);
      if (removed.has(k) || seen.has(k)) continue;
      seen.add(k); out.push(h);
    }
    return out;
  }

  // The trash: union of both sides by id+quote, minus anything permanently deleted
  // (purged ledger), oldest first, newest TRASH_CAP kept.
  function mergeTrash(localArr, remoteArr, purged) {
    const byKey = new Map();
    for (const h of [...remoteArr, ...localArr]) {
      const k = hlKey(h);
      if (!purged.has(k) && !byKey.has(k)) byKey.set(k, h);
    }
    return [...byKey.values()].sort((a, b) => (a.del || 0) - (b.del || 0)).slice(-TRASH_CAP);
  }

  // Freewrite: one document per timeline, {html, mod}. The later edit wins whole.
  const parseFw = s => {
    try { const o = JSON.parse(s || 'null');
      return o && typeof o === 'object' ? { html: String(o.html || ''), mod: Number(o.mod) || 0 } : null;
    } catch (e) { return null; }
  };

  // Study progress (study.py): {v:1, s:{<section key>:{m, k:{<card id>:[state,t]},
  // b:{s,n,t} best, l:{s,n,t,bl} last, a:attempts}}}. Merged field by field: a card's
  // mark by its own time (newest wins; a cleared mark is state 0, so it stays cleared),
  // the best score by its share right (a tie keeps the earlier), the last attempt by
  // time, the attempt count by size. Keys are written sorted so equal data is equal text.
  const parseSt = s => {
    try { const o = JSON.parse(s || 'null'); return o && o.s && typeof o.s === 'object' ? o : { v: 1, s: {} }; }
    catch (e) { return { v: 1, s: {} }; }
  };
  const sortedObj = o => { const r = {}; Object.keys(o).sort().forEach(k => { r[k] = o[k]; }); return r; };
  function mergeStudy(a, b) {
    const out = { v: 1, s: {} };
    const keys = new Set([...Object.keys(a.s || {}), ...Object.keys(b.s || {})]);
    const share = r => (r && r.n ? r.s / r.n : -1);
    for (const key of [...keys].sort()) {
      const x = (a.s || {})[key] || {}, y = (b.s || {})[key] || {}, r = {};
      const k = {};
      for (const src of [x.k || {}, y.k || {}])
        for (const id of Object.keys(src)) {
          const m = src[id];
          if (Array.isArray(m) && (!k[id] || (Number(m[1]) || 0) > (Number(k[id][1]) || 0))) k[id] = m;
        }
      if (Object.keys(k).length) r.k = sortedObj(k);
      if (x.b || y.b) r.b = share(y.b) > share(x.b) ? y.b : x.b;
      if (x.l || y.l) r.l = (Number(y.l && y.l.t) || 0) > (Number(x.l && x.l.t) || 0) ? y.l : (x.l || y.l);
      const at = Math.max(Number(x.a) || 0, Number(y.a) || 0);
      if (at) r.a = at;
      r.m = Math.max(Number(x.m) || 0, Number(y.m) || 0);
      out.s[key] = r;
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

      /* ---- homepage project order (account-wide; the newest choice wins) ----
         Kept locally as {v, t} (t = when it was chosen); the account document
         carries the same pair, so a choice made on one device reaches the
         rest, and an old choice never overwrites a newer one. */
      {
        let ls = null;
        try { ls = JSON.parse(origGet(SORT_KEY) || 'null'); } catch (e) {}
        const rs = remoteUser && remoteUser.homeSort
          ? { v: String(remoteUser.homeSort), t: Number(remoteUser.homeSortAt) || 0 } : null;
        if (ls && ls.v && (!rs || (Number(ls.t) || 0) > rs.t)) {
          await setDoc(userRef, { homeSort: ls.v, homeSortAt: Number(ls.t) || Date.now(),
                                  updatedAt: serverTimestamp() }, { merge: true });
        } else if (rs && (!ls || rs.t > (Number(ls.t) || 0))) {
          origSet(SORT_KEY, JSON.stringify(rs));
          try { window.dispatchEvent(new Event('alto-home-sort')); } catch (e) {}
        }
      }

      if (TID) {
        const mainRef = doc(db, 'users', uid, 'tl', TID);

        /* ---- highlights ---- */
        // A note still being typed (the "+" placeholder, flagged `pending`) stays
        // on this device until it is saved: other devices never see an empty note
        // appear and vanish.
        const localAll = parseArr(origGet(HL_KEY));
        const pendingLocal = localAll.filter(h => h && h.pending);
        const localArr = localAll.filter(h => !(h && h.pending));
        const localStr = JSON.stringify(localArr);
        const remoteArr = parseArr(remoteMain ? remoteMain.highlights : '[]');
        const removed = new Set(Array.isArray(remoteMain && remoteMain.hl_removed) ? remoteMain.hl_removed : []);
        const prevArr = parseArr(meta.lastHl);
        const nowKeys = new Set(localArr.map(hlKey));
        for (const h of prevArr) { const k = hlKey(h); if (!nowKeys.has(k)) removed.add(k); }
        const merged = mergeHl(localArr, remoteArr, removed);
        const mergedStr = JSON.stringify(merged);
        const tombs = [...removed].slice(-TOMB_CAP);

        if (mergedStr !== localStr) {
          const keep = merged.concat(pendingLocal);
          applyHighlightsLocally(keep, JSON.stringify(keep));
        } else if (!pendingLocal.length) origSet(HL_KEY, mergedStr);

        const remoteTombsStr = JSON.stringify(Array.isArray(remoteMain && remoteMain.hl_removed) ? remoteMain.hl_removed : []);
        const needMainPush = !remoteMain
          || mergedStr !== (remoteMain.highlights || '[]')
          || JSON.stringify(tombs) !== remoteTombsStr;
        if (needMainPush) {
          await setDoc(mainRef, { highlights: mergedStr, hl_removed: tombs,
                                  updatedAt: serverTimestamp() }, { merge: true });
        }
        meta.lastHl = mergedStr;

        /* ---- trash (deleted highlights/notes; Undo + the Deleted list) ---- */
        const localTr = parseArr(origGet(TR_KEY));
        const remoteTr = parseArr(remoteMain ? remoteMain.hl_trash : '[]');
        const remotePurged = Array.isArray(remoteMain && remoteMain.hl_trash_purged) ? remoteMain.hl_trash_purged : [];
        const purged = new Set(remotePurged);
        const nowTrKeys = new Set(localTr.map(hlKey));
        for (const h of parseArr(meta.lastTr)) { const k = hlKey(h); if (!nowTrKeys.has(k)) purged.add(k); }
        const mergedTr = mergeTrash(localTr, remoteTr, purged);
        const mergedTrStr = JSON.stringify(mergedTr);
        const purgedArr = [...purged].slice(-TOMB_CAP);
        if (mergedTrStr !== JSON.stringify(localTr)) {
          origSet(TR_KEY, mergedTrStr);
          try { window.dispatchEvent(new Event('alto-trash-sync')); } catch (e) {}
        }
        if (mergedTrStr !== (remoteMain && remoteMain.hl_trash || '[]')
            || JSON.stringify(purgedArr) !== JSON.stringify(remotePurged)) {
          await setDoc(mainRef, { hl_trash: mergedTrStr, hl_trash_purged: purgedArr,
                                  updatedAt: serverTimestamp() }, { merge: true });
        }
        meta.lastTr = mergedTrStr;

        /* ---- freewrite (one rich-text document; the later edit wins) ---- */
        {
          const lf = parseFw(origGet(FW_KEY));
          const rf = remoteMain && remoteMain.fw ? parseFw(JSON.stringify(remoteMain.fw)) : null;
          if (rf && rf.mod && (!lf || rf.mod > lf.mod)) {
            origSet(FW_KEY, JSON.stringify(rf));
            try { window.dispatchEvent(new Event('alto-fw-sync')); } catch (e) {}
          } else if (lf && lf.mod && (!rf || lf.mod > rf.mod)) {
            await setDoc(mainRef, { fw: { html: lf.html, mod: lf.mod }, updatedAt: serverTimestamp() },
                         { merge: true });
          }
        }

        /* ---- study progress (flash-card marks, quiz scores) ---- */
        {
          const ls = parseSt(origGet(ST_KEY));
          const rs = parseSt(remoteMain && typeof remoteMain.study === 'string' ? remoteMain.study : '');
          const ms = JSON.stringify(mergeStudy(ls, rs));
          const empty = !Object.keys(JSON.parse(ms).s).length;
          if (!empty && ms !== JSON.stringify(ls)) {
            origSet(ST_KEY, ms);
            try { window.dispatchEvent(new Event('alto-study-sync')); } catch (e) {}
          }
          if (!empty && ms !== (remoteMain && remoteMain.study || '')) {
            await setDoc(mainRef, { study: ms, updatedAt: serverTimestamp() }, { merge: true });
          }
        }

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

  // On the prototype, not the localStorage object: Safari ignores an override of
  // the method on the object itself, so local changes never triggered a sync there.
  Storage.prototype.setItem = function (k, v) {
    nativeSet.call(this, k, v);
    if (this === localStorage && cloud.user && (k === HL_KEY || k === TR_KEY || k === FW_KEY || k === ST_KEY || k === RP_KEY || k === TH_KEY || k === SORT_KEY)) requestSync('local-change');
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

  /* A page is stored gzipped, as Bytes in `z` with `enc: 'gzip'` — about a
     quarter of its html — and the cap applies to those stored bytes. Everything
     outside this file still sees html: _packPage/_unpackPage are the only two
     places the stored form exists. A document written before this (a plain
     `html` string) still reads, and the next upload replaces it. A browser
     with no CompressionStream (Safari before 16.4) still uploads plain html,
     up to the same cap. See private_shell.py. */
  const PAGE_ENC = 'gzip';

  async function _pipe(bytes, Stream) {
    const out = new Blob([bytes]).stream().pipeThrough(new Stream(PAGE_ENC));
    return new Uint8Array(await new Response(out).arrayBuffer());
  }

  // → { fields, bytes }: the fields to write in place of `html`, and what they
  // cost against MAX_PAGE_BYTES.
  async function _packPage(html) {
    const raw = new TextEncoder().encode(html || '');
    if (typeof CompressionStream !== 'function')
      return { fields: { html: html || '' }, bytes: raw.length, raw: raw.length };
    const z = await _pipe(raw, CompressionStream);
    return { fields: { z: Bytes.fromUint8Array(z), enc: PAGE_ENC },
             bytes: z.length, raw: raw.length };
  }

  async function _unpackPage(data) {
    const v = data || {};
    if (!v.z) return v.html || null;
    if (v.enc !== PAGE_ENC) throw new Error('page stored as unknown encoding ' + v.enc);
    if (typeof DecompressionStream !== 'function')
      throw new Error('this browser is too old to open this page; please update it');
    const z = typeof v.z.toUint8Array === 'function' ? v.z.toUint8Array() : v.z;
    return new TextDecoder().decode(await _pipe(z, DecompressionStream));
  }

  function _tooLarge(p) {
    return new Error(Math.round(p.bytes / 1024) + ' KB' +
                     (p.fields.z ? ' compressed (' + Math.round(p.raw / 1024) + ' KB of html)' : '') +
                     ' exceeds the ' + Math.round(MAX_PAGE_BYTES / 1024) + ' KB limit');
  }

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

  async function _markViewed(key) {
    const u = auth.currentUser;
    if (!u || !key) return false;
    try {
      await setDoc(doc(db, 'users', u.uid, 'pagemeta', key),
                   { viewedAt: serverTimestamp() }, { merge: true });
      return true;
    } catch (e) { return false; }
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
    for (const d of snap.docs) {
      const v = d.data() || {};
      const m = _metaOf(await _unpackPage(v).catch(() => '') || '');
      if (!m.title) m.title = v.title || '';
      if (!m.tid) m.tid = v.tid || '';
      writes.push(setDoc(doc(db, 'users', uid, 'pagemeta', d.id),
        Object.assign(m, { shareKey: v.shareKey || '', updatedAt: v.updatedAt || serverTimestamp() })));
    }
    await Promise.all(writes);
    await setDoc(doc(db, 'users', uid), { pagemetaV: META_V }, { merge: true });
  }

  async function _getPage(key) {
    const u = auth.currentUser;
    if (!u || !key) return null;
    const snap = await getDoc(doc(db, 'users', u.uid, 'pages', key));
    return snap.exists() ? _unpackPage(snap.data()) : null;
  }

  async function _putPage(key, html, title) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    if (!key) throw new Error('no page key');
    const packed = await _packPage(html);
    if (packed.bytes > MAX_PAGE_BYTES) throw _tooLarge(packed);
    // The title IS stored, deliberately, and only here. The opaque key keeps
    // the public URL from announcing its subject; this document is inside
    // users/{uid}, which the rules make readable to nobody but the owner. A
    // list you cannot read the names in is not a list you can use.
    await setDoc(doc(db, 'users', u.uid, 'pages', key),
                 Object.assign({ title: title || '', tid: _identityOf(html),
                                 updatedAt: serverTimestamp() }, packed.fields));
    // merge: shareKey belongs to the share flow, not to an upload.
    await setDoc(doc(db, 'users', u.uid, 'pagemeta', key),
                 Object.assign(_metaOf(html), { updatedAt: serverTimestamp() },
                               title ? { title } : {}),
                 { merge: true });
    return true;
  }

  /* ── starting a timeline here ─────────────────────────────────────────── */
  // The starter page names its title in page text, JS strings and JSON; with
  // these few characters swapped for look-alikes one replacement is right in
  // all of them (alto/build/starter.py).
  function _cleanTitle(s) {
    return String(s || '').replace(/[\u0000-\u001f\u2028\u2029]/g, ' ')
      .replace(/(^|[\s(\[{\u2014\u2013-])"/g, '$1\u201c').replace(/"/g, '\u201d')
      .replace(/(^|[\s(\[{\u2014\u2013-])'/g, '$1\u2018').replace(/['`]/g, '\u2019').replace(/&/g, ' and ')
      .replace(/[<>\\]/g, '').replace(/\$\{/g, '$ {').replace(/\s+/g, ' ').trim().slice(0, 120);
  }
  function _slug(s, pre) {
    let x = String(s || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (x && !/^[a-z]/.test(x)) x = pre + x;
    return x.slice(0, 40).replace(/-+$/, '') || pre + 'new';
  }
  const _ALPHA = 'abcdefghijkmnpqrstuvwxyz23456789';
  function _pageKey() {
    const r = new Uint8Array(22); crypto.getRandomValues(r);
    return Array.from(r, b => _ALPHA[b % 32]).join('');
  }
  function _attr(s) { return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  async function _freeId(uid, coll, base) {
    for (let i = 1; i < 200; i++) {
      const id = i === 1 ? base : (base.slice(0, 44) + '-' + i);
      if (!(await getDoc(doc(db, 'users', uid, coll, id))).exists()) return id;
    }
    throw new Error('no free id');
  }
  async function _createTimeline(o) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    const kind = (o.kind === 'timeline' || o.kind === 'lanes') ? o.kind : 'outline';
    const title = _cleanTitle(o.title) || 'Untitled timeline';
    const pname = String(o.project || '').replace(/\s+/g, ' ').trim().slice(0, 120) || title;
    const [hr, jr] = await Promise.all([fetch('/new/' + kind + '.html', { cache: 'no-cache' }),
                                        fetch('/new/' + kind + '.json', { cache: 'no-cache' })]);
    if (!hr.ok || !jr.ok) throw new Error('This site has no starter yet — it comes with the next update.');
    const starter = await hr.text(), dr = await jr.json();
    const now = new Date().toISOString();
    // the project: one of the account's by name, else a new one
    let pid = null;
    (await getDocs(collection(db, 'users', u.uid, 'alto_projects'))).forEach(d => {
      let v = null; try { v = JSON.parse((d.data() || {}).data || 'null'); } catch (e) {}
      if (!pid && v && String(v.name || '').trim().toLowerCase() === pname.toLowerCase()) pid = d.id;
    });
    if (!pid) {
      pid = await _freeId(u.uid, 'alto_projects', _slug(pname, 'p-'));
      await setDoc(doc(db, 'users', u.uid, 'alto_projects', pid), {
        data: JSON.stringify({ project_id: pid, name: pname, purpose: '', kind: 'studying', created: now }),
        created: now });
    }
    const tid = await _freeId(u.uid, 'alto_timelines', _slug(title, 't-'));
    const key = _pageKey();
    const html = starter.split('subject=Zqtitleqz').join('subject=' + encodeURIComponent(title))
      .split('Zqtitleqz').join(title).split('zqtidqz').join(tid).split('Zqlabelqz').join(_attr(pname));
    const brief = Object.assign({}, dr.brief, { title: title, timeline_id: tid });
    // The owner writes it all in the page: their own words are the material.
    const tdoc = { timeline_id: tid, project_id: pid, brief: brief,
                   consent: { granted: true, at: now, manual: true,
                              sources: [{ name: 'Written by the owner in the page', kind: 'own-writing' }] },
                   status: 'published', visibility: 'private-web', private_key: key,
                   created: now, started: 'homepage' };
    await Promise.all((dr.nodes || []).map((n, i) => setDoc(
      doc(db, 'users', u.uid, 'alto_timelines', tid, 'nodes', n.id),
      { data: JSON.stringify(Object.assign({}, n, { _seq: i + 1 })), _seq: i + 1 })));
    await setDoc(doc(db, 'users', u.uid, 'alto_timelines', tid, 'meta', 'connections'), { data: '[]' });
    await setDoc(doc(db, 'users', u.uid, 'alto_timelines', tid), { data: JSON.stringify(tdoc), created: now });
    await _putPage(key, html, pname);
    await setDoc(doc(db, 'users', u.uid, 'pagemeta', key), { added: Math.floor(Date.now() / 1000) }, { merge: true });
    return { key: key, tid: tid, pid: pid, url: '/pv/' + key + '/' };
  }

  /* ── moving a timeline to another project, and Recently deleted ─────────
     A project is a name the homepage groups by: the page's alto-label, its
     listing record's `project`, and — where the connector keeps drafts in the
     account — the draft's project_id. A move rewrites all three, so the next
     build from the draft keeps it where it was put.

     Deleting puts a timeline in Recently deleted (pagemeta.binned, epoch
     seconds) and stops its share link. For BIN_DAYS it can be restored; after
     that the homepage removes it for good (_purgeExpired) — page, listing
     record, draft, notes and edits. Nothing is ever removed at once. */
  const BIN_DAYS = 30;
  function _uidOrThrow() { const u = auth.currentUser; if (!u) throw new Error('not signed in'); return u.uid; }
  async function _projectId(uid, pname) {
    let pid = null;
    (await getDocs(collection(db, 'users', uid, 'alto_projects'))).forEach(d => {
      let v = null; try { v = JSON.parse((d.data() || {}).data || 'null'); } catch (e) {}
      if (!pid && v && String(v.name || '').trim().toLowerCase() === pname.toLowerCase()) pid = d.id;
    });
    if (pid) return pid;
    const now = new Date().toISOString();
    pid = await _freeId(uid, 'alto_projects', _slug(pname, 'p-'));
    await setDoc(doc(db, 'users', uid, 'alto_projects', pid), {
      data: JSON.stringify({ project_id: pid, name: pname, purpose: '', kind: 'studying', created: now }),
      created: now });
    return pid;
  }
  function _cleanProject(s) { return String(s || '').replace(/[\u0000-\u001f\u2028\u2029]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120); }
  async function _moveTimeline(key, tid, project) {
    const uid = _uidOrThrow();
    const pname = _cleanProject(project);
    if (!pname) throw new Error('no project name');
    // the draft, when the connector keeps it in the account
    if (tid && /^[a-z0-9][a-z0-9-]{0,63}$/.test(tid)) {
      const tref = doc(db, 'users', uid, 'alto_timelines', tid);
      const ts = await getDoc(tref);
      if (ts.exists()) {
        let t = null; try { t = JSON.parse((ts.data() || {}).data || 'null'); } catch (e) {}
        if (t) {
          t.project_id = await _projectId(uid, pname);
          await setDoc(tref, { data: JSON.stringify(t) }, { merge: true });
        }
      }
    }
    // the page names its project in one meta tag; rewriting it keeps the
    // listing record (read back from the page) in step
    const pref = doc(db, 'users', uid, 'pages', key);
    const ps = await getDoc(pref);
    if (ps.exists()) {
      const html = await _unpackPage(ps.data());
      const share = (ps.data() || {}).shareKey || '';
      if (html) {
        const out = html.replace(/(<meta name="alto-label" content=")[^"]*(")/i, '$1' + _attr(pname) + '$2');
        await _putPage(key, out, pname);
        // _putPage writes the page afresh; its share link is the share flow's
        if (share) await setDoc(pref, { shareKey: share }, { merge: true });
      }
    }
    await setDoc(doc(db, 'users', uid, 'pagemeta', key), { project: pname, title: pname }, { merge: true });
    return { project: pname };
  }
  async function _binTimeline(key) {
    const uid = _uidOrThrow();
    // the share link stops first: a deleted timeline is read by nobody else
    try { await _shareRevoke(key); } catch (e) {}
    await setDoc(doc(db, 'users', uid, 'pagemeta', key), { binned: Math.floor(Date.now() / 1000) }, { merge: true });
    return { binned: true, days: BIN_DAYS };
  }
  async function _restoreTimeline(key) {
    const uid = _uidOrThrow();
    await setDoc(doc(db, 'users', uid, 'pagemeta', key), { binned: 0 }, { merge: true });
    return { restored: true };
  }
  async function _deleteAll(ref) {
    await Promise.all((await getDocs(ref)).docs.map(d => deleteDoc(d.ref)));
  }
  async function _purgeOne(uid, key, tid) {
    if (tid && /^[a-z0-9][a-z0-9-]{0,63}$/.test(tid)) {
      await _deleteAll(collection(db, 'users', uid, 'alto_timelines', tid, 'nodes'));
      await deleteDoc(doc(db, 'users', uid, 'alto_timelines', tid, 'meta', 'connections'));
      await deleteDoc(doc(db, 'users', uid, 'alto_timelines', tid));
      await _deleteAll(collection(db, 'users', uid, 'tl', tid, 'reports'));
      await deleteDoc(doc(db, 'users', uid, 'tl', tid));
      await deleteDoc(doc(db, 'users', uid, 'edits', tid));
    }
    await deleteDoc(doc(db, 'users', uid, 'alto_snapshots', key));
    await deleteDoc(doc(db, 'users', uid, 'pages', key));
    // the listing record goes last: while it is there the homepage still
    // knows to finish the job
    await deleteDoc(doc(db, 'users', uid, 'pagemeta', key));
  }
  // Only what has been in Recently deleted longer than BIN_DAYS, each checked
  // again against the account just before it goes.
  async function _purgeExpired() {
    const uid = _uidOrThrow();
    const cut = Math.floor(Date.now() / 1000) - BIN_DAYS * 86400;
    const snap = await getDocs(collection(db, 'users', uid, 'pagemeta'));
    let n = 0;
    for (const d of snap.docs) {
      const v = d.data() || {};
      const b = Number(v.binned) || 0;
      if (!b || b > cut) continue;
      const again = await getDoc(d.ref);
      const bb = again.exists() ? Number((again.data() || {}).binned) || 0 : 0;
      if (!bb || bb > cut) continue;
      await _purgeOne(uid, d.id, v.tid || '');
      n++;
    }
    return n;
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
                 added: Number(v.added) || 0,
                 binned: Number(v.binned) || 0,
                 viewedAt: (v.viewedAt && v.viewedAt.seconds) || 0,
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

  const LOCAL_BLOCK = /<script id="alto-local-src">[\s\S]*?<\/script>/g;
  const LOCAL_EMPTY = '<script id="alto-local-src">window._ALTO_LOCAL={};</script>';
  function _reidentify(html, shareKey) {
    const m = /var COURSE_ID = '([^']*)';/.exec(html || '');
    if (!m) throw new Error('not an Alto timeline page');
    const oldId = m[1], newId = 's-' + shareKey;
    // The owner's own file paths (reidentify.LOCAL_BLOCK) never leave with a
    // share: other people's computers do not have those files.
    html = html.replace(LOCAL_BLOCK, LOCAL_EMPTY);
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
    if (!snap.exists()) return null;
    // The share shell reads d.html; hand it html whichever way it is stored.
    const d = Object.assign({}, snap.data());
    if (d.z) { d.html = await _unpackPage(d); delete d.z; delete d.enc; }
    return d;
  }

  async function _putShare(key, data) {
    const u = auth.currentUser;
    if (!u) throw new Error('not signed in');
    if (!key) throw new Error('no share key');
    // A timeline share carries a page, packed like a private page; a project
    // share carries only its items.
    let body = Object.assign({}, data);
    if (body.html) {
      const packed = await _packPage(body.html);
      if (packed.bytes > MAX_PAGE_BYTES) throw _tooLarge(packed);
      delete body.html;
      body = Object.assign(body, packed.fields);
    }
    // owner is what the rules check on every later update and delete, so it is
    // written here and never taken from the caller.
    await setDoc(doc(db, 'shares', key),
                 Object.assign(body, { owner: u.uid,
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
    const master = await _unpackPage(page);
    if (!master) throw new Error('nothing published here yet');
    const existing = page.shareKey || '';
    if (mustBeNew && existing) return { shareKey: existing, reused: true };
    const shareKey = existing || _mintKey();
    // Re-identify BEFORE writing. A share that kept the master's identity
    // would write a recipient's highlights into the owner's own records.
    const html = _reidentify(master, shareKey);
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

  // Listeners on this timeline's cloud record; called at sign-in, and again by
  // setTid() when the shell learns the timeline after sign-in.
  function subscribeTl(user) {
    for (const u of [unsubMain, unsubRp]) { try { u && u(); } catch (e) {} }
    unsubMain = unsubRp = null;
    remoteMain = undefined; remoteReports = undefined; remoteTombs = new Set();
    if (!user || !TID) return;
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

  function _editsRef(tid) {
    if (!cloud.user) throw new Error('not signed in');
    tid = String(tid || '');
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(tid)) throw new Error('bad timeline id');
    return doc(db, 'users', cloud.user.uid, 'edits', tid);
  }
  const _decodeEdits = (snap) => {
    if (!snap || !snap.exists()) return null;
    try { const d = snap.data() || {}; return d.data ? JSON.parse(d.data) : null; } catch (e) { return null; }
  };
  async function _getEdits(tid) { return _decodeEdits(await getDoc(_editsRef(tid))); }
  async function _putEdits(tid, obj) {
    await setDoc(_editsRef(tid), { data: JSON.stringify(obj || {}), updatedAt: serverTimestamp() });
    return true;
  }
  function _watchEdits(tid, cb) {
    if (!cloud.user) return () => {};
    return onSnapshot(_editsRef(tid), (snap) => { try { cb(_decodeEdits(snap)); } catch (e) {} },
                      () => {});
  }

  function _setTid(tid) {
    tid = String(tid || '');
    if (!tid || tid === TID) return false;
    TID = tid; cloud.tid = tid;
    HL_KEY = `alto-hl-${tid}`; RP_KEY = `alto-rp-${tid}`; TR_KEY = `alto-hl-${tid}-trash`; FW_KEY = `alto-hl-${tid}-fw`; ST_KEY = `alto-hl-${tid}-st`;
    META_KEY = `alto-cloud-meta-v3-${tid}`;
    meta = loadMeta();
    if (cloud.user) subscribeTl(cloud.user);
    return true;
  }

  onAuthStateChanged(auth, (user) => {
    cloud.user = user || null;
    // Pages draw from what this browser remembers until this is set; after it,
    // cloud.user is the truth, including a null that means signed out.
    cloud.known = true;
    try { window.dispatchEvent(new CustomEvent('alto-auth')); } catch (e) {}
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

      subscribeTl(user);
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
