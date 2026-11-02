"""The study plan on the page (Luke, 2026-11-01: "Allow a user to have claude or bass create a study plan, identifying which nodes the
user needs to study and highlighting them according to a study schedule"; spec ORG/notes-tl-studyplan-spec.md).

A plan is `brief.study_plan` = {v: 1, exam_date, days_per_week, minutes_per_day, items: [{node, day, why, signal}]}, written by the Claude tool
or Bass (both validate with plan_check.py). This module only DRAWS it, on a computer's page:
  * every planned node gets one class by the reader's own local date (so a page opened tomorrow changes by itself): sp-today (a clear ring and a
    small day tag), sp-soon (the next three days, a dim ring), sp-late (past due and not ticked, a stronger ring), sp-done (every item ticked);
    the same classes on every format, because every node is `#node-<id>` (cards, System discs, lanes);
  * a "Study plan" row in the notes panel opens a sheet: Late / Today / This week, each item with its reason, a tick, and a click to go to the node;
    "Make or change my plan" is a hook (window._altoStudyPlanRoutes.open) like the converter's, with a prompt to copy when no route is installed.
The ticks are the READER's state, kept with the card marks in the page's study state (`{hl key}-st`, section key "__plan__", card id "node|day",
1 = done, 0 = cleared): the shape alto-cloud.js already merges. The tool never writes them.
Absent plan (or one with no usable item) = this returns "" and the page is byte-identical to before. Nothing is drawn on a phone."""
from __future__ import annotations

import re

from .blocks import ID_PATTERNS
from .sanitize import js_json, plain_text

SIGNALS = ("marks", "quiz", "exam", "told", "syllabus")
MAX_ITEMS = 120
MAX_WHY = 200
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _day_ok(s) -> bool:
    import datetime
    try:
        datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return False
    return bool(_DAY.match(s))


def clean(plan, node_ids) -> dict:
    """The part of a stored plan the page can draw: items for nodes that are here, on real days, with a plain reason, no repeats. The tool and
    Bass check the same things before they save (plan_check.py); this keeps a hand-edited or older brief from drawing a ring on nothing."""
    if not isinstance(plan, dict):
        return {}
    have, seen, items = set(node_ids), set(), []
    for it in plan.get("items") or []:
        if not isinstance(it, dict):
            continue
        n, d = it.get("node"), it.get("day")
        why = plain_text(it.get("why") or "").strip()[:MAX_WHY]
        if n not in have or not _day_ok(d) or not why or (n, d) in seen:
            continue
        seen.add((n, d))
        sig = it.get("signal")
        items.append({"node": n, "day": d, "why": why, "signal": sig if sig in SIGNALS else ""})
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        return {}
    exam = plan.get("exam_date")
    mpd = plan.get("minutes_per_day")
    return {"v": 1, "exam": exam if _day_ok(exam) else "", "minutes": mpd if isinstance(mpd, int) and not isinstance(mpd, bool) and 0 < mpd <= 1440 else 0, "items": items}


