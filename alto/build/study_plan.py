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
    return {"v": 1, "exam": exam if _day_ok(exam) else "", "items": items}


CSS = r"""<style id="alto-sp-css">
  /* a planned node: one class by the reader's date (study_plan.py). A computer's page only: the phone and its whole view draw nothing */
  html:not(.mobile):not(.phone-whole) .node.sp-today > .node-card{outline:2px solid var(--accent);outline-offset:3px;}
  html:not(.mobile):not(.phone-whole) .node.sp-soon > .node-card{outline:1.5px dashed var(--accent);outline-offset:3px;outline-color:var(--accent);outline-color:color-mix(in srgb,var(--accent) 55%,transparent);}
  html:not(.mobile):not(.phone-whole) .node.sp-late > .node-card{outline:2.5px solid var(--sp-late,#e5484d);outline-offset:3px;}
  html:not(.mobile):not(.phone-whole) .node.sp-done > .node-card{outline:0;}
  html:not(.mobile):not(.phone-whole) .node .sp-tag{position:absolute;top:-12px;right:-6px;z-index:3;padding:2px 7px;font:600 10.5px/1.2 system-ui,-apple-system,sans-serif;letter-spacing:.03em;white-space:nowrap;
    border-radius:9px;background:var(--accent);color:var(--bg);pointer-events:none;}
  html:not(.mobile):not(.phone-whole) .node.sp-soon .sp-tag{background:var(--surface);color:var(--accent);border:1px solid var(--accent);}
  html:not(.mobile):not(.phone-whole) .node.sp-late .sp-tag{background:var(--sp-late,#e5484d);color:#fff;}
  html:not(.mobile):not(.phone-whole) .node.sp-done .sp-tag{background:var(--surface);color:var(--muted);border:1px solid var(--border);}
  html:not(.mobile):not(.phone-whole) .node.sp-go > .node-card{outline:3px solid var(--accent);outline-offset:5px;transition:outline-offset .4s;}
  .sp-tag{display:none;} html:not(.mobile):not(.phone-whole) .sp-tag{display:block;}
  #sp-row{display:none;}
  html:not(.mobile):not(.phone-whole) #sp-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:10px 12px 0;padding:8px 12px;border:1px solid var(--border);border-radius:9px;
    background:var(--surface);color:var(--text);font:inherit;font-size:12.5px;cursor:pointer;text-align:left;}
  html:not(.mobile):not(.phone-whole) #sp-row:hover{border-color:var(--accent);}
  #sp-row b{font-weight:600;} #sp-row span{color:var(--muted);font-size:11.5px;}
  #notes-panel.fw-mode #sp-row{display:none !important;}
  #sp-sheet{display:none;}
  html:not(.mobile):not(.phone-whole) #sp-sheet.open{display:flex;flex-direction:column;position:fixed;top:var(--nav-bottom,115px);right:12px;width:360px;max-height:calc(100vh - var(--nav-bottom,115px) - 24px);z-index:60;
    background:var(--panel-glass-bg,var(--surface));color:var(--text);border:1px solid var(--border);border-radius:12px;box-shadow:0 10px 34px rgba(0,0,0,.28);overflow:hidden;}
  #sp-sheet .sp-hd{display:flex;align-items:center;gap:8px;padding:12px 14px 8px;}
  #sp-sheet .sp-hd h3{margin:0;flex:1;font-size:15px;font-weight:600;}
  #sp-sheet .sp-x{border:0;background:transparent;color:var(--muted);font-size:20px;line-height:1;cursor:pointer;padding:2px 6px;}
  #sp-sheet .sp-sub{padding:0 14px 8px;color:var(--muted);font-size:12px;}
  #sp-sheet .sp-body{flex:1;overflow-y:auto;padding:0 8px 8px;}
  #sp-sheet .sp-g{margin:8px 6px 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
  #sp-sheet .sp-g.late{color:var(--sp-late,#e5484d);}
  #sp-sheet .sp-it{display:flex;gap:9px;align-items:flex-start;padding:7px 8px;border-radius:8px;}
  #sp-sheet .sp-it:hover{background:rgba(127,127,127,.12);}
  #sp-sheet .sp-it input{margin:3px 0 0;flex:none;width:16px;height:16px;accent-color:var(--accent);cursor:pointer;}
  #sp-sheet .sp-t{flex:1;min-width:0;}
  #sp-sheet .sp-go{display:block;padding:0;border:0;background:transparent;color:var(--text);font:inherit;font-size:13px;font-weight:600;text-align:left;cursor:pointer;}
  #sp-sheet .sp-go:hover{color:var(--accent);text-decoration:underline;}
  #sp-sheet .sp-d{font-size:11px;color:var(--muted);} #sp-sheet .sp-w{font-size:12px;color:var(--muted);margin-top:2px;}
  #sp-sheet .sp-it.done .sp-go{text-decoration:line-through;color:var(--muted);}
  #sp-sheet .sp-none{padding:10px 14px;color:var(--muted);font-size:12.5px;}
  #sp-sheet .sp-ft{padding:10px 14px 12px;border-top:1px solid var(--border);}
  #sp-sheet .sp-mk{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:9px;background:var(--surface);color:var(--text);font:inherit;font-size:12.5px;cursor:pointer;}
  #sp-sheet .sp-mk:hover{border-color:var(--accent);}
  #sp-sheet .sp-pr{margin-top:8px;font-size:12px;color:var(--muted);} #sp-sheet .sp-pr textarea{width:100%;box-sizing:border-box;height:84px;margin-top:6px;font:inherit;font-size:12px;
    background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:6px 8px;resize:none;}
  @media print{ .node.sp-today > .node-card,.node.sp-soon > .node-card,.node.sp-late > .node-card,.node.sp-done > .node-card{outline:0 !important;} .sp-tag,#sp-row,#sp-sheet{display:none !important;} }
</style>"""

