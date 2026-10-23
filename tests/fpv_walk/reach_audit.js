/* Can every room be walked to? (node, no browser): floods the plan from its "Walk in" spot with the guided trip's own cell test (palace_building_fpv.py
   navCell: floor under the capsule, nothing in the way, no step down a ledge; stairs are cells whose floor rises) and rides the lifts between levels.
   A room counts when its card's arrival spot (where a trip to the card stops) is reached; a room whose arrival spot is not, but whose floor is, is
   listed in floorOnly. Every room gets a card here, as in walk_audit.js.

   node reach_audit.js <renderer.js> <plan.json>   ->  one JSON line: {rooms, reached, floorOnly:[ids], missing:[ids]} */
global.window=global; global.document=null; global.navigator={};
var fs=require('fs'), src=fs.readFileSync(process.argv[2],'utf8'), hook='API._debug=function(){ return S; };';
if(src.indexOf(hook)<0) throw new Error('renderer changed: no _debug hook to expose navCell');
eval(src.replace(hook,hook+' API._nav={navCell:navCell, cell:NAV.cell, pip:pip, interior:interior};'));
var plan=JSON.parse(fs.readFileSync(process.argv[3],'utf8')), A=window.AltoBuildingFPV, data={nodes:{}, order:[]};
(plan.rm||[]).forEach(function(r,i){ if(r.gp||r.k==='void') return; var id='n'+i; data.nodes[id]={n:'Card '+i, t:'Card '+i, r:r.id, a:0}; data.order.push(id); });
var G=A.sim(plan,data), N=A._nav, C=N.cell, cache={}, seen={}, todo=[], lv={}, D8=[[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
plan.lv.forEach(function(l){ lv[l.id]=l; });
function cell(i,j,z){ return N.navCell(G,cache,i,j,z); }
function key(i,j,z){ return i+','+j+','+Math.round(z*4); }
function seed(x,y,z){ var i0=Math.round(x/C), j0=Math.round(y/C); for(var r=0;r<8;r++) for(var di=-r;di<=r;di++) for(var dj=-r;dj<=r;dj++){ if(Math.max(Math.abs(di),Math.abs(dj))!==r) continue;
  var zz=cell(i0+di,j0+dj,z+.3); if(zz!=null&&Math.abs(zz-z)<.3){ var k=key(i0+di,j0+dj,zz); if(!(k in seen)){ seen[k]=1; todo.push([i0+di,j0+dj,zz]); } return; } } }
function flood(){ while(todo.length){ var o=todo.pop(); for(var d=0;d<8;d++){ var ni=o[0]+D8[d][0], nj=o[1]+D8[d][1], z=cell(ni,nj,o[2]); if(z==null) continue;
  if(d>3&&(cell(o[0]+D8[d][0],o[1],o[2])==null||cell(o[0],o[1]+D8[d][1],o[2])==null)) continue; var k=key(ni,nj,z); if(!(k in seen)){ seen[k]=1; todo.push([ni,nj,z]); } } } }
function near(x,y,z,rad){ var i0=Math.round(x/C), j0=Math.round(y/C), R=Math.ceil(rad/C); for(var di=-R;di<=R;di++) for(var dj=-R;dj<=R;dj++) for(var dz=-1;dz<=1;dz++) if(key(i0+di,j0+dj,z+dz*.25) in seen) return true; return false; }
seed(plan.sp.p[0],plan.sp.p[1],lv[plan.sp.l].e);
var rode={};
for(var more=true;more;){ flood(); more=false;                                          /* a lift reached on one floor is ridden to the other */
  G.lifts.forEach(function(o,li){ var c=N.interior(o.s.fp); [[o.lo,o.hi],[o.hi,o.lo]].forEach(function(p){ var k=li+p[0].id; if(rode[k]||!near(c[0],c[1],p[0].e,3)) return; rode[k]=1; seed(c[0],c[1],p[1].e); more=true; }); }); }
var byZ={}; Object.keys(seen).forEach(function(k){ var p=k.split(','); (byZ[p[2]]=byZ[p[2]]||[]).push([p[0]*C,p[1]*C]); });
function floorReached(r){ var zk=Math.round(lv[r.l].e*4), P=r.p, xs=P.map(function(q){ return q[0]; }), ys=P.map(function(q){ return q[1]; }), x0=Math.min.apply(0,xs)+.3, x1=Math.max.apply(0,xs)-.3, y0=Math.min.apply(0,ys)+.3, y1=Math.max.apply(0,ys)-.3;
  return [zk-1,zk,zk+1].some(function(z){ return (byZ[z]||[]).some(function(c){ return c[0]>x0&&c[0]<x1&&c[1]>y0&&c[1]<y1&&N.pip(P,c[0],c[1]); }); }); }
var rid={}, out={rooms:0, reached:0, floorOnly:[], missing:[]}; plan.rm.forEach(function(r){ rid[r.id]=r; });
data.order.forEach(function(id){ if(!G.slots['card-'+id]) return; var r=rid[data.nodes[id].r], to=A.arrival('card-'+id); out.rooms++;
  if(to&&near(to.x,to.y,to.z,.45)) out.reached++; else if(floorReached(r)){ out.reached++; out.floorOnly.push(r.id); } else out.missing.push(r.id); });
console.log(JSON.stringify(out));