CSS = r"""<style id="alto-sp-css">
  /* a planned node: one class by the reader's date, drawn as Art's look page shows (study_plan.py). A computer's page only: a phone and its whole view draw nothing */
  html{--sp-late:#b42318;--sp-ok:#1f6b3a;--sp-acc:#5b3fc4;} html.dark{--sp-late:#ff8a7a;--sp-ok:#7fd49a;--sp-acc:#b7a6ff;}
  /* Retro and Holographic dress the page in their own accent (gold, the theme's glow): the plan follows it there, as Art's frames show */
  html.alto-holo,html.alto-retro{--sp-acc:var(--accent);}
  /* Holographic keeps late RED on both its grounds (Art alto-art-1101-4800-a); today stays the theme's own light (--accent), the words stay on the tag */
  html.alto-holo{--sp-late:#b42318;--sp-ok:#1f6b3a;} html.alto-holo.dark{--sp-late:#ff8a7a;--sp-ok:#7fd49a;}
  html:not(.mobile):not(.phone-whole) .node.sp-today > .node-card{outline:3px solid var(--sp-acc);outline-offset:4px;box-shadow:0 0 0 9px color-mix(in srgb,var(--sp-acc) 20%,transparent);}
  html:not(.mobile):not(.phone-whole) .node.sp-soon > .node-card{outline:2px dashed var(--sp-acc);outline-offset:4px;}
  html:not(.mobile):not(.phone-whole) .node.sp-late > .node-card{outline:3px solid var(--sp-late);outline-offset:4px;}
  html:not(.mobile):not(.phone-whole) .node.sp-done > .node-card{opacity:.66;}
  html:not(.mobile):not(.phone-whole) .node .sp-tag{display:block;position:absolute;top:-11px;right:10px;z-index:3;padding:5px 8px;font:700 11px/1 system-ui,-apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;
    border-radius:6px;background:var(--sp-acc);color:var(--bg);pointer-events:none;}
  html:not(.mobile):not(.phone-whole) .node.sp-soon .sp-tag{background:transparent;color:var(--text);border:1px solid var(--sp-acc);}
  html:not(.mobile):not(.phone-whole) .node.sp-late .sp-tag{background:var(--sp-late);color:var(--bg);}
  html:not(.mobile):not(.phone-whole) .node.sp-done .sp-tag{background:transparent;color:var(--sp-ok);border:1px solid var(--sp-ok);}
  html:not(.mobile):not(.phone-whole) .node.sp-go > .node-card{outline:3px solid var(--sp-acc);outline-offset:8px;}
  .sp-tag{display:none;}
  /* the entry: a tab on the right rail under Overview, seen without opening the notes panel; its words say what a click does */
  #sp-chip{display:none;}
  html:not(.mobile):not(.phone-whole) #sp-chip{display:block;position:fixed;right:0;top:calc(50% + 84px);z-index:395;width:34px;box-sizing:border-box;padding:12px 0;writing-mode:vertical-rl;
    background:var(--surface);border:1px solid var(--border);border-right:none;color:var(--sp-acc);border-radius:6px 0 0 6px;cursor:pointer;font:inherit;font-size:11px;letter-spacing:.08em;white-space:nowrap;}
  html:not(.mobile):not(.phone-whole) #sp-chip:hover,html:not(.mobile):not(.phone-whole) #sp-chip.open{color:var(--text);border-color:var(--sp-acc);}
  #sp-chip.late{color:var(--sp-late);}
  html:not(.mobile):not(.phone-whole) #tab-rail > #sp-chip{position:static !important;top:auto !important;right:auto !important;}
  #sp-row{display:none;}
  html:not(.mobile):not(.phone-whole) #sp-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:10px 12px 0;padding:8px 12px;border:1px solid var(--border);border-radius:9px;
    background:var(--surface);color:var(--text);font:inherit;font-size:12.5px;cursor:pointer;text-align:left;}
  html:not(.mobile):not(.phone-whole) #sp-row:hover{border-color:var(--sp-acc);}
  #sp-row b{font-weight:600;} #sp-row span{color:var(--muted);font-size:11.5px;}
  #notes-panel.fw-mode #sp-row{display:none !important;}
  #sp-sheet{display:none;}
  html:not(.mobile):not(.phone-whole) #sp-sheet.open{display:flex;flex-direction:column;position:fixed;top:var(--nav-bottom,115px);right:46px;width:380px;max-height:calc(100vh - var(--nav-bottom,115px) - 24px);z-index:396;
    background:var(--panel-glass-bg,var(--surface));color:var(--text);border:1px solid var(--border);border-radius:14px;box-shadow:0 10px 34px rgba(0,0,0,.28);overflow:hidden;padding:16px 18px;box-sizing:border-box;}
  #sp-sheet h3{margin:0;font-size:20px;font-weight:600;line-height:1.2;}
  #sp-sheet .sp-ex{color:var(--muted);margin:4px 0 12px;font-size:13px;}
  #sp-sheet .sp-tabs{display:inline-flex;align-self:flex-start;border:1px solid var(--border);border-radius:9px;overflow:hidden;margin-bottom:6px;}
  #sp-sheet .sp-tabs button{border:0;background:transparent;color:var(--text);font:inherit;font-size:13px;font-weight:600;padding:9px 16px;cursor:pointer;}
  #sp-sheet .sp-tabs button[aria-selected="true"]{background:var(--sp-acc);color:var(--bg);}
  #sp-sheet .sp-body{flex:1;overflow-y:auto;}
  #sp-sheet .sp-li{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:10px;align-items:start;padding:10px 0;border-top:1px solid var(--border);}
  #sp-sheet .sp-li input{appearance:none;-webkit-appearance:none;width:22px;height:22px;margin:2px 0 0;border:2px solid var(--sp-acc);border-radius:5px;cursor:pointer;display:grid;place-items:center;background:transparent;}
  #sp-sheet .sp-li input:checked{background:var(--sp-acc);} #sp-sheet .sp-li input:checked::after{content:"\2713";color:var(--bg);font-size:14px;line-height:1;}
  #sp-sheet .sp-li input:focus-visible{outline:2px solid var(--sp-acc);outline-offset:2px;}
  #sp-sheet .sp-go{display:block;padding:0;border:0;background:transparent;color:var(--text);font:inherit;font-size:15px;font-weight:700;text-align:left;cursor:pointer;}
  #sp-sheet .sp-go:hover{text-decoration:underline;}
  #sp-sheet .sp-w{display:block;font-style:normal;color:var(--muted);font-size:13px;margin-top:2px;}
  #sp-sheet .sp-li.done .sp-go{color:var(--muted);}
  #sp-sheet .sp-pill{padding:5px 8px;border-radius:6px;font:700 11px/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;background:var(--sp-acc);color:var(--bg);}
  #sp-sheet .sp-pill.soon{background:transparent;color:var(--text);border:1px solid var(--sp-acc);} #sp-sheet .sp-pill.late{background:var(--sp-late);color:var(--bg);}
  #sp-sheet .sp-pill.done{background:transparent;color:var(--sp-ok);border:1px solid var(--sp-ok);}
  #sp-sheet .sp-none{padding:12px 0;color:var(--muted);font-size:13px;border-top:1px solid var(--border);}
  #sp-sheet .sp-btns{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap;}
  #sp-sheet .sp-btn{min-height:40px;padding:0 16px;border-radius:10px;background:var(--sp-acc);color:var(--bg);font:inherit;font-size:13px;font-weight:700;border:0;cursor:pointer;}
  #sp-sheet .sp-btn.o{background:transparent;color:var(--text);border:1.5px solid var(--border);}
  #sp-sheet .sp-pr{margin-top:10px;font-size:12px;color:var(--muted);} #sp-sheet .sp-pr textarea{width:100%;box-sizing:border-box;height:90px;margin-top:6px;font:inherit;font-size:12px;
    background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:6px 8px;resize:none;}
  @media (max-width:640px){ #sp-chip,#sp-row,#sp-sheet,.sp-tag{display:none !important;} .node.sp-today > .node-card,.node.sp-soon > .node-card,.node.sp-late > .node-card,.node.sp-done > .node-card{outline:0 !important;box-shadow:none !important;opacity:1 !important;} }
  @media print{ .node.sp-today > .node-card,.node.sp-soon > .node-card,.node.sp-late > .node-card,.node.sp-done > .node-card{outline:0 !important;box-shadow:none !important;opacity:1 !important;} .sp-tag,#sp-chip,#sp-row,#sp-sheet{display:none !important;} }
</style>"""

