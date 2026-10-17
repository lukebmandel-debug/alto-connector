"""Claiming a background building (fill-in, palace_fillin.py) as one of the user's own building nodes.

In edit mode's "+ Add building", pointing at a simulated (white) building outlines it and a click makes the new node stand
on that footprint: the node's block (palace.py nbDraw) is the footprint's polygon lifted by the node's height, not a rectangle.
The node keeps its OWN copy of the footprint — the fill-in is regenerated whenever the city is set up again — in its
placement hint (brief.placement[id]["shape"], next to "lot"):

    {"x": cx, "y": cy, "a": deg, "w": w, "h": h, "r": [[dx, dy], ...]}

x, y: the centre of the footprint's box turned by `a` degrees (the box is its lot: w x h, as a lot [cx, cy, w, h, deg] is); r: the
ring in page px relative to that centre (3-40 whole-number points, clockwise on the screen). The page gets the lot as the usual
5 numbers plus the ring ([cx, cy, w, h, deg, ring]) in one more block appended after the towers' (tower_lots), so every lot key
("<block>.0"), the street routes, the card, the hit box and the fill-in clearing work from the box. A "lot" next to a "shape" is
ignored. The phone's map draws the same polygon (it draws with nbDraw too).
"""
from __future__ import annotations

import math

MIN_PTS, MAX_PTS = 3, 40
MAX_SIDE = 600.0                  # page px: the longest side of a footprint's box (a block is ~100-200)
MIN_SIDE = 3.0
MAX_XY = 200_000.0
MAX_R = 700                       # |dx|, |dy| of a ring point


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_shape(v, where="shape") -> dict:
    """A claimed footprint, validated and made canonical (whole-number ring, clockwise) -> a new dict. Raises BriefError."""
    if not isinstance(v, dict) or set(v) - {"x", "y", "a", "w", "h", "r"}:
        raise _err(f"{where}: an object {{x, y, a, w, h, r}} (the footprint's centre, angle, box and ring)")
    for k in ("x", "y", "w", "h"):
        if not _num(v.get(k)):
            raise _err(f"{where}: {k} must be a number")
    a = v.get("a", 0)
    if not _num(a) or not -90 <= a <= 90:
        raise _err(f"{where}: a (degrees) must be a number from -90 to 90")
    if not (abs(v["x"]) <= MAX_XY and abs(v["y"]) <= MAX_XY):
        raise _err(f"{where}: x, y are page px")
    if not (MIN_SIDE <= v["w"] <= MAX_SIDE and MIN_SIDE <= v["h"] <= MAX_SIDE):
        raise _err(f"{where}: the box w x h must be {MIN_SIDE:g} to {MAX_SIDE:g} px a side")
    r = v.get("r")
    if not isinstance(r, list) or not MIN_PTS <= len(r) <= MAX_PTS:
        raise _err(f"{where}: r is a list of {MIN_PTS} to {MAX_PTS} [x, y] points")
    ring = []
    for q in r:
        if (not isinstance(q, (list, tuple)) or len(q) != 2 or not all(_num(c) for c in q)
                or any(abs(c) > MAX_R or c != int(c) for c in q)):
            raise _err(f"{where}: each point of r is [x, y], whole numbers within {MAX_R} px of the centre")
        ring.append([int(q[0]), int(q[1])])
    area2 = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring)))
    if area2 == 0:
        raise _err(f"{where}: r has no area")
    if area2 < 0:
        ring.reverse()                               # clockwise on the screen (y down), as the page's walls are picked
    co, si = math.cos(math.radians(-a)), math.sin(math.radians(-a))
    for x, y in ring:                                # the ring lies inside its box (turned by a)
        u, w_ = x * co - y * si, x * si + y * co
        if abs(u) > v["w"] / 2 + 1.5 or abs(w_) > v["h"] / 2 + 1.5:
            raise _err(f"{where}: r reaches outside the box w x h turned by a")
    return {"x": round(v["x"], 1), "y": round(v["y"], 1), "a": round(a, 1), "w": round(v["w"], 1), "h": round(v["h"], 1), "r": ring}


def lot_of(shape: dict) -> list:
    """The lot a claimed footprint stands on: [cx, cy, w, h, deg, ring]."""
    return [shape["x"], shape["y"], shape["w"], shape["h"], shape["a"], shape["r"]]


