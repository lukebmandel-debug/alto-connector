"""Part H of the first-person ride: detailed landmark models in the shared mesh format (owner: the landmarks agent)."""

JS_H = r"""
/* LANDMARKS: landmarkMeshes(l, floors, W) is called by gatherWorld for every landmark l (M.landmarks[i]: {n, box:[x0,y0,x1,y1], page}) in the cells.
   It must keep the simple extruded stand-in working for the 2D fallback (lmSolids pushes into W.solids) and ALSO push a detailed model into W.meshes
   as {a: Float32Array (mesh format, palace_ride_mesh.py), id: name} when it has one. */
function landmarkMeshes(l, floors, W){ lmSolids(l, W.solids, floors); }
"""
