"""Manual edit mode for Key figures sections (figures.py), spliced into MANUAL_JS / MANUAL_CSS by manual_edit.manual_edit with the same
markers the flash-card editor uses (it uses that script's own `field`, `change`, `changes`, `undo`, `toast`, `rid`, `STORE`):

  FIG_EDIT_FIELD     the field `fg|<section key>|figs`: a section's whole list of rows, one change, one step of undo
  FIG_EDIT_REFRESH   what to redraw when that field changes (the box in place; a new section re-renders the page)
  FIG_EDIT_DECORATE  the "✎ Edit figures" button under each box
  FIG_EDIT_JS        the editor (the block's name, the rows: add, remove, move; Save is one ⌘Z), the starter a new section gets
  (the editor reuses the flash-card editor's sheet, #aed-study, so it needs no sheet of its own beyond the button and one row layout)

Desktop only, like every structural edit. The editor works on a copy and saves once; Cancel on a section just made takes it away again.
"""

FIG_EDIT_FIELD = r"""    if(kind === 'fg' && p.length === 3 && p[2] === 'figs'){
      var FG = window._ALTO_FG = window._ALTO_FG || {};
      if(NEWT.test(id)){
        if(!FG[id] && !newTreeSec(id)) return null;
        return {kind:'struct', sig:function(){ return 'new'; },
          get:function(){ return FG[id] ? JSON.parse(JSON.stringify(FG[id])) : null; },
          set:function(v){ var q = newTreeSec(id);
            if(v && v.n && v.n.length){ FG[id] = JSON.parse(JSON.stringify(v)); if(q) setSlot(q.s, id, true, 'afg'); }
            else { delete FG[id]; if(q) setSlot(q.s, id, false, 'afg'); } }};
      }
      if(!FG[id]) return null;
      return {kind:'struct', sig:function(){ return PRIS['fg|' + id]; },
        get:function(){ return JSON.parse(JSON.stringify(FG[id])); },
        set:function(v){ FG[id] = JSON.parse(JSON.stringify(v)); }};
    }
"""

FIG_EDIT_REFRESH = r"""    if(kind === 'fg'){
      if(NEWT.test(p[1] || '') || !(window._altoFigures && document.querySelector('.dl-box[data-afg-key="' + p[1] + '"]'))){ if(P){ rerenderPage(P); repaint(); } return; }
      window._altoFigures.sync(p[1]); if(P) repaint();
      return;
    }
"""

FIG_EDIT_DECORATE = r"""      if(structOK()) dc.querySelectorAll('.dl-box[data-afg-key]').forEach(function(bx){
        var key = bx.getAttribute('data-afg-key'), nx = bx.nextSibling;
        if(!field('fg|' + key + '|figs') || (nx && nx.classList && nx.classList.contains('aed-fg-wrap'))) return;
        var w = document.createElement('div'); w.className = 'aed-fg-wrap';
        var eb = document.createElement('button'); eb.type = 'button'; eb.className = 'aed-fg'; eb.setAttribute('data-fk', key);
        eb.textContent = '✎ Edit figures'; eb.title = 'Edit the rows: add, remove and reorder them';
        w.appendChild(eb); bx.parentNode.insertBefore(w, bx.nextSibling);
      });
"""