def claimed(placement, roots) -> dict:
    """{building id: clean shape} for the placement hints that carry a valid footprint (a building, not a floor)."""
    out = {}
    for nid, h in (placement or {}).items():
        if nid in roots and isinstance(h, dict) and h.get("shape"):
            try:
                out[nid] = check_shape(h["shape"])
            except Exception:                        # noqa: BLE001 — a bad one is reported by validate_brief; the page ignores it
                pass
    return out


def claim_lots(blocks: list, claims: dict, at: dict) -> list:
    """One more block per claimed footprint (after the towers'), one lot each; at[id] points to it."""
    if not claims:
        return blocks
    blocks = list(blocks)
    for nid in sorted(claims):
        lt = lot_of(claims[nid])
        bid = len(blocks)
        blocks.append({"id": bid, "lots": [lt]})
        at[nid] = f"{bid}.0"
    return blocks


def migrate_shapes(old_pal: dict, new_pal: dict, placement: dict) -> dict:
    """A city set up again: each claimed footprint moves with the real place under its centre (like a saved lot); one that
    cannot be carried over is dropped (the building is placed afresh)."""
    from . import palace_place as pp
    from .palace import unpack
    todo = [v for v in placement.values() if isinstance(v, dict) and v.get("shape")]
    if not todo:
        return placement
    try:
        od, nd = unpack(old_pal["data_z"]), unpack(new_pal["data_z"])
        om, nm = dict(od["map"], bbox=old_pal.get("bbox")), dict(nd["map"], bbox=new_pal.get("bbox"))
    except Exception:                                # noqa: BLE001
        om = nm = None
    for v in todo:
        s = v["shape"]
        try:
            rp = pp.real_of(om, s["x"], s["y"]) if om else None
            if rp is None:
                raise ValueError
            px, py = pp.page_of(nm, *rp) if nm.get("doms") else pp.to_px_real(nm, *rp)
            v["shape"] = {**s, "x": round(px, 1), "y": round(py, 1)}
        except Exception:                            # noqa: BLE001
            v.pop("shape", None)
    return placement