JS = r"""<script id="alto-sp">
(function(){
  var P = window._ALTO_SP || null, HAS = !!(P && P.items && P.items.length);
  var KEY = '__ALTO_HL_KEY__-st', SEC = '__plan__', DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var r = document.documentElement, sheet = null, row = null, chip = null, timer = 0, tab = 'today';
  function desk(){ return !r.classList.contains('mobile') && !r.classList.contains('phone-whole') && window.innerWidth > 640; }
  function el(tag, cls, txt){ var e = document.createElement(tag); if(cls) e.className = cls; if(txt != null) e.textContent = txt; return e; }
  function now(){ return window._altoSpNow ? new Date(window._altoSpNow) : new Date(); }
  function key(d){ function z(n){ return n < 10 ? '0' + n : '' + n; } return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()); }
  function ord(s){ var a = s.split('-'); return Date.UTC(+a[0], +a[1] - 1, +a[2]) / 864e5; }
  function human(s){ var a = s.split('-'), d = new Date(+a[0], +a[1] - 1, +a[2]); return DAYS[d.getDay()] + ' ' + d.getDate() + ' ' + MON[d.getMonth()]; }
  function wk(s){ var a = s.split('-'); return DAYS[new Date(+a[0], +a[1] - 1, +a[2]).getDay()]; }
  /* the reader's ticks: {v:1, s:{__plan__:{m, k:{'node|day':[1 done | 0 cleared, t]}}}}, the study state's own shape (alto-cloud.js merges it) */
  function load(){ try{ var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if(o && o.s && typeof o.s === 'object') return o; }catch(e){} return {v:1, s:{}}; }
  function done(n, d){ var k = (load().s[SEC] || {}).k || {}, v = k[n + '|' + d]; return !!(v && v[0] === 1); }
  function tick(n, d, on){
    var o = load(), s = o.s[SEC] || (o.s[SEC] = {}), k = s.k || (s.k = {}); k[n + '|' + d] = [on ? 1 : 0, Date.now()]; s.m = Date.now();
    try{ localStorage.setItem(KEY, JSON.stringify(o)); }catch(e){}
  }
  /* each item's state today: late (past, not ticked), today, soon (the next three days), later, done */
  function states(){
    if(!HAS) return [];
    var t = ord(key(now()));
    return P.items.map(function(it){
      var dd = ord(it.day) - t, dn = done(it.node, it.day);
      return {it: it, st: dn ? 'done' : dd < 0 ? 'late' : dd === 0 ? 'today' : dd <= 3 ? 'soon' : 'later', dd: dd};
    });
  }
  function word(x){
    return x.st === 'done' ? '✓ Done' : x.st === 'today' ? 'Today' : x.st === 'late' ? (-x.dd) + (x.dd === -1 ? ' day late' : ' days late') : x.dd === 1 ? 'Tomorrow' : wk(x.it.day);
  }
  /* the tab belongs in the right rail with Overview, Notes, Filter and Scene (before Scene, which keeps itself last); until the rail exists it stands alone on the edge */
  function place(){
    var rail = document.getElementById('tab-rail'); if(!chip || !rail || chip.parentNode === rail) return;
    var bg = document.getElementById('bg-toggle'); if(bg && bg.parentNode === rail) rail.insertBefore(chip, bg); else rail.appendChild(chip);
  }
  function paint(){
    place();
    var S = states(), by = {};
    S.forEach(function(x){ (by[x.it.node] || (by[x.it.node] = [])).push(x); });
    Array.prototype.forEach.call(document.querySelectorAll('.node[class*="sp-"]'), function(n){ n.classList.remove('sp-today', 'sp-soon', 'sp-late', 'sp-done'); var t = n.querySelector('.sp-tag'); if(t) t.remove(); });
    if(desk()) Object.keys(by).forEach(function(id){
      var n = document.getElementById('node-' + id); if(!n) return;
      var L = by[id], c = ['late', 'today', 'soon'].filter(function(k){ return L.some(function(x){ return x.st === k; }); })[0] || (L.every(function(x){ return x.st === 'done'; }) ? 'done' : '');
      if(!c) return;
      var pick = c === 'done' ? L[0] : L.filter(function(x){ return x.st === c; }).sort(function(a, b){ return c === 'late' ? a.dd - b.dd : a.dd - b.dd; })[0];
      n.classList.add('sp-' + c);
      var host = n.querySelector('.node-card') || n, tg = el('span', 'sp-tag', word(pick)); tg.setAttribute('aria-hidden', 'true'); host.appendChild(tg);
    });
    summary(S); if(sheet && sheet.classList.contains('open')) fill(S);
  }
  function title(id){ var n = document.querySelector('#node-' + id), t = n && n.querySelector('.node-title'), o = n && n.querySelector('.node-order'); return (o && o.textContent.trim() ? o.textContent.trim() + ' ' : '') + (t ? t.textContent.trim() : id); }
  function fly(id){
    var n = document.getElementById('node-' + id); if(!n) return;
    try{ n.scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'}); }catch(e){ n.scrollIntoView(); }
    n.classList.add('sp-go'); setTimeout(function(){ n.classList.remove('sp-go'); }, 1600);
  }
  function counts(S){ return {today: S.filter(function(x){ return x.st === 'today'; }).length, late: S.filter(function(x){ return x.st === 'late'; }).length}; }
  function summary(S){
    var c = counts(S), txt = !HAS ? 'Make a study plan' : c.late ? c.late + ' late · Today: ' + c.today : c.today ? 'Today: ' + c.today : 'Study plan';
    if(row) row.querySelector('span').textContent = !HAS ? 'make one' : c.late ? c.late + ' late · ' + c.today + ' today' : c.today ? c.today + ' today' : 'nothing due today';
    if(chip){ chip.textContent = txt; chip.classList.toggle('late', !!c.late); chip.setAttribute('aria-label', 'Study plan: ' + txt); }
  }
  function item(x){
    var d = el('div', 'sp-li' + (x.st === 'done' ? ' done' : '')), cb = el('input'); cb.type = 'checkbox'; cb.checked = x.st === 'done'; cb.setAttribute('aria-label', 'Done: ' + title(x.it.node));
    cb.onchange = function(){ tick(x.it.node, x.it.day, cb.checked); paint(); };
    var t = el('div'), g = el('button', 'sp-go', title(x.it.node)); g.type = 'button'; g.onclick = function(){ fly(x.it.node); };
    t.appendChild(g); t.appendChild(el('i', 'sp-w', x.it.why));
    var pl = el('span', 'sp-pill ' + x.st, word(x)); d.appendChild(cb); d.appendChild(t); d.appendChild(pl); return d;
  }
  function fill(S){
    var b = sheet.querySelector('.sp-body'); b.textContent = '';
    var L = S.filter(tab === 'today' ? function(x){ return x.st === 'late' || x.st === 'today' || (x.st === 'done' && x.dd <= 0); }
                                     : function(x){ return x.dd > 0 && x.dd <= 7; }).sort(function(a, c){ return a.dd - c.dd; });
    L.forEach(function(x){ b.appendChild(item(x)); });
    if(!L.length) b.appendChild(el('div', 'sp-none', tab === 'today' ? 'Nothing due today.' : 'Nothing planned for the next week.'));
    Array.prototype.forEach.call(sheet.querySelectorAll('.sp-tabs button'), function(t){ t.setAttribute('aria-selected', t.getAttribute('data-t') === tab ? 'true' : 'false'); });
    var ex = sheet.querySelector('.sp-ex'), bits = [], left = P && P.exam ? ord(P.exam) - ord(key(now())) : null;
    if(P && P.exam) bits.push('Exam: ' + human(P.exam) + (left >= 0 ? ' · ' + left + (left === 1 ? ' day' : ' days') : ''));
    if(P && P.minutes) bits.push('about ' + P.minutes + ' minutes a day');
    ex.textContent = bits.join(' · '); ex.style.display = bits.length ? '' : 'none';
  }
  function prompt(){
    return 'Make or change my study plan for this timeline. Ask me one question at a time: when my exam is and how much time I have each day, and what I already know I am weak on. '
      + 'Then propose the nodes I should study first, each with the reason in my own words, and save it with set_study_plan.';
  }
  function make(box){
    var R = window._altoStudyPlanRoutes;
    if(R && typeof R.open === 'function'){ try{ R.open(); return; }catch(e){} }
    if(box.querySelector('.sp-pr')) return;
    var p = el('div', 'sp-pr', 'Paste this to Claude (or open Bass) to make or change your plan:'), ta = el('textarea'); ta.readOnly = true; ta.value = prompt(); ta.onfocus = function(){ ta.select(); };
    p.appendChild(ta); box.appendChild(p);
  }
  function toggle(on){
    var open = on == null ? !sheet.classList.contains('open') : on; sheet.classList.toggle('open', open); if(chip) chip.classList.toggle('open', open); if(open) fill(states());
  }
  function build(){
    sheet = el('div'); sheet.id = 'sp-sheet'; sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-label', 'Study plan');
    sheet.appendChild(el('h3', '', 'Study plan')); sheet.appendChild(el('div', 'sp-ex'));
    var tabs = el('div', 'sp-tabs'); tabs.setAttribute('role', 'tablist');
    [['today', 'Today'], ['week', 'This week']].forEach(function(t){ var b = el('button', '', t[1]); b.type = 'button'; b.setAttribute('role', 'tab'); b.setAttribute('data-t', t[0]); b.onclick = function(){ tab = t[0]; fill(states()); }; tabs.appendChild(b); });
    if(HAS) sheet.appendChild(tabs);
    sheet.appendChild(el('div', 'sp-body'));
    var bt = el('div', 'sp-btns'), mk = el('button', 'sp-btn', 'Make or change my plan'), cl = el('button', 'sp-btn o', 'Close'); mk.type = cl.type = 'button';
    mk.onclick = function(){ make(sheet); }; cl.onclick = function(){ toggle(false); }; bt.appendChild(mk); bt.appendChild(cl); sheet.appendChild(bt);
    sheet.addEventListener('keydown', function(e){ if(e.key === 'Escape') toggle(false); });
    document.body.appendChild(sheet);
    chip = el('button'); chip.id = 'sp-chip'; chip.type = 'button'; chip.onclick = function(){ toggle(); }; document.body.appendChild(chip);
    var list = document.getElementById('notes-list');
    if(list){ row = el('button'); row.id = 'sp-row'; row.type = 'button'; row.appendChild(el('b', '', 'Study plan')); row.appendChild(el('span', '', ''));
      row.onclick = function(){ toggle(); }; list.parentNode.insertBefore(row, list); }
    if(!HAS){ var b = sheet.querySelector('.sp-body'); b.appendChild(el('div', 'sp-none', 'No plan yet. Tell Claude or Bass when your exam is and what you find hard, and it will pick the nodes to study each day.')); }
  }
  function midnight(){
    clearTimeout(timer); var n = now(), nx = new Date(n.getFullYear(), n.getMonth(), n.getDate() + 1, 0, 0, 2);
    timer = setTimeout(function(){ paint(); midnight(); }, Math.min(Math.max(nx - n, 1000), 2147483000));
  }
  /* the cards are drawn after this script runs (the page lays itself out on load; the System draws its discs a little later): paint again then */
  function start(){ build(); paint(); midnight(); window.addEventListener('load', paint); [300, 1200, 3000].forEach(function(ms){ setTimeout(paint, ms); }); }
  window._altoStudyPlan = {paint: paint, states: states};
  window.addEventListener('alto-study-sync', paint); window.addEventListener('storage', function(e){ if(e.key === KEY) paint(); });
  document.addEventListener('visibilitychange', function(){ if(!document.hidden){ paint(); midnight(); } });
  window.addEventListener('resize', function(){ paint(); });
  if(document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
</script>"""


def study_plan_block(brief, nodes) -> str:
    """The plan's data, style and script, ONLY for a page that has a plan that can be drawn: the rings, the day tags, the tab and the sheet.
    A page without one gets nothing (byte-identical to a build before the feature; Luke 2026-11-01 L-1101-222655: the study plan is offered on the
    homepage card and in the interview only)."""
    plan = clean(getattr(brief, "study_plan", None), [n.id for n in nodes])
    if not plan:
        return ""
    hl = ID_PATTERNS["hl_key"].format(tid=brief.timeline_id)
    data = "\n<script id=\"alto-sp-data\">window._ALTO_SP=" + js_json(plan, separators=(",", ":")) + ";</script>"
    return data + "\n" + CSS + "\n" + JS.replace("__ALTO_HL_KEY__", hl) + "\n"
