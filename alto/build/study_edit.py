"""Manual edit mode for flash cards and quizzes (study.py).

Spliced into MANUAL_JS / MANUAL_CSS by manual_edit.manual_edit — it uses that
script's own `field`, `change`, `changes`, `undo`, `toast`, `rid`, `page` — so
the pieces below are plain strings with markers, not a script of their own:

  STUDY_EDIT_FIELD     the field `sd|<study key>|study`: a section's whole list
                       (cards or questions), one change, one step of undo
  STUDY_EDIT_DECORATE  the "✎ Edit quiz" / "✎ Edit cards" button on each one
  STUDY_EDIT_JS        the editor, the starter a new section gets, and the
                       prompt that opens Claude to write one from the notes
  STUDY_EDIT_CSS       the editor's look

Desktop only, like every structural edit. The editor works on a copy and saves
once (Save), so a whole sitting at it is a single ⌘Z; Cancel on a section just
made takes the section away again.
"""

STUDY_EDIT_FIELD = r"""    if(kind === 'sd' && p.length === 3 && p[2] === 'study'){
      var ST = window._ALTO_ST = window._ALTO_ST || {};
      if(NEWT.test(id)){
        // a section added here: its list is made with it
        if(!ST[id] && !newTreeSec(id)) return null;
        return {kind:'struct', sig:function(){ return 'new'; },
          get:function(){ return ST[id] ? JSON.parse(JSON.stringify(ST[id])) : null; },
          set:function(v){ var q = newTreeSec(id);
            if(v && v.n && v.n.length){ ST[id] = JSON.parse(JSON.stringify(v)); if(q) setSlot(q.s, id, true, 'ast'); }
            else { delete ST[id]; if(q) setSlot(q.s, id, false, 'ast'); } }};
      }
      if(!ST[id]) return null;
      return {kind:'struct', sig:function(){ return PRIS['sd|' + id]; },
        get:function(){ return JSON.parse(JSON.stringify(ST[id])); },
        set:function(v){ ST[id] = JSON.parse(JSON.stringify(v)); }};
    }
"""

STUDY_EDIT_DECORATE = r"""      if(structOK()) dc.querySelectorAll('.ast[data-ast-key]').forEach(function(bx){
        var key = bx.getAttribute('data-ast-key'), bar = bx.querySelector('.ast-bar'), S0 = (window._ALTO_ST || {})[key];
        if(!bar || !S0 || bar.querySelector('.aed-st') || !field('sd|' + key + '|study')) return;
        var eb = document.createElement('button'); eb.type = 'button'; eb.className = 'aed-st';
        eb.setAttribute('data-sk', key); eb.textContent = S0.k === 'q' ? '✎ Edit quiz' : '✎ Edit cards';
        eb.title = S0.k === 'q' ? 'Edit the questions, choices and answers' : 'Edit the cards';
        bar.appendChild(eb);
      });
"""