# ── the page ────────────────────────────────────────────────────────────────
CLAIM_FUNCS = r"""
function clmSh(){ if(!P.sh){ P.sh={}; P.shk={}; for(var k in P.pl0) if(P.pl0[k].shape){ P.sh[k]=P.pl0[k].shape; P.shk[k]=P.at[k]; } } return P.sh; }
function clmLot(s){ return [s.x, s.y, s.w, s.h, s.a, s.r]; }
function clmAbs(L){ var o=[], a=(L[4]||0)*Math.PI/180, c=Math.cos(a), s=Math.sin(a);
  (L[5]||[[-1,-1],[1,-1],[1,1],[-1,1]].map(function(q){ return [q[0]*L[2]/2*c-q[1]*L[3]/2*s, q[0]*L[2]/2*s+q[1]*L[3]/2*c]; })).forEach(function(q){ o.push(L[0]+q[0], L[1]+q[1]); }); return o; }
function clmIn(p,x,y){ for(var a=0,n=p.length,j=n-2,c=false;a<n;j=a,a+=2) if((p[a+1]>y)!==(p[j+1]>y) && x<p[a]+(y-p[a+1])*(p[j]-p[a])/(p[j+1]-p[a+1])) c=!c; return c; }
function clmSd(x,y,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, d=dx*dx+dy*dy, t=d?Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/d)):0; return Math.hypot(ax+t*dx-x, ay+t*dy-y); }
/* two polygons (flat x,y lists) overlap or come within g px: each one's corners and edge middles against the other */
function clmNear(A,B,g){ return clmHit(A,B,g) || clmHit(B,A,g); }
function clmHit(A,B,g){ for(var i=0,n=A.length,m=B.length;i<n;i+=2){ var j=(i+2)%n, X=A[i], Y=A[i+1];
    for(var t=0;t<2;t++){ if(clmIn(B,X,Y)) return true; for(var k=0,k2=m-2;g && k<m;k2=k,k+=2) if(clmSd(X,Y,B[k2],B[k2+1],B[k],B[k+1])<g) return true; X=(X+A[j])/2; Y=(Y+A[j+1])/2; } }
  return false; }
function clmRing(L,cls,parent){ var p=clmAbs(L), d=''; for(var i=0;i<p.length;i+=2) d+=(i?'L':'M')+p[i].toFixed(1)+' '+p[i+1].toFixed(1); return el('path',{'class':cls, d:d+'Z'},parent); }
function clmCut(x,L){ var p=clmAbs(L); x.beginPath(); x.moveTo(p[0],p[1]); for(var i=2;i<p.length;i+=2) x.lineTo(p[i],p[i+1]); x.closePath(); x.fill(); x.lineWidth=16; x.lineJoin='round'; x.stroke(); x.beginPath(); }
function clmShape(s){ if(s._cl) return s._cl; var q=[], p=s.p, i, k=Math.ceil(p.length/80);
  for(i=0;i<p.length;i+=2*k) q.push([p[i],p[i+1]]);
  var best=0,ba=0; for(i=0;i<q.length;i++){ var j=(i+1)%q.length, d=Math.hypot(q[j][0]-q[i][0],q[j][1]-q[i][1]); if(d>best){ best=d; ba=Math.atan2(q[j][1]-q[i][1],q[j][0]-q[i][0])*180/Math.PI; } }
  ba=((ba%90)+135)%90-45; var r=ba*Math.PI/180, c=Math.cos(-r), sn=Math.sin(-r), u0=1e9,u1=-1e9,v0=1e9,v1=-1e9;
  q.forEach(function(t){ var u=t[0]*c-t[1]*sn, v=t[0]*sn+t[1]*c; u0=Math.min(u0,u); u1=Math.max(u1,u); v0=Math.min(v0,v); v1=Math.max(v1,v); });
  var mu=(u0+u1)/2, mv=(v0+v1)/2, cx=mu*Math.cos(r)-mv*Math.sin(r), cy=mu*Math.sin(r)+mv*Math.cos(r), ring=q.map(function(t){ return [Math.round(t[0]-cx), Math.round(t[1]-cy)]; }), a2=0;
  ring.forEach(function(t,i){ var n=ring[(i+1)%ring.length]; a2+=t[0]*n[1]-n[0]*t[1]; }); if(a2<0) ring.reverse();
  return s._cl={x:Math.round(cx*10)/10, y:Math.round(cy*10)/10, a:Math.round(ba*10)/10, w:Math.round((u1-u0)*10)/10, h:Math.round((v1-v0)*10)/10, r:ring}; }
function clmBusy(sh){ var A=clmAbs(clmLot(sh)), bad=false;
  Object.keys(P.at).forEach(function(id){ var L=lot(P.at[id]); if(!bad && L && Math.abs(L[0]-sh.x)<L[2]+sh.w+20 && Math.abs(L[1]-sh.y)<L[3]+sh.h+20) bad=clmNear(A, clmAbs(L), 0); });
  return bad; }
function clmAt(p){
  if(!addMode || typeof fillGroups!=='function' || !FILL || fillLevel<1 || !editing()) return null;
  var G=fillGroups(), CH=FILL.ch, ci=Math.floor(p[0]/CH[0]), cj=Math.floor(p[1]/CH[1]), best=null, ba=1e18;
  for(var lv=1;lv<=fillLevel && lv<=4;lv++){ if(Z<FILL_ZMIN[lv] || !G[lv]) continue;
    for(var di=-1;di<=1;di++) for(var dj=-1;dj<=1;dj++){ var C=G[lv][(ci+di)+','+(cj+dj)]; if(!C) continue;
      for(var u in C.u) C.u[u].forEach(function(s){ var b=s.b, a=(b[2]-b[0])*(b[3]-b[1]); if(a<ba && p[0]>b[0] && p[0]<b[2] && p[1]>b[1] && p[1]<b[3] && clmIn(s.p,p[0],p[1])){ ba=a; best=s; } }); } }
  if(!best) return null; var sh=clmShape(best); return (sh.w<3 || sh.h<3 || clmBusy(sh))?null:{key:'c'+sh.x+','+sh.y, cl:sh, L:clmLot(sh), by:null}; }
function clmField(id){ return {kind:'card', sig:function(){ var h=(P.pl0||{})[id]; return h&&h.shape?h.shape:null; }, get:function(){ return clmSh()[id]||null; },
  set:function(v){ var S=clmSh(), k=P.shk[id]; if(k) P.b[+k.split('.')[0]]=[]; delete S[id]; delete P.shk[id]; delete P.at[id];
    if(v){ S[id]=v; P.b.push([clmLot(v)]); P.at[id]=P.shk[id]=(P.b.length-1)+'.0'; } P._dirty=1; }}; }
"""

CLAIM_CSS = ""

