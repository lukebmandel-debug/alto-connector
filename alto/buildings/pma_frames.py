"""The PMA's "labelled frames" (Luke 2026-10-29, option A): every work in the wall table (pma_wall.json) hangs in its gallery as a framed canvas with a museum label.

`merge(plan)` is what `pma.plan()` runs on its fresh copy of the plan. For each wall-table row of kind "painting":
  * a plan slot that already exists (sl-<key>) keeps its place and gets the frame fields;
  * a row with no slot yet (the works named in a cited review of the reinstalled galleries) is hung on a free stretch of wall in its room, clear of doors and corners.
Frame fields written on the slot (`fr`: the renderer paints the Labelled-frame look only for slots that have it):
  fr  "g" warm gilt moulding (work dated before 1900) | "w" dark walnut (1900 onward)
  lb  where the label hangs: "r" right of the frame, "l" left of it, "b" below it (when neither side has room or solid wall behind it)
  lu  (phone only, optional) how far the centred label below the frame slides (m, viewer's right) to stay on solid wall
  work.lic  "pd" (the real picture hangs once /bart/ serves it; until then the empty canvas) | anything else: the empty canvas only; work.cl  the credit line of a hung picture.
A work is never given an image here; `work.img` stays what the plan or pma_art.json says (see pma_wall.json for the licence rule).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALL = HERE / "pma_wall.json"

PLATE_W = 0.50          # the label plate's width (m); the renderer's FR.PW
PHONE_PW = 0.625        # the same plate on a phone (1.25x)
GAP = 0.10              # frame edge to label
CLEAR = 0.40            # least clearance from a door or a corner (spec: 40 cm)
BETWEEN = 0.12          # least air between one work's extent and the next
ASSUMED_LONG = 0.85     # long side (m) of a work whose size is not in the sources used


def slot_id(key: str) -> str:
    """The plan's slot id for a wall-table key (a plan id token is at most 32 characters)."""
    return ("sl-" + key)[:32].rstrip("-")


def wall_rows() -> list:
    return json.loads(WALL.read_text(encoding="utf-8"))["rows"]


def _year(text) -> int | None:
    m = re.search(r"\d{4}", str(text or ""))
    return int(m.group(0)) if m else None


def _size(row: dict) -> tuple:
    px = row.get("px")
    if px:
        asp = px[0] / px[1]
        w, h = (ASSUMED_LONG, ASSUMED_LONG / asp) if asp >= 1 else (ASSUMED_LONG * asp, ASSUMED_LONG)
        return round(w, 3), round(h, 3), "size assumed (the catalogued size is not in the sources used); proportions from the Commons file"
    return 0.62, 0.78, "size and proportions assumed (neither is in the sources used)"


def _opening_points(plan: dict, level: str) -> list:
    out = []
    for w in plan["wl"]:
        if w["l"] != level:
            continue
        pts = w["p"] + ([w["p"][0]] if w.get("loop") else [])
        segs = []
        tot = 0.0
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            segs.append((a, b, L, tot))
            tot += L
        for o in w.get("o", []):
            t = o["a"]
            for a, b, L, t0 in segs:
                if L > 0 and t0 <= t <= t0 + L + 1e-9:
                    f = (t - t0) / L
                    out.append(((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), o["w"] / 2))
                    break
    return out


def _edges(room: dict) -> list:
    poly = room["p"]
    ccw = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) > 0
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1.0:
            continue
        dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = (-dy, dx) if ccw else (dy, -dx)                      # into the room
        d = (-n[1], n[0])                                        # the viewer's right (the renderer's `d`)
        out.append({"a": a, "dir": (dx, dy), "n": n, "d": d, "L": L, "s": dx * d[0] + dy * d[1]})
    return out


def _u(p, e) -> float:
    """Position of point p along the edge, in the viewer's-right direction (so a larger u is to the right)."""
    return (p[0] - e["a"][0]) * e["d"][0] + (p[1] - e["a"][1]) * e["d"][1]


def _on_edge(s: dict, e: dict) -> bool:
    px, py = s["p"][0] - e["a"][0], s["p"][1] - e["a"][1]
    off = px * e["n"][0] + py * e["n"][1]
    along = px * e["dir"][0] + py * e["dir"][1]
    fc = math.radians(s.get("fc", 0))
    return abs(off - 0.05) < 0.2 and -0.01 <= along <= e["L"] + 0.01 and (math.cos(fc) * e["n"][0] + math.sin(fc) * e["n"][1]) > 0.95


def _wall_segs(plan: dict, level: str) -> list:
    out = []
    for w in plan["wl"]:
        if w["l"] != level or w.get("k") == "rail":
            continue
        pts = w["p"] + ([w["p"][0]] if w.get("loop") else [])
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L > 0:
                out.append((a, b, L, (w.get("t") or 0.2) / 2 + 0.5))
    return out


