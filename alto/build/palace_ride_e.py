"""Part E of the first-person ride: free roaming - walk anywhere in the city at street level (owner: the roam agent)."""

JS_E = r"""
var ROAM={ enter:function(){ return false; }, exit:function(){}, active:function(){ return false; } };
/* ROAM: window._palRide.roam = {enter(x,y,heading), exit(stay), active()}  (see the contract in the notes folder) */
"""
CSS_E = ""