_FILL_HOOKS = [
    ("hw=(L[2]*c+L[3]*s)/2+8, hh=(L[2]*s+L[3]*c)/2+8; r.push([L[0]-hw, L[1]-hh, L[0]+hw, L[1]+hh]); });",
     "hw=(L[2]*c+L[3]*s)/2+8, hh=(L[2]*s+L[3]*c)/2+8; r.push([L[0]-hw, L[1]-hh, L[0]+hw, L[1]+hh, L[5]?clmAbs(L):null]); });"),
    ("if(b[0]<t[2] && b[2]>t[0] && b[1]<t[3] && b[3]>t[1]) return; }",
     "if(b[0]<t[2] && b[2]>t[0] && b[1]<t[3] && b[3]>t[1] && (!t[4] || clmNear(t[4], s.p, 8))) return; }"),
    ("L[1]>my1+400) return; var a=(L[4]||0)*Math.PI/180,", "L[1]>my1+400) return; if(L[5]){ clmCut(x,L); return; } var a=(L[4]||0)*Math.PI/180,"),
]

_HOOKS = [
    # nbDraw: the footprint is the shape's ring when the lot has one, every edge of it is a wall to pick from, the animation gets a box
    ("  var C=[[-w,-h],[w,-h],[w,h],[-w,h]].map(function(q){ return [q[0]*ca-q[1]*sa, q[0]*sa+q[1]*ca]; });\n  var yb=",
     "  var C=L[5]?L[5].map(function(q){ return [q[0],q[1]]; }):[[-w,-h],[w,-h],[w,h],[-w,h]].map(function(q){ return [q[0]*ca-q[1]*sa, q[0]*sa+q[1]*ca]; });\n  var yb="),
    ("  for(var i=0;i<4;i++){ var A=C[i], B=C[(i+1)%4], nx=", "  for(var i=0;i<C.length;i++){ var A=C[i], B=C[(i+1)%C.length], nx="),
    ("  var res=[x0,y0,x1,y1,yb]; res.C=C; return res;", "  var res=[x0,y0,x1,y1,yb]; res.C=L[5]?null:C; return res;"),
    # placeAll: a ring is part of what the block was built from
    ("key=[L[0],L[1],L[2],L[3],L[4],H].join('|');", "key=[L[0],L[1],L[2],L[3],L[4],H,L[5]?L[5].join():''].join('|');"),
    # add mode: outline of a lot is its ring; a background building is picked before a lot; the form takes a footprint
    ("function lotRect(L, cls, parent, pad){ pad=pad||0;\n", "function lotRect(L, cls, parent, pad){ pad=pad||0; if(L[5]) return clmRing(L,cls,parent);\n"),
    ("function lotAt(p){\n  var t=taken();", "function lotAt(p){\n  var cl=clmAt(p); if(cl) return cl;\n  var t=taken();"),
    ("var L=key?lot(key):null; if(!floorOf && (!L || taken()[key])){",
     "var CL=key&&key.r?key:null, L=CL?clmLot(CL):key?lot(key):null; if(!floorOf && (!L || (CL?clmBusy(CL):taken()[key]))){"),
    ("else list.push(['p|'+id+'|lot', key]);", "else list.push(CL?['p|'+id+'|shape', CL]:['p|'+id+'|lot', key]);"),
    ("formAt=hit.key; addForm(hit.key, null,", "formAt=hit.key; addForm(hit.cl||hit.key, null,"),
    # the op, and no dragging of a building off its footprint
    ("  if(p[0]==='p' && p[2]==='lot' && TT[p[1]]) return {kind:'card',", "  if(p[0]==='p' && p[2]==='shape' && TT[p[1]]) return clmField(p[1]);\n  if(p[0]==='p' && p[2]==='lot' && TT[p[1]]) return {kind:'card',"),
    ("  if(P.tw && P.tw[id]) return;", "  if((P.tw && P.tw[id]) || clmSh()[id]) return;"),
    # the functions, with the fill-in's (they use its tables)
    ("/* ── the board: the city under the cards, at the current zoom ── */", CLAIM_FUNCS + "\n/* ── the board: the city under the cards, at the current zoom ── */"),
]


def patch_js(js: str) -> str:
    for a, b in _HOOKS + (_FILL_HOOKS if "function fillTaken(" in js else []):       # (the fill-in's own parts: only a page that has it)
        if js.count(a) != 1:
            raise RuntimeError("palace_claim: hook anchor not found once: " + a[:70])
        js = js.replace(a, b)
    return js