JS = r"""<script id="alto-sp">
(function(){
  var P = window._ALTO_SP; if(!P || !P.items || !P.items.length) return;
  var KEY = '__ALTO_HL_KEY__-st', SEC = '__plan__', DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var r = document.documentElement, sheet = null, row = null, timer = 0;
  function desk(){ return !r.classList.contains('mobile') && !r.classList.contains('phone-whole') && window.innerWidth > 640; }
  function el(tag, cls, txt){ var e = document.createElement(tag); if(cls) e.className = cls; if(txt != null) e.textContent = txt; return e; }
  function now(){ return window._altoSpNow ? new Date(window._altoSpNow) : new Date(); }
  function key(d){ function z(n){ return n < 10 ? '0' + n : '' + n; } return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()); }
  function ord(s){ var a = s.split('-'); return Date.UTC(+a[0], +a[1] - 1, +a[2]) / 864e5; }
  function human(s){ var a = s.split('-'), d = new Date(+a[0], +a[1] - 1, +a[2]); return DAYS[d.getDay()] + ' ' + MON[d.getMonth()] + ' ' + d.getDate(); }
  /* the reader's ticks: {v:1, s:{__plan__:{m, k:{'node|day':[1 done | 0 cleared, t]}}}}, the study state's own shape (alto-cloud.js merges it) */
  function load(){ try{ var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if(o && o.s && typeof o.s === 'object') return o; }catch(e){} return {v:1, s:{}}; }
  function done(n, d){ var k = (load().s[SEC] || {}).k || {}, v = k[n + '|' + d]; return !!(v && v[0] === 1); }
  function tick(n, d, on){
    var o = load(), s = o.s[SEC] || (o.s[SEC] = {}), k = s.k || (s.k = {}); k[n + '|' + d] = [on ? 1 : 0, Date.now()]; s.m = Date.now();
    try{ localStorage.setItem(KEY, JSON.stringify(o)); }catch(e){}
  }
  /* each item's state today: late (past, not ticked), today, soon (the next three days), later, done */
  function states(){
    var t = ord(key(now()));
    return P.items.map(function(it){
      var dd = ord(it.day) - t, dn = done(it.node, it.day);
      return {it: it, st: dn ? 'done' : dd < 0 ? 'late' : dd === 0 ? 'today' : dd <= 3 ? 'soon' : 'later', dd: dd};
    });
  }
  function tagText(c, S){
    if(c === 'done') return '✓';
    var e = S.filter(function(x){ return x.st === c; }).sort(function(a, b){ return a.dd - b.dd; })[0];
    return c === 'today' ? 'Today' : c === 'late' ? 'Late · ' + human(e.it.day) : human(e.it.day);
  }
  function paint(){
    var S = states(), by = {};
    S.forEach(function(x){ (by[x.it.node] || (by[x.it.node] = [])).push(x); });
    Array.prototype.forEach.call(document.querySelectorAll('.node[class*="sp-"]'), function(n){ n.classList.remove('sp-today', 'sp-soon', 'sp-late', 'sp-done'); var t = n.querySelector('.sp-tag'); if(t) t.remove(); });
    if(!desk()) return;
    Object.keys(by).forEach(function(id){
      var n = document.getElementById('node-' + id); if(!n) return;
      var L = by[id], c = ['late', 'today', 'soon'].filter(function(k){ return L.some(function(x){ return x.st === k; }); })[0] || (L.every(function(x){ return x.st === 'done'; }) ? 'done' : '');
      if(!c) return;
      n.classList.add('sp-' + c);
      var host = n.querySelector('.node-card') || n, tg = el('span', 'sp-tag', tagText(c, L)); tg.setAttribute('aria-hidden', 'true'); host.appendChild(tg);
    });
    summary(S); if(sheet && sheet.classList.contains('open')) fill(S);
  }
  function title(id){ var t = document.querySelector('#node-' + id + ' .node-title'); return t ? t.textContent.trim() : id; }
  function fly(id){
    var n = document.getElementById('node-' + id); if(!n) return;
    try{ n.scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'}); }catch(e){ n.scrollIntoView(); }
    n.classList.add('sp-go'); setTimeout(function(){ n.classList.remove('sp-go'); }, 1600);
  }
  function summary(S){
    if(!row) return;
    var today = S.filter(function(x){ return x.st === 'today'; }).length, late = S.filter(function(x){ return x.st === 'late'; }).length;
    row.querySelector('span').textContent = late ? late + ' late · ' + today + ' today' : today ? today + ' today' : 'nothing due today';
  }
  function item(x){
    var d = el('div', 'sp-it' + (x.st === 'done' ? ' done' : '')), cb = el('input'); cb.type = 'checkbox'; cb.checked = x.st === 'done'; cb.setAttribute('aria-label', 'Done: ' + title(x.it.node));
    cb.onchange = function(){ tick(x.it.node, x.it.day, cb.checked); paint(); };
    var t = el('div', 'sp-t'), g = el('button', 'sp-go', title(x.it.node)); g.type = 'button'; g.onclick = function(){ fly(x.it.node); };
    t.appendChild(g); t.appendChild(el('div', 'sp-d', human(x.it.day))); t.appendChild(el('div', 'sp-w', x.it.why)); d.appendChild(cb); d.appendChild(t); return d;
  }
  function fill(S){
    var b = sheet.querySelector('.sp-body'); b.textContent = '';
    var G = [['late', 'Late', function(x){ return x.st === 'late'; }], ['', 'Today', function(x){ return x.st === 'today' || (x.st === 'done' && x.dd === 0); }],
             ['', 'This week', function(x){ return (x.st === 'soon' || x.st === 'later' || x.st === 'done') && x.dd > 0 && x.dd <= 7; }]], any = false;
    G.forEach(function(g){
      var L = S.filter(g[2]).sort(function(a, c){ return a.dd - c.dd; }); if(!L.length) return; any = true;
      b.appendChild(el('div', 'sp-g ' + g[0], g[1])); L.forEach(function(x){ b.appendChild(item(x)); });
    });
    if(!any) b.appendChild(el('div', 'sp-none', 'Nothing due in the next week.'));
    var ex = sheet.querySelector('.sp-sub'); ex.textContent = P.exam ? 'Exam ' + human(P.exam) + (ord(P.exam) >= ord(key(now())) ? ' · ' + (ord(P.exam) - ord(key(now()))) + ' days' : '') : '';
    ex.style.display = ex.textContent ? '' : 'none';
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
  function build(){
    sheet = el('div'); sheet.id = 'sp-sheet'; sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-label', 'Study plan');
    var hd = el('div', 'sp-hd'), x = el('button', 'sp-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close study plan'); x.onclick = function(){ sheet.classList.remove('open'); };
    hd.appendChild(el('h3', '', 'Study plan')); hd.appendChild(x); sheet.appendChild(hd); sheet.appendChild(el('div', 'sp-sub')); sheet.appendChild(el('div', 'sp-body'));
    var ft = el('div', 'sp-ft'), mk = el('button', 'sp-mk', 'Make or change my plan'); mk.type = 'button'; mk.onclick = function(){ make(ft); }; ft.appendChild(mk); sheet.appendChild(ft);
    sheet.addEventListener('keydown', function(e){ if(e.key === 'Escape') sheet.classList.remove('open'); });
    document.body.appendChild(sheet);
    var list = document.getElementById('notes-list');
    if(list){ row = el('button'); row.id = 'sp-row'; row.type = 'button'; row.appendChild(el('b', '', 'Study plan')); row.appendChild(el('span', '', ''));
      row.onclick = function(){ var open = !sheet.classList.contains('open'); sheet.classList.toggle('open', open); if(open) fill(states()); };
      list.parentNode.insertBefore(row, list); }
  }
  function midnight(){
    clearTimeout(timer); var n = now(), nx = new Date(n.getFullYear(), n.getMonth(), n.getDate() + 1, 0, 0, 2);
    timer = setTimeout(function(){ paint(); midnight(); }, Math.min(Math.max(nx - n, 1000), 2147483000));
  }
  function start(){ build(); paint(); midnight(); }
  window._altoStudyPlan = {paint: paint, states: states};
  window.addEventListener('alto-study-sync', paint); window.addEventListener('storage', function(e){ if(e.key === KEY) paint(); });
  document.addEventListener('visibilitychange', function(){ if(!document.hidden){ paint(); midnight(); } });
  window.addEventListener('resize', function(){ paint(); });
  if(document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
</script>"""


def study_plan_block(brief, nodes) -> str:
    """The plan's data, style and script: "" unless the brief carries a plan with at least one item that can be drawn."""
    plan = clean(getattr(brief, "study_plan", None), [n.id for n in nodes])
    if not plan:
        return ""
    hl = ID_PATTERNS["hl_key"].format(tid=brief.timeline_id)
    return ("\n<script id=\"alto-sp-data\">window._ALTO_SP=" + js_json(plan, separators=(",", ":")) + ";</script>\n" + CSS + "\n" + JS.replace("__ALTO_HL_KEY__", hl) + "\n")