FIG_EDIT_JS = r"""  /* ── key figures: the editor (figures_edit.py) ─────────────────────────── */
  function figStarter(){ return {n: [{i: rid('r'), f: '', l: ''}]}; }
  function figHKey(key){
    var m = /^(n|c|a0|a1)-(.+)-(\d+|new-[a-z0-9]+)$/.exec(key); if(!m) return '';
    return {n: 'n', c: 'c', a0: 'env', a1: 'theme'}[m[1]] + '|' + m[2] + '|s|' + m[3] + '|h';
  }
  function openFigEditor(key, opts){
    opts = opts || {};
    var f = field('fg|' + key + '|figs'); if(!f) return;
    var W = f.get(); if(!W) return;
    var hk = figHKey(key), hf = hk ? field(hk) : null, name0 = hf ? String(txt(hf.get()) || '').trim() : '', name = name0 || 'Key figures';
    var w = document.getElementById('aed-study');
    if(w) w.parentNode.removeChild(w);
    w = document.createElement('div'); w.id = 'aed-study'; w.className = 'aed-fig'; document.body.appendChild(w);
    var box = document.createElement('div'); box.className = 'as-box'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); w.appendChild(box);
    function E(tag, cls, t){ var e = document.createElement(tag); if(cls) e.className = cls; if(t != null) e.textContent = t; return e; }
    function close(cancelled){ if(w.parentNode) w.parentNode.removeChild(w); window.removeEventListener('keydown', onKey, true);
      if(window._unifiedEscape) window.addEventListener('keydown', window._unifiedEscape, true);
      if(cancelled && opts.fresh){ var o = STORE.ops['fg|' + key + '|figs']; if(o && !o.done) undo(); } }
    function onKey(e){ if(e.key === 'Escape'){ e.preventDefault(); e.stopImmediatePropagation(); close(true); } }
    if(window._unifiedEscape) window.removeEventListener('keydown', window._unifiedEscape, true);
    window.addEventListener('keydown', onKey, true);
    w.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    w.addEventListener('click', function(e){ e.stopPropagation(); });
    w.addEventListener('keydown', function(e){ e.stopPropagation(); });
    var head = E('div', 'as-head'); head.appendChild(E('h4', '', opts.fresh ? 'New key figures' : 'Edit key figures')); box.appendChild(head);
    var nameRow = E('label', 'as-name'); nameRow.appendChild(E('span', '', 'Name of this block (Key figures, Deadlines, Limits…)'));
    var nameIn = E('input'); nameIn.type = 'text'; nameIn.maxLength = 120; nameIn.placeholder = 'Key figures'; nameIn.value = name; nameIn.oninput = function(){ name = nameIn.value; };
    nameRow.appendChild(nameIn); box.appendChild(nameRow);
    var list = E('div', 'as-list'); box.appendChild(list);
    var addB = E('button', 'as-add', '+ Add a row'); addB.type = 'button'; box.appendChild(addB);
    var err = E('div', 'as-err'); err.setAttribute('role', 'alert'); box.appendChild(err);
    var foot = E('div', 'as-foot'), bC = E('button', '', 'Cancel'), bS = E('button', 'as-save', 'Save'); bC.type = bS.type = 'button';
    foot.appendChild(bC); foot.appendChild(bS); box.appendChild(foot);
    function tools(onUp, onDown, onDel){
      var t = E('span', 'as-tools');
      [['↑', 'Move up', onUp], ['↓', 'Move down', onDown], ['✕', 'Remove this row', onDel]].forEach(function(x){
        var b = E('button', '', x[0]); b.type = 'button'; b.title = x[1]; b.setAttribute('aria-label', x[1]); b.onclick = x[2]; t.appendChild(b); });
      return t;
    }
    function mv(a, i, d){ var j = i + d; if(j < 0 || j >= a.length) return false; var t = a[i]; a[i] = a[j]; a[j] = t; return true; }
    function inp(cls, val, ph, max, on, label){ var t = E('input', cls); t.type = 'text'; t.maxLength = max; t.placeholder = ph; t.value = val || ''; t.setAttribute('aria-label', label || ph); t.oninput = function(){ on(t.value); }; return t; }
    function ta(cls, val, ph, on){ var t = E('textarea', cls); t.rows = 2; t.maxLength = 2000; t.placeholder = ph; t.value = val || ''; t.setAttribute('aria-label', ph); t.oninput = function(){ on(t.value); t.style.height = 'auto'; t.style.height = Math.min(220, t.scrollHeight + 2) + 'px'; }; return t; }
    function draw(focus){
      list.innerHTML = '';
      W.n.forEach(function(it, ni){
        var row = E('div', 'as-item'); row.setAttribute('data-n', ni);
        var ih = E('div', 'as-ih'); ih.appendChild(E('b', '', 'Row ' + (ni + 1)));
        ih.appendChild(tools(function(){ if(mv(W.n, ni, -1)) draw(ni - 1); }, function(){ if(mv(W.n, ni, 1)) draw(ni + 1); },
          function(){ W.n.splice(ni, 1); if(!W.n.length) W.n.push(figStarter().n[0]); draw(); }));
        row.appendChild(ih);
        var top = E('div', 'afe-top');
        top.appendChild(inp('afe-f', it.f, 'Figure: 21 days, $75,000, 12…', 40, function(v){ it.f = v; }, 'The big figure'));
        top.appendChild(inp('afe-l', it.l, 'Label: what the figure is', 200, function(v){ it.l = v; }, 'Label'));
        row.appendChild(top);
        row.appendChild(inp('afe-d', it.d, 'Detail line (optional): when it runs, who it binds…', 200, function(v){ it.d = v; }, 'Detail line'));
        row.appendChild(ta('as-x', it.q, 'Quote (optional): the words that set it', function(v){ it.q = v; }));
        row.appendChild(inp('afe-c', it.c, 'Citation (optional): Rule 15(a)(1)(A)', 120, function(v){ it.c = v; }, 'Citation'));
        list.appendChild(row);
      });
      if(focus != null){ var t = list.querySelectorAll('.as-item')[focus]; if(t){ t.scrollIntoView({block: 'nearest'}); var fi = t.querySelector('.afe-f'); if(fi) fi.focus(); } }
    }
    addB.onclick = function(){ if(W.n.length >= 24){ err.textContent = 'At most 24 rows.'; return; } W.n.push(figStarter().n[0]); draw(W.n.length - 1); };
    bC.onclick = function(){ close(true); };
    bS.onclick = function(){
      var out = [], bad = -1;
      W.n.forEach(function(it, ni){
        var fg = String(it.f || '').trim(); if(bad >= 0) return;
        var o = {i: it.i, f: fg}; ['l', 'd', 'q', 'c'].forEach(function(k){ var v = String(it[k] || '').replace(/[ \t]+/g, ' ').trim(); if(v) o[k] = v; });
        if(!fg && Object.keys(o).length === 2) return;                         // an untouched blank row
        if(!fg){ bad = ni; return; }
        out.push(o);
      });
      if(bad >= 0){ err.textContent = 'Row ' + (bad + 1) + ' needs its figure.'; var it = list.querySelectorAll('.as-item')[bad]; if(it){ it.scrollIntoView({block: 'center'}); it.classList.add('bad'); setTimeout(function(){ it.classList.remove('bad'); }, 1800); } return; }
      if(!out.length){ err.textContent = 'Add at least one figure.'; return; }
      var L = [['fg|' + key + '|figs', {n: out}]], nm = String(name || '').replace(/\s+/g, ' ').trim() || 'Key figures';
      if(hf && nm !== name0) L.push([hk, nm]);
      var done = changes(L);
      close(false); toast(done ? (opts.fresh ? 'Added — ⌘Z takes it back.' : 'Saved — ⌘Z brings back the old one.') : 'Nothing changed.');
    };
    draw(opts.fresh ? 0 : null);
    setTimeout(function(){ var t = list.querySelector('.afe-f'); if(t) t.focus(); }, 30);
  }
"""

FIG_EDIT_CSS = r"""
  /* key figures: the button under each block, and the editor's row (figures_edit.py; the sheet is the flash-card editor's) */
  .aed-fg-wrap{display:block;margin:6px 0 2px;}
  .aed-fg{font:inherit;font-size:12.5px;line-height:1;padding:7px 12px;border-radius:999px;border:1.5px dashed var(--muted);background:none;color:var(--text);cursor:pointer;}
  .aed-fg:hover{border-style:solid;border-color:var(--text);}
  #aed-study.aed-fig .afe-top{display:grid;grid-template-columns:minmax(0,9em) minmax(0,1fr);gap:8px;margin:0 0 8px;}
  #aed-study.aed-fig .afe-f{font-weight:700;} #aed-study.aed-fig input[type=text]{display:block;}
  #aed-study.aed-fig .afe-d,#aed-study.aed-fig .afe-c{margin:0 0 8px;}
  @media (max-width:600px){#aed-study.aed-fig .afe-top{grid-template-columns:minmax(0,1fr);}}
"""
