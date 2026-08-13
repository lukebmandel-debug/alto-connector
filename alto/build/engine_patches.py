"""Recorded fixes applied to the emitted engine HTML.

`engine/timeline_template.html` and `engine/FROZEN/` stay byte-faithful to the
pinned upstream engine — that is what tests/test_roundtrip.py proves, and the
proof is worth keeping. Engine bugs found downstream are therefore fixed here:
one explicit old→new string per bug, applied to the emitted page, each with an
expected hit count so a future engine refresh that moves the anchor fails the
build loudly instead of silently dropping the fix.

Same discipline as hosted.py's `_rep`. Each entry carries the symptom, so a
patch can be retired the moment upstream fixes it.
"""
from __future__ import annotations


class PatchError(RuntimeError):
    pass


# ── merge-flag overshoot ─────────────────────────────────────────────────────
# When a connection has no clear corridor, the router lets it *ride* another
# line's horizontal (tryMerge), then paints the host's colour back onto the
# bottom half of the guest's tube so both are readable. That overlay spans
# `mergedRide.x1..x2`, which come from corner CENTRES, while the tube it
# overlays runs straight only between the corner ARCS (inset by `r`). The
# difference draws as a bare stub jutting past the curve into open space —
# visible on any timeline where two relations of different colours share a
# lane. Clamp the overlay to the straight run both tubes actually share.
_MERGE_FLAG_OLD = """        if(mergedRide && mergedRide.host.color && mergedRide.host.color !== tubeColor && (mergedRide.x2 - mergedRide.x1) > 8){
          var flag = document.createElementNS(NS,'path');
          flag.setAttribute('d', 'M ' + mergedRide.x1 + ' ' + (midY + tubeW/4) +
                                 ' L ' + mergedRide.x2 + ' ' + (midY + tubeW/4));"""

_MERGE_FLAG_NEW = """        var _mfLo = mergedRide ? mergedRide.x1 : 0, _mfHi = mergedRide ? mergedRide.x2 : 0;
        if(mergedRide){
          // Ends that sit on a corner centre (either tube's) are inside an arc,
          // where neither tube runs straight — pull them in by the arc radius so
          // the overlay stops with the curve instead of jutting past it.
          var _mfCorners = [sx, tx, mergedRide.host.x1, mergedRide.host.x2];
          var _mfAtCorner = function(x){
            for(var _ci = 0; _ci < _mfCorners.length; _ci++){
              if(typeof _mfCorners[_ci] === 'number' && Math.abs(x - _mfCorners[_ci]) < 1) return true;
            }
            return false;
          };
          if(_mfAtCorner(_mfLo)) _mfLo += r;
          if(_mfAtCorner(_mfHi)) _mfHi -= r;
        }
        if(mergedRide && mergedRide.host.color && mergedRide.host.color !== tubeColor && (_mfHi - _mfLo) > 8){
          var flag = document.createElementNS(NS,'path');
          flag.setAttribute('d', 'M ' + _mfLo + ' ' + (midY + tubeW/4) +
                                 ' L ' + _mfHi + ' ' + (midY + tubeW/4));"""

PATCHES = [
    {
        "name": "merge-flag-overshoot",
        "old": _MERGE_FLAG_OLD,
        "new": _MERGE_FLAG_NEW,
        "count": 1,
    },
]


def apply_patches(html: str) -> str:
    for p in PATCHES:
        found = html.count(p["old"])
        if found != p["count"]:
            raise PatchError(
                f"engine patch {p['name']!r}: anchor matched {found} times, "
                f"expected {p['count']} — the engine moved under it; re-derive "
                "the patch against the current template or retire it")
        html = html.replace(p["old"], p["new"])
    return html