STUDY_EDIT_JS = r"""  /* ── flash cards and quizzes: the editor (study_edit.py) ─────────────────── */
  function studyStarter(kind){
    return kind === 'quiz' ? {k: 'q', lab: '', n: [{i: rid('q'), q: '', c: ['', ''], a: 0}]}
                           : {k: 'c', lab: '', sh: false, n: [{i: rid('c'), f: '', b: ''}]};
  }
  // The prompt that opens Claude: the page, the kind, and the rule (§0) — only the owner's own material.
  function studyPrompt(kind, key){
    var P = page(), dc = document.getElementById('detail-content'), nm = dc && dc.querySelector('.detail-name');
    var title = nm ? nm.textContent.trim() : '', what = kind === 'q' ? 'a quiz' : 'a set of flash cards';
    var shape = kind === 'q'
      ? 'a section {h: "Quiz", t: "", quiz: {questions: [{q, choices: [2-8 answers], answer: <index of the right choice, or a list of indexes for select-all-that-apply>, explain}]}}'
      : 'a section {h: "Flash cards", t: "", cards: {cards: [{front, back}]}}';
    return 'Please write ' + what + ' for the page “' + title + '”' + (P ? ' (' + P.type + ' page, id: ' + P.id + ')' : '') +
      ' of my Alto timeline. Use ONLY my own material — what this timeline already holds and the notes and sources I have given you — never outside knowledge: ' +
      'every ' + (kind === 'q' ? 'question, choice, answer and explanation' : 'card') + ' must be grounded in my notes. ' +
      'Read the page first with get_timeline, then add ' + shape + ' to that page’s sections with add_nodes (keep its other sections), rebuild and republish. ' +
      'Ask me first if it would help to know how many ' + (kind === 'q' ? 'questions' : 'cards') + ' I want.';
  }
  function askClaudeStudy(kind, key){
    if(window._altoAskClaude) window._altoAskClaude(studyPrompt(kind, key)); else toast('Open Claude from the edit pill, then ask for it.');
  }
  var LETTERS = 'ABCDEFGH';
  function openStudyEditor(key, opts){
    opts = opts || {};
    var f = field('sd|' + key + '|study'); if(!f) return;
    var W = f.get(); if(!W) return;
    var isQ = W.k === 'q', noun = isQ ? 'quiz' : 'flash cards';
    var w = document.getElementById('aed-study');
    if(w) w.parentNode.removeChild(w);
    w = document.createElement('div'); w.id = 'aed-study'; document.body.appendChild(w);
    var box = document.createElement('div'); box.className = 'as-box'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); w.appendChild(box);
    function E(tag, cls, t){ var e = document.createElement(tag); if(cls) e.className = cls; if(t != null) e.textContent = t; return e; }
    // Escape closes the editor, not the page behind it: the engine's own handler is set aside meanwhile (as for a field being edited)
    function close(cancelled){ if(w.parentNode) w.parentNode.removeChild(w); window.removeEventListener('keydown', onKey, true);
      if(window._unifiedEscape) window.addEventListener('keydown', window._unifiedEscape, true);
      if(cancelled && opts.fresh){ var o = STORE.ops['sd|' + key + '|study']; if(o && !o.done) undo(); } }
    function onKey(e){ if(e.key === 'Escape'){ e.preventDefault(); e.stopImmediatePropagation(); close(true); } }
    if(window._unifiedEscape) window.removeEventListener('keydown', window._unifiedEscape, true);
    window.addEventListener('keydown', onKey, true);
    w.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    w.addEventListener('click', function(e){ e.stopPropagation(); });
    w.addEventListener('keydown', function(e){ e.stopPropagation(); });
    var head = E('div', 'as-head'); head.appendChild(E('h4', '', (opts.fresh ? 'New ' : 'Edit ') + noun)); box.appendChild(head);
    // Claude writes these best: from the notes, so every item is grounded in the user's own material
    var cb = E('div', 'as-claude' + (opts.fresh ? ' big' : ''));
    var ct = E('div', 'as-ct'); ct.appendChild(E('b', '', '✦ Suggested: have Claude write this ' + (isQ ? 'quiz' : 'set') + ' from your notes'));
    ct.appendChild(E('span', '', opts.fresh ? 'Claude drafts it only from your own materials — every ' + (isQ ? 'question and answer' : 'card') + ' comes from your notes — and adds it to this page. You can still change anything here afterwards.'
      : 'Need more ' + (isQ ? 'questions' : 'cards') + '? Claude can write them from your notes. Anything you change here stays.'));
    cb.appendChild(ct);
    var cbtn = E('button', 'as-claudebtn', '✦ Ask Claude to write it'); cbtn.type = 'button';
    cbtn.onclick = function(){ askClaudeStudy(W.k, key); }; cb.appendChild(cbtn); box.appendChild(cb);
    var nameRow = E('label', 'as-name'); nameRow.appendChild(E('span', '', 'Name on the bar'));
    var nameIn = E('input'); nameIn.type = 'text'; nameIn.maxLength = 120; nameIn.placeholder = isQ ? 'Quiz' : 'Flash cards'; nameIn.value = W.lab || '';
    nameIn.oninput = function(){ W.lab = nameIn.value; }; nameRow.appendChild(nameIn); box.appendChild(nameRow);
    var list = E('div', 'as-list'); box.appendChild(list);
    var addB = E('button', 'as-add', isQ ? '+ Add a question' : '+ Add a card'); addB.type = 'button'; box.appendChild(addB);
    if(!isQ){ var sh = E('label', 'as-opt'), shc = E('input'); shc.type = 'checkbox'; shc.checked = !!W.sh; shc.onchange = function(){ W.sh = shc.checked; };
      sh.appendChild(shc); sh.appendChild(document.createTextNode(' Start in a shuffled order')); box.appendChild(sh); }
    var err = E('div', 'as-err'); err.setAttribute('role', 'alert'); box.appendChild(err);
    var foot = E('div', 'as-foot'), bC = E('button', '', 'Cancel'), bS = E('button', 'as-save', 'Save'); bC.type = bS.type = 'button';
    foot.appendChild(bC); foot.appendChild(bS); box.appendChild(foot);

    function tools(onUp, onDown, onDel, lbl){
      var t = E('span', 'as-tools');
      [['↑', 'Move up', onUp], ['↓', 'Move down', onDown], ['✕', 'Remove ' + lbl, onDel]].forEach(function(x){
        var b = E('button', '', x[0]); b.type = 'button'; b.title = x[1]; b.setAttribute('aria-label', x[1]); b.onclick = x[2]; t.appendChild(b); });
      return t;
    }
    function mv(a, i, d){ var j = i + d; if(j < 0 || j >= a.length) return false; var t = a[i]; a[i] = a[j]; a[j] = t; return true; }
    function ta(cls, val, ph, rows, on){ var t = E('textarea', cls); t.rows = rows; t.placeholder = ph; t.value = val || ''; t.oninput = function(){ on(t.value); autosize(t); }; setTimeout(function(){ autosize(t); }, 0); return t; }
    function autosize(t){ t.style.height = 'auto'; t.style.height = Math.min(260, t.scrollHeight + 2) + 'px'; }
    function draw(focus){
      list.innerHTML = '';
      W.n.forEach(function(it, ni){
        var row = E('div', 'as-item'); row.setAttribute('data-n', ni);
        var ih = E('div', 'as-ih'); ih.appendChild(E('b', '', (isQ ? 'Question ' : 'Card ') + (ni + 1)));
        ih.appendChild(tools(function(){ if(mv(W.n, ni, -1)) draw(); }, function(){ if(mv(W.n, ni, 1)) draw(); },
          function(){ W.n.splice(ni, 1); if(!W.n.length) W.n.push(studyStarter(isQ ? 'quiz' : 'cards').n[0]); draw(); }, isQ ? 'this question' : 'this card'));
        row.appendChild(ih);
        if(isQ){
          row.appendChild(ta('as-q', it.q, 'The question', 2, function(v){ it.q = v; }));
          var multi = Array.isArray(it.a), mb = E('label', 'as-opt'), mc = E('input'); mc.type = 'checkbox'; mc.checked = multi;
          mc.onchange = function(){ if(mc.checked) it.a = typeof it.a === 'number' ? [it.a] : it.a; else it.a = Array.isArray(it.a) ? (it.a[0] != null ? it.a[0] : 0) : it.a; draw(); };
          mb.appendChild(mc); mb.appendChild(document.createTextNode(' More than one choice is right (“select all that apply”)')); row.appendChild(mb);
          row.appendChild(E('div', 'as-cl', multi ? 'Tick every right choice' : 'Mark the one right choice'));
          it.c.forEach(function(c, ci){
            var cr = E('div', 'as-ch'), on = multi ? it.a.indexOf(ci) >= 0 : it.a === ci;
            var mk = E('input'); mk.type = multi ? 'checkbox' : 'radio'; mk.name = 'as-r-' + ni; mk.checked = on; mk.title = 'This choice is right'; mk.setAttribute('aria-label', 'Choice ' + LETTERS[ci] + ' is right');
            mk.onchange = function(){ if(multi){ var s = it.a.filter(function(x){ return x !== ci; }); if(mk.checked) s.push(ci); it.a = s.sort(); } else it.a = ci; };
            cr.appendChild(mk); cr.appendChild(E('span', 'as-l', LETTERS[ci] + '.'));
            var ci_ = E('input', 'as-ci'); ci_.type = 'text'; ci_.maxLength = 500; ci_.placeholder = 'Choice ' + LETTERS[ci]; ci_.value = c; ci_.oninput = function(){ it.c[ci] = ci_.value; };
            cr.appendChild(ci_);
            cr.appendChild(tools(function(){ if(ci > 0){ moveChoice(it, ci, -1); draw(); } }, function(){ if(ci < it.c.length - 1){ moveChoice(it, ci, 1); draw(); } },
              function(){ if(it.c.length <= 2){ err.textContent = 'A question needs at least two choices.'; return; } dropChoice(it, ci); draw(); }, 'this choice'));
            row.appendChild(cr);
          });
          var ac = E('button', 'as-addc', '+ Add a choice'); ac.type = 'button'; ac.onclick = function(){ if(it.c.length >= 8){ err.textContent = 'At most 8 choices.'; return; } it.c.push(''); draw(); setTimeout(function(){ var ins = row.querySelectorAll('.as-ci'); if(ins.length) ins[ins.length - 1].focus(); }, 0); };
          row.appendChild(ac);
          row.appendChild(ta('as-x', it.x, 'Why that is the answer — shown after grading (optional)', 2, function(v){ it.x = v; }));
        } else {
          row.appendChild(E('div', 'as-cl', 'Front'));
          row.appendChild(ta('as-q', it.f, 'A question or a term', 2, function(v){ it.f = v; }));
          row.appendChild(E('div', 'as-cl', 'Back'));
          row.appendChild(ta('as-x', it.b, 'Its answer, from your notes', 3, function(v){ it.b = v; }));
        }
        list.appendChild(row);
      });
      if(focus != null){ var t = list.querySelectorAll('.as-item')[focus]; if(t){ t.scrollIntoView({block: 'nearest'}); var fi = t.querySelector('textarea'); if(fi) fi.focus(); } }
    }
    function moveChoice(it, ci, d){
      var cj = ci + d, t = it.c[ci]; it.c[ci] = it.c[cj]; it.c[cj] = t;
      function m(x){ return x === ci ? cj : x === cj ? ci : x; }
      it.a = Array.isArray(it.a) ? it.a.map(m).sort() : m(it.a);
    }
    function dropChoice(it, ci){
      it.c.splice(ci, 1);
      if(Array.isArray(it.a)) it.a = it.a.filter(function(x){ return x !== ci; }).map(function(x){ return x > ci ? x - 1 : x; });
      else it.a = it.a === ci ? 0 : it.a > ci ? it.a - 1 : it.a;
    }
    addB.onclick = function(){ W.n.push(studyStarter(isQ ? 'quiz' : 'cards').n[0]); draw(W.n.length - 1); };
    bC.onclick = function(){ close(true); };
    // Check it, drop what was left empty, and say what is wrong where it is
    function build(){
      var out = [], bad = null;
      W.n.forEach(function(it, ni){
        if(bad) return;
        if(isQ){
          var q = String(it.q || '').trim(), multi = Array.isArray(it.a), keep = [];
          it.c.forEach(function(c, ci){ if(String(c || '').trim()) keep.push(ci); });
          if(!q && !keep.length && !String(it.x || '').trim()) return;                    // an untouched blank
          if(!q){ bad = [ni, 'Question ' + (ni + 1) + ' needs its question.']; return; }
          if(keep.length < 2){ bad = [ni, 'Question ' + (ni + 1) + ' needs at least two choices.']; return; }
          var seen = {}, dup = false; keep.forEach(function(ci){ var k = String(it.c[ci]).trim().toLowerCase(); if(seen[k]) dup = true; seen[k] = 1; });
          if(dup){ bad = [ni, 'Question ' + (ni + 1) + ' repeats a choice.']; return; }
          var want = (multi ? it.a : [it.a]).filter(function(x){ return keep.indexOf(x) >= 0; }).map(function(x){ return keep.indexOf(x); });
          if(!want.length){ bad = [ni, 'Question ' + (ni + 1) + ': mark which choice is right.']; return; }
          if(want.length === keep.length){ bad = [ni, 'Question ' + (ni + 1) + ': every choice is marked right — leave at least one wrong.']; return; }
          var o = {i: it.i, q: q, c: keep.map(function(ci){ return String(it.c[ci]).trim(); }), a: multi ? want.sort() : want[0]};
          var x = String(it.x || '').trim(); if(x) o.x = x;
          out.push(o);
        } else {
          var fr = String(it.f || '').trim(), bk = String(it.b || '').trim();
          if(!fr && !bk) return;
          if(!fr || !bk){ bad = [ni, 'Card ' + (ni + 1) + ' needs both a front and a back.']; return; }
          out.push({i: it.i, f: fr, b: bk});
        }
      });
      if(bad) return {bad: bad};
      if(!out.length) return {bad: [0, isQ ? 'Add at least one question.' : 'Add at least one card.']};
      var v = isQ ? {k: 'q', lab: String(W.lab || '').trim(), n: out} : {k: 'c', lab: String(W.lab || '').trim(), sh: !!W.sh, n: out};
      return {v: v};
    }
    bS.onclick = function(){
      var r = build();
      if(r.bad){ err.textContent = r.bad[1]; var it = list.querySelectorAll('.as-item')[r.bad[0]]; if(it){ it.scrollIntoView({block: 'center'}); it.classList.add('bad'); setTimeout(function(){ it.classList.remove('bad'); }, 1800); } return; }
      var done = change('sd|' + key + '|study', r.v);
      close(false); toast(done ? (opts.fresh ? 'Added — ⌘Z takes it back.' : 'Saved — ⌘Z brings back the old one.') : 'Nothing changed.');
    };
    draw(opts.fresh ? 0 : null);
    setTimeout(function(){ (opts.fresh ? cbtn : nameIn).focus(); }, 30);
  }
"""

