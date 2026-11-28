"""Chip summaries: one line on a chip (a case) that jogs the memory, printed in ink-saver under the card that carries the chip.

Luke, 2026-11-28: "in ink saver, I want one line summaries of the starred cases included in the node with enough to jog my memory of the
case facts, holding, and reasoning". A summary belongs to the chip (Entity.summary / AxisValue.summary, set by set_chip_summaries); the
outline's and the horizontal timeline's ink-saver print (print_views.flowStage) lists, under each card's chips, one line "★ Name — summary" for
every ★ chip on that card that has one. Print only: the screen is unchanged. A page with no summary gets none of this (byte-identical).
"""
from __future__ import annotations

import json

CSS = "<style id=\"alto-ink-sum-css\">html :is(#alto-ink-host,#alto-ink-measure) .ink-card .ink-sum{margin:2px 0 0 !important;padding:0 !important;font-size:9.5px !important;line-height:1.25 !important;}</style>\n"

# runs in flowStage with `cl` (the card's compact copy) before icon-only chips are dropped
HOOK = ("var SUMS = window._ALTO_CHIPSUM || {}, sl = {};\n"
        "      cl.querySelectorAll('.csym-btn, .esym-btn, .tsym-btn').forEach(function(b){\n"
        "        var nm = b.getAttribute('data-tn') || b.getAttribute('title') || '';\n"
        "        if(SUMS[nm] && !sl[nm] && b.querySelector('.alto-lbl.star')){ sl[nm] = 1; var sx = document.createElement('div'); sx.className = 'ink-sum';\n"
        "          sx.textContent = '\\u2605 ' + nm + ' \\u2014 ' + SUMS[nm]; cl.appendChild(sx); } });")


def table(brief) -> dict:
    """{chip name: summary} for every chip that has one."""
    out = {}
    for e in getattr(brief, "entities", None) or []:
        if (e.summary or "").strip():
            out[e.name] = e.summary.strip()
    for ax in (getattr(brief, "axes", None) or [])[:2]:
        for v in ax.values:
            if (v.summary or "").strip():
                out[v.name] = v.summary.strip()
    return out


def splice(css: str, js: str, brief) -> str:
    t = table(brief) if brief is not None else {}
    if not t:
        return css + js.replace("      @@INKSUM@@\n", "")
    data = "window._ALTO_CHIPSUM=" + json.dumps(t, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";"
    js = js.replace("@@INKSUM@@", HOOK)
    return CSS + css + js.replace('<script id="alto-print-views-js">', '<script id="alto-print-views-js">' + data, 1)
