"""Part G of the first-person ride: scenery - street trees, lamps, crosswalks, cars, people, lit windows (owner: the scenery agent)."""

JS_G = r"""
/* SCENERY: sceneryGather(W, set) adds to the world W (W.solids for anything that must sort with buildings, W.scenery for flat/overlay items);
   sceneryDraw(ctx, W, P, C, tm) draws W.scenery each frame, after the ground and before the solids. Both are called from palace_ride_b.py / palace_ride_d.py. */
function sceneryGather(W, set){}
function sceneryDraw(ctx, W, P, Cam, tm){}
function sceneryUpdate(W, tm, Cam){}      /* each frame: move W.movers (cars, people): set m.x, m.y, m.z, m.yaw */
"""
CSS_G = ""