STUDY_EDIT_CSS = r"""
  /* flash cards and quizzes: the button on each, and the editor (study_edit.py) */
  .aed-st{font:inherit;font-size:12.5px;line-height:1;padding:7px 12px;border-radius:999px;border:1.5px dashed var(--muted);background:none;color:var(--text);cursor:pointer;}
  .aed-st:hover{border-style:solid;border-color:var(--text);}
  #aed-study{position:fixed;inset:0;z-index:8460;display:flex;align-items:flex-start;justify-content:center;padding:4vh 16px;overflow:auto;background:rgba(8,9,16,.5);}
  #aed-study .as-box{width:760px;max-width:100%;box-sizing:border-box;padding:20px 22px 16px;border-radius:18px;background:var(--surface);color:var(--text);
    border:1px solid var(--border);box-shadow:0 28px 70px rgba(0,0,0,.4);font:14px/1.45 system-ui,-apple-system,sans-serif;}
  #aed-study h4{margin:0 0 12px;font-size:18px;font-weight:650;}
  #aed-study .as-claude{display:flex;align-items:center;gap:14px;margin:0 0 16px;padding:11px 14px;border-radius:13px;
    border:1px solid color-mix(in srgb,var(--accent,#7c6cf0) 55%,var(--border));background:color-mix(in srgb,var(--accent,#7c6cf0) 11%,transparent);}
  #aed-study .as-claude.big{padding:16px 18px;border-width:2px;}
  #aed-study .as-ct{flex:1;font-size:12.5px;color:var(--muted);line-height:1.5;}
  #aed-study .as-ct b{display:block;color:var(--text);font-size:14px;margin-bottom:3px;}
  #aed-study .as-claudebtn{flex:none;font:inherit;font-size:13px;font-weight:600;padding:9px 15px;border-radius:10px;border:0;background:var(--accent,#7c6cf0);color:#fff;cursor:pointer;}
  #aed-study .as-claudebtn:hover{filter:brightness(1.08);}
  #aed-study .as-name{display:block;margin:0 0 12px;} #aed-study .as-name span{display:block;font-size:11.5px;color:var(--muted);margin-bottom:3px;}
  #aed-study input[type=text],#aed-study textarea{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:9px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-study textarea{resize:vertical;min-height:44px;display:block;}
  #aed-study .as-item{margin:0 0 12px;padding:12px 14px 12px;border-radius:13px;border:1px solid var(--border);background:color-mix(in srgb,var(--text) 3%,transparent);transition:box-shadow .3s;}
  #aed-study .as-item.bad{box-shadow:0 0 0 2px #dc2626;}
  #aed-study .as-ih{display:flex;align-items:center;justify-content:space-between;margin:0 0 7px;}
  #aed-study .as-ih b{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-study .as-tools{display:inline-flex;gap:3px;flex:none;}
  #aed-study .as-tools button{width:26px;height:26px;padding:0;border-radius:7px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer;font:inherit;font-size:12px;line-height:1;}
  #aed-study .as-tools button:hover{color:var(--text);border-color:var(--muted);}
  #aed-study .as-tools button:last-child:hover{color:#dc2626;border-color:#dc2626;}
  #aed-study .as-cl{margin:9px 0 4px;font-size:11.5px;color:var(--muted);}
  #aed-study .as-ch{display:flex;align-items:center;gap:8px;margin:0 0 6px;}
  #aed-study .as-ch>input[type=radio],#aed-study .as-ch>input[type=checkbox]{flex:none;width:17px;height:17px;margin:0;accent-color:var(--accent,#7c6cf0);}
  #aed-study .as-l{flex:none;width:18px;color:var(--muted);font-size:13px;}
  #aed-study .as-opt{display:flex;align-items:center;gap:6px;margin:8px 0 0;font-size:12.5px;color:var(--muted);cursor:pointer;}
  #aed-study .as-opt input{accent-color:var(--accent,#7c6cf0);}
  #aed-study .as-addc,#aed-study .as-add{font:inherit;font-size:12.5px;padding:6px 12px;border-radius:9px;border:1.5px dashed var(--border);background:none;color:var(--muted);cursor:pointer;margin:2px 0 8px;}
  #aed-study .as-add{display:block;width:100%;padding:11px;margin:0 0 6px;border-radius:12px;font-size:13.5px;}
  #aed-study .as-addc:hover,#aed-study .as-add:hover{color:var(--text);border-color:var(--muted);}
  #aed-study .as-err{min-height:18px;margin:6px 0 0;font-size:12.5px;color:#dc2626;}
  #aed-study .as-foot{display:flex;justify-content:flex-end;gap:8px;margin-top:8px;position:sticky;bottom:-16px;padding:10px 0 4px;background:var(--surface);}
  #aed-study .as-foot button{height:34px;padding:0 18px;border-radius:9px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-study .as-foot .as-save{background:var(--accent,#7c6cf0);border-color:transparent;color:#fff;font-weight:600;}
  @media (max-width:600px){#aed-study .as-claude{flex-direction:column;align-items:stretch;}}
"""
