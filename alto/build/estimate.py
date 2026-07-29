"""Card-height estimator for server-side layout hints.

Calibrated against the 38 real DOM card heights of the frozen Terrarium engine
(tools/calibration_data.json, measured via offsetHeight in Chromium):

    h = BASE + LINE_H * ceil(desc_chars / CPL)

With BASE=98, LINE_H=20, CPL=34.5 the fit has ZERO underestimates and a worst
overestimate of 45px across all 38 cards. The browser-side resolver
(initLayout) re-measures real heights at boot and only ever pushes cards DOWN,
so overestimating is safe (slightly airier page) while underestimating could
bunch the settled layout — hence the added safety margin.
"""
import math

BASE = 98
LINE_H = 20
CPL = 34.5
SAFETY = 8          # px added on top of the calibrated fit
FLOOR = 120         # no card estimates below this
FALLBACK = 260      # matches the engine's own fallback for unmeasurable cards


def card_height(desc: str, title: str = "") -> int:
    desc_len = len(desc or "")
    if desc_len == 0:
        return FLOOR
    h = BASE + LINE_H * math.ceil(desc_len / CPL) + SAFETY
    # Long titles wrap to a second line (~24 chars/line in the 270px card).
    if len(title or "") > 24:
        h += LINE_H
    return max(FLOOR, h)
