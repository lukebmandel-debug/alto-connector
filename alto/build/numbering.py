"""Outline card numbers: a path that says whose child each card is.

A unit's top card is the unit's number ("2"). Below it the levels cycle
letter / .number / .number / -number, and the next letter is written straight
on, so a deep card reads 2.e.6.2-1c.5.4-2:

    2           the unit's top card
    2.e         its 5th child
    2.e.6       the 6th child of 2.e
    2.e.6.2     …
    2.e.6.2-1
    2.e.6.2-1c  letters again, then .n, .n, -n, and so on as deep as it goes

Letters run a..z, aa, ab… The number is derived from the outline (never
stored), so moving or inserting a card renumbers what follows it. Typing a
number on a card (manual edit mode) means "put it there": parse_num() reads
it back into the unit and each level's place. The Python here and the JS in
NUM_JS must agree; tests/test_numbering.py holds them to it.
"""
from __future__ import annotations

import re


def letters(i: int) -> str:
    """0 → a, 25 → z, 26 → aa (bijective base 26)."""
    s, i = "", i + 1
    while i > 0:
        i, m = divmod(i - 1, 26)
        s = chr(97 + m) + s
    return s


def seg(depth: int, i: int) -> str:
    """The mark for the i-th (0-based) child at `depth` below the unit's top card."""
    c = (depth - 1) % 4
    if c == 0:
        return ("." if depth == 1 else "") + letters(i)
    return ("-" if c == 3 else ".") + str(i + 1)


def path_numbers(seqs: list, kids: dict, parent: dict) -> dict:
    """id → number. seqs = each unit's card ids in reading order (ACT_SEQS);
    kids = parent id → child ids in order; parent = child id → parent id. A
    card whose parent is in another unit counts as a top card of its own unit;
    a unit with more than one top card numbers them as if under one (2.a, 2.b)."""
    out: dict = {}
    for a, q in enumerate(seqs):
        in_q = set(q)
        roots = [i for i in q if not (parent.get(i) and parent[i] in in_q)]
        seen: set = set()

        def walk(x, pre, d):
            if x in seen:
                return
            seen.add(x)
            out[x] = pre
            for j, k in enumerate([k for k in kids.get(x, []) if k in in_q]):
                walk(k, pre + seg(d + 1, j), d + 1)

        if len(roots) == 1:
            walk(roots[0], str(a + 1), 0)
        else:
            for j, r in enumerate(roots):
                walk(r, str(a + 1) + seg(1, j), 1)
    return out


_TOK = re.compile(r"\.?([a-z]+)|[.\-](\d+)")


def parse_num(s: str):
    """'2.e.6.2-1c' → (2, [4, 5, 1, 0, 2]) — the unit (1-based) and each
    level's place (0-based) — or None when it is not a number of this shape.
    Separators are forgiven; a level's kind (letters or digits) is not."""
    s = re.sub(r"[.\s]+$", "", str(s or "").strip().lower())
    m = re.match(r"^(\d+)(.*)$", s)
    if not m:
        return None
    unit, rest, idx, d = int(m.group(1)), m.group(2), [], 0
    while rest:
        t = _TOK.match(rest)
        if not t:
            return None
        d += 1
        want_letters = (d - 1) % 4 == 0
        if t.group(1) is not None:
            if not want_letters:
                return None
            v = 0
            for ch in t.group(1):
                v = v * 26 + (ord(ch) - 96)
            idx.append(v - 1)
        else:
            if want_letters or int(t.group(2)) < 1:
                return None
            idx.append(int(t.group(2)) - 1)
        rest = rest[t.end():]
    if unit < 1:
        return None
    return unit, idx


def format_num(unit: int, idx: list) -> str:
    return str(unit) + "".join(seg(d + 1, i) for d, i in enumerate(idx))


# The same three, for the page (manual edit mode renumbers live).
NUM_JS = r"""
window._altoNumSeg = function(d, i){
  var c = (d - 1) % 4;
  if(c === 0){ var s = '', n = i + 1; while(n > 0){ var m = (n - 1) % 26; s = String.fromCharCode(97 + m) + s; n = Math.floor((n - 1) / 26); } return (d === 1 ? '.' : '') + s; }
  return (c === 3 ? '-' : '.') + (i + 1);
};
window._altoPathNums = function(seqs, K, P){
  var out = {}, seg = window._altoNumSeg;
  seqs.forEach(function(q, a){
    var inQ = {}, seen = {}; q.forEach(function(i){ inQ[i] = 1; });
    var roots = q.filter(function(i){ return !(P[i] && inQ[P[i]]); });
    function walk(x, pre, d){ if(seen[x]) return; seen[x] = 1; out[x] = pre;
      (K[x] || []).filter(function(k){ return inQ[k]; }).forEach(function(k, j){ walk(k, pre + seg(d + 1, j), d + 1); }); }
    if(roots.length === 1) walk(roots[0], String(a + 1), 0);
    else roots.forEach(function(r, j){ walk(r, String(a + 1) + seg(1, j), 1); });
  });
  return out;
};
window._altoParseNum = function(s){
  s = String(s || '').trim().toLowerCase().replace(/[.\s]+$/, '');
  var m = /^(\d+)(.*)$/.exec(s); if(!m) return null;
  var unit = +m[1], rest = m[2], idx = [], d = 0, re = /^(?:\.?([a-z]+)|[.\-](\d+))/;
  while(rest){
    var t = re.exec(rest); if(!t) return null;
    d++; var wantL = (d - 1) % 4 === 0;
    if(t[1] != null){ if(!wantL) return null; var v = 0; for(var k = 0; k < t[1].length; k++) v = v * 26 + (t[1].charCodeAt(k) - 96); idx.push(v - 1); }
    else { if(wantL || +t[2] < 1) return null; idx.push(+t[2] - 1); }
    rest = rest.slice(t[0].length);
  }
  return unit < 1 ? null : {unit: unit, idx: idx};
};
window._altoFormatNum = function(unit, idx){ return String(unit) + idx.map(function(i, d){ return window._altoNumSeg(d + 1, i); }).join(''); };
"""