def _solid(segs: list, e: dict, lo: float, hi: float) -> bool:
    """True when a plate spanning lo..hi (viewer's-right coordinate along edge e) has wall behind its whole width, ends and middle."""
    for u in (lo, (lo + hi) / 2, hi):
        t = u * e["s"]
        px, py = e["a"][0] + e["dir"][0] * t, e["a"][1] + e["dir"][1] * t
        if not any(_behind(sg, px, py) for sg in segs):
            return False
    return True


def _behind(sg: tuple, px: float, py: float) -> bool:
    a, b, L, tol = sg
    along = ((px - a[0]) * (b[0] - a[0]) + (py - a[1]) * (b[1] - a[1])) / L
    off = abs((px - a[0]) * (b[1] - a[1]) - (py - a[1]) * (b[0] - a[0])) / L
    return -0.01 <= along <= L + 0.01 and off <= tol


def merge(plan: dict, unplaced: list | None = None) -> dict:
    rows = [r for r in wall_rows() if r.get("kind") == "painting"]
    from .pma_art import manifest
    hosted = manifest()["images"]
    rooms = {r["id"]: r for r in plan["rm"]}
    by_id = {s["id"]: s for s in plan["sl"]}
    doors = {}
    walls = {}
    for r in rows:
        s = by_id.get(slot_id(r["key"]))
        if s is None:
            r["_new"] = True
            continue
        _frame_fields(s, r)
    unplaced = [] if unplaced is None else unplaced
    for rid in sorted({r["rm"] for r in rows if r.get("_new")}):
        room = rooms[rid]
        edges = _edges(room)
        lv = room["l"]
        doors.setdefault(lv, _opening_points(plan, lv))
        # what already hangs on each edge: (u0, u1) occupied stretches, label included
        taken = [[] for _ in edges]
        for s in plan["sl"]:
            if s["rm"] != rid or "sz" not in s:
                continue
            for i, e in enumerate(edges):
                if _on_edge(s, e):
                    u = _u(s["p"], e)
                    right = GAP + PLATE_W if s.get("fr") else 0.3
                    taken[i].append((u - s["sz"][0] / 2 - BETWEEN, u + s["sz"][0] / 2 + right + BETWEEN))
        for i, e in enumerate(edges):                            # doors and corners
            u0, u1 = _u(e["a"], e), _u((e["a"][0] + e["dir"][0] * e["L"], e["a"][1] + e["dir"][1] * e["L"]), e)
            lo, hi = min(u0, u1), max(u0, u1)
            taken[i].append((lo - 9, lo + CLEAR))
            taken[i].append((hi - CLEAR, hi + 9))
            for c, hw in doors[lv]:
                off = (c[0] - e["a"][0]) * e["n"][0] + (c[1] - e["a"][1]) * e["n"][1]
                along = (c[0] - e["a"][0]) * e["dir"][0] + (c[1] - e["a"][1]) * e["dir"][1]
                if abs(off) < 0.45 and -0.5 <= along <= e["L"] + 0.5:
                    uc = _u(c, e)
                    taken[i].append((uc - hw - CLEAR, uc + hw + CLEAR))
        for r in [x for x in rows if x["rm"] == rid and x.get("_new")]:
            W, H, sr = _size(r)
            need = W + 2 * BETWEEN + GAP + PLATE_W
            spot = None
            order = sorted(range(len(edges)), key=lambda i: -edges[i]["L"])
            for i in order:
                e = edges[i]
                u0, u1 = sorted((_u(e["a"], e), _u((e["a"][0] + e["dir"][0] * e["L"], e["a"][1] + e["dir"][1] * e["L"]), e)))
                u = u0 + CLEAR + BETWEEN + W / 2
                while u + W / 2 + GAP + PLATE_W + BETWEEN <= u1 - CLEAR + 1e-9:
                    ext = (u - W / 2 - BETWEEN, u + W / 2 + GAP + PLATE_W + BETWEEN)
                    hit = [t for t in taken[i] if t[0] < ext[1] and ext[0] < t[1]]
                    if not hit:
                        spot = (i, u, ext)
                        break
                    u = max(t[1] for t in hit) + BETWEEN + W / 2
                if spot:
                    break
            if not spot:
                unplaced.append({"key": r["key"], "rm": rid, "why": "no free stretch of wall in the room"})
                continue
            i, u, ext = spot
            e = edges[i]
            taken[i].append(ext)
            t = u * e["s"]                                         # u is measured from the edge's start along the viewer's right, so the distance along the edge is u * s (s = +-1)
            p = (e["a"][0] + e["dir"][0] * t + e["n"][0] * 0.05, e["a"][1] + e["dir"][1] * t + e["n"][1] * 0.05)
            s = {"id": slot_id(r["key"]), "rm": rid, "p": [round(p[0], 2), round(p[1], 2)], "z": round(max(1.5, H / 2 + 0.35), 2), "sz": [W, H],
                 "fc": round(math.degrees(math.atan2(e["n"][1], e["n"][0])) % 360, 1), "al": ["painting"], "pc": r["pc"], "c": 1 if r["pc"] == "room" else 0,
                 "s": ["pma-map", "est"] + (["commons-art"] if r.get("img") else []), "gl": r["gl"], "sr": sr, "sb": "assumed",
                 "work": {"title": r["title"], "artist": r["artist"], "date": r["year"], "credit": "Philadelphia Museum of Art" + (f" (object {r['source'].rsplit('/', 1)[-1]})" if r.get("source") else ""),
                          "pma_url": r.get("source") or "https://www.philamuseum.org/visit/museum-map"}}
            if r.get("img") in hosted:
                s["work"]["img"] = hosted[r["img"]]["url"]
            plan["sl"].append(s)
            by_id[s["id"]] = s
            _frame_fields(s, r)
    # every framed slot: where its label hangs (right when there is room for it, else left, else below)
    for rid in {s["rm"] for s in plan["sl"] if s.get("fr")}:
        edges = _edges(rooms[rid])
        for s in plan["sl"]:
            if s["rm"] != rid or not s.get("fr"):
                continue
            s["lb"] = "b"
            for i, e in enumerate(edges):
                if not _on_edge(s, e):
                    continue
                u = _u(s["p"], e)
                u0, u1 = sorted((_u(e["a"], e), _u((e["a"][0] + e["dir"][0] * e["L"], e["a"][1] + e["dir"][1] * e["L"]), e)))
                hw = s["sz"][0] / 2
                right_ok = u + hw + GAP + PLATE_W <= u1 - CLEAR + 1e-6
                left_ok = u - hw - GAP - PLATE_W >= u0 + CLEAR - 1e-6
                segs = walls.setdefault(rooms[rid]["l"], _wall_segs(plan, rooms[rid]["l"]))
                if _solid(segs, e, u, u) and not _solid(segs, e, u - hw, u + hw):                           # the frame itself hangs past a wall's end: slide it back onto the wall
                    for k in range(1, 27):
                        sh = next((x for x in (-k * 0.05, k * 0.05) if _solid(segs, e, u + x - hw, u + x + hw)), None)
                        if sh is not None:
                            s["p"] = [round(s["p"][0] + e["dir"][0] * sh * e["s"], 2), round(s["p"][1] + e["dir"][1] * sh * e["s"], 2)]
                            u += sh
                            break
                on_wall = _solid(segs, e, u, u)                                                            # a frame with no wall data behind it (open galleries) keeps the old rule
                if on_wall and right_ok and not _solid(segs, e, u + hw + GAP, u + hw + GAP + PLATE_W):     # the plate would hang in an opening or past a wall's end
                    right_ok = False
                if on_wall and left_ok and not _solid(segs, e, u - hw - GAP - PLATE_W, u - hw - GAP):
                    left_ok = False
                for o in plan["sl"]:
                    if o is s or o["rm"] != rid or "sz" not in o or not _on_edge(o, e):
                        continue
                    ou = _u(o["p"], e)
                    if ou > u and ou - o["sz"][0] / 2 < u + hw + GAP + PLATE_W + 0.05:
                        right_ok = False
                    if ou < u and ou + o["sz"][0] / 2 > u - hw - GAP - PLATE_W - 0.05:
                        left_ok = False
                for c, dh in doors.setdefault(rooms[rid]["l"], _opening_points(plan, rooms[rid]["l"])):
                    off = (c[0] - e["a"][0]) * e["n"][0] + (c[1] - e["a"][1]) * e["n"][1]
                    along = (c[0] - e["a"][0]) * e["dir"][0] + (c[1] - e["a"][1]) * e["dir"][1]
                    if abs(off) < 0.45 and -0.5 <= along <= e["L"] + 0.5:
                        uc = _u(c, e)
                        if uc > u and uc - dh - CLEAR < u + hw + GAP + PLATE_W:
                            right_ok = False
                        if uc < u and uc + dh + CLEAR > u - hw - GAP - PLATE_W:
                            left_ok = False
                s["lb"] = "r" if right_ok else "l" if left_ok else "b"
                s.pop("lu", None)
                half = PHONE_PW / 2                                                                         # the phone hangs the label below, centred: slide it onto solid wall when the centre has none
                if on_wall and not _solid(segs, e, u - half, u + half):
                    for k in range(1, int(hw / 0.05) + 1):
                        sh = next((x for x in (-k * 0.05, k * 0.05) if _solid(segs, e, u + x - half, u + x + half)), None)
                        if sh is not None:
                            s["lu"] = round(sh, 2)
                            break
                break
    return plan


def _frame_fields(s: dict, r: dict) -> None:
    y = _year(r.get("year")) or _year(s.get("work", {}).get("date"))
    s["fr"] = "w" if (y or 0) >= 1900 else "g"
    w = s["work"]
    w["lic"] = r["lic"]
    if r["lic"] == "pd" and r.get("img"):
        w["cl"] = "Public domain, via Wikimedia Commons"
    elif r["lic"] != "pd":
        w.pop("img", None)                                        # only a public-domain row hangs a picture
