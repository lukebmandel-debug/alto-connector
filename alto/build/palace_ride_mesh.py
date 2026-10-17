"""The mesh format shared by every part of the first-person city (renderer, landmarks, scenery) and a small builder for it.

A MESH is a flat Float32Array of triangles, 10 floats a vertex:  x y z  nx ny nz  u v  mat tint
  x y        map units (1 unit = 1/1.3 m: SCALE in palace_skyline.py); z is UP, in map units; the ground is z = 0
  nx ny nz   unit normal
  u v        facade coordinates in METRES: u along a wall (from its first corner), v up the wall from the wall's base
             (a floor-to-floor of 3.4 m is v = 3.4); for roofs and floors u v are the world x y / 1.3 (metres)
  mat        material id, see MAT below (the renderer's shader picks brick / stone / glass ... by it)
  tint       0..1, a per-building random number (brick colour, window pattern, lit windows at night): the renderer reads it
WINDING (all builders obey it; fixed in the landmarks part, the old quad/cone normals pointed INTO the building and the dome was inside-out): a triangle's corners run
counter-clockwise for a viewer standing OUTSIDE the surface, a real viewer in the x east / y south / z up frame (a left-handed frame, so the right-handed cross product
(B-A)x(C-A) of the numbers points INTO the surface, against the stored normal). Stored normals always point OUT. With the usual view matrix (right = (-fy,fx,0), up, -forward)
that is gl.frontFace(CCW) + cullFace(BACK). A mesh may carry an origin m.o=[x,y] (map units): the builders then write u v relative to it (small numbers for the shader).
Builders append to a MB mesh `m` (an object with a growing array) and `MB.done(m)` returns the Float32Array.
Everything here is plain functions on arrays: no DOM, no allocation per frame (meshes are built once per world).
"""

JS_MB = r"""
/* ── mesh builder (palace_ride_mesh.py): see the format above ── */
var MAT={ground:0, brick:1, stone:2, glass:3, concrete:4, roof:5, metal:6, copper:7, glassdome:8, wood:9, water:10, asphalt:11, paving:12, grass:13, white:14, dark:15, tile:16, road:11, trunk:17, leaf:18, car:19, skin:20, lamp:21, sign:22, brickred:23};
var UM=1.3;                                    /* map units per metre */
var MB={
  mk:function(){ return {a:[]}; },
  v:function(m,x,y,z,nx,ny,nz,u,v,mat,tint){ m.a.push(x,y,z,nx,ny,nz,u,v,mat,tint||0); },
  tri:function(m,A,B,C,nx,ny,nz,mat,tint,uvA,uvB,uvC){ MB.v(m,A[0],A[1],A[2],nx,ny,nz,uvA[0],uvA[1],mat,tint); MB.v(m,B[0],B[1],B[2],nx,ny,nz,uvB[0],uvB[1],mat,tint); MB.v(m,C[0],C[1],C[2],nx,ny,nz,uvC[0],uvC[1],mat,tint); },
  /* a quad A B C D (counter-clockwise seen from the front), normal from the corners; uv: u runs A->B in metres, v runs A->D in metres */
  quad:function(m,A,B,C,D,mat,tint,uv){ var ux=B[0]-A[0], uy=B[1]-A[1], uz=B[2]-A[2], vx=D[0]-A[0], vy=D[1]-A[1], vz=D[2]-A[2], nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, l=-Math.sqrt(nx*nx+ny*ny+nz*nz)||-1; nx/=l; ny/=l; nz/=l;      /* winding is clockwise seen from outside (right-hand cross points INWARD), so the outward normal is its negative */
    var lu=(uv&&uv.w!=null)?uv.w:Math.sqrt(ux*ux+uy*uy+uz*uz)/UM, lv=(uv&&uv.h!=null)?uv.h:Math.sqrt(vx*vx+vy*vy+vz*vz)/UM, u0=uv&&uv.u0||0, v0=uv&&uv.v0||0;
    MB.tri(m,A,B,C,nx,ny,nz,mat,tint,[u0,v0],[u0+lu,v0],[u0+lu,v0+lv]); MB.tri(m,A,C,D,nx,ny,nz,mat,tint,[u0,v0],[u0+lu,v0+lv],[u0,v0+lv]); },
  /* a wall from (ax,ay) to (bx,by), from z0 up to z1; its outward side is to the LEFT of A->B seen from above with y down (see ringCCW) */
  wall:function(m,ax,ay,bx,by,z0,z1,mat,tint,u0){ MB.quad(m,[ax,ay,z0],[bx,by,z0],[bx,by,z1],[ax,ay,z1],mat,tint,{u0:u0||0,v0:0}); },
  /* signed area of a ring (flat x,y,x,y...): > 0 means clockwise on the screen (y down) */
  area:function(r){ var n=r.length/2, a=0; for(var i=0;i<n;i++){ var j=(i+1)%n; a+=r[2*i]*r[2*j+1]-r[2*j]*r[2*i+1]; } return a/2; },
  /* make a ring run so that wall(A->B) faces OUTWARD (what prism() needs) */
  ringOut:function(r){ if(MB.area(r)>0){ var o=[]; for(var i=r.length-2;i>=0;i-=2) o.push(r[i],r[i+1]); return o; } return r.slice(); },
  /* ear-clipping triangulation of a simple ring: returns [i,j,k,...] vertex indices */
  tris:function(r){ var n=r.length/2, idx=[], i; for(i=0;i<n;i++) idx.push(i); var out=[], sg=MB.area(r)>0?1:-1, guard=0;
    function cross(a,b,c){ return (r[2*b]-r[2*a])*(r[2*c+1]-r[2*a+1])-(r[2*b+1]-r[2*a+1])*(r[2*c]-r[2*a]); }
    function inside(p,a,b,c){ var d1=cross(a,b,p), d2=cross(b,c,p), d3=cross(c,a,p); return (d1>=0&&d2>=0&&d3>=0)||(d1<=0&&d2<=0&&d3<=0); }
    while(idx.length>3 && guard++<5000){ var ear=false;
      for(i=0;i<idx.length;i++){ var a=idx[(i+idx.length-1)%idx.length], b=idx[i], c=idx[(i+1)%idx.length]; if(cross(a,b,c)*sg<=1e-9) continue; var ok=true;
        for(var k=0;k<idx.length;k++){ var p=idx[k]; if(p===a||p===b||p===c) continue; if(inside(p,a,b,c)){ ok=false; break; } }
        if(ok){ out.push(a,b,c); idx.splice(i,1); ear=true; break; } }
      if(!ear) break; }
    if(idx.length===3) out.push(idx[0],idx[1],idx[2]); return out; },
  /* a flat polygon (a roof, a floor, a plaza) at height z, facing up (or down with dn), uv = world metres */
  flat:function(m,ring,z,mat,tint,dn){ var t=MB.tris(ring), s=dn?-1:1; for(var i=0;i<t.length;i+=3){ var a=t[i], b=t[i+1], c=t[i+2]; if(dn){ var q=b; b=c; c=q; }
      var A=[ring[2*a],ring[2*a+1],z], B=[ring[2*b],ring[2*b+1],z], C=[ring[2*c],ring[2*c+1],z]; var cr=(B[0]-A[0])*(C[1]-A[1])-(B[1]-A[1])*(C[0]-A[0]); if((cr>0)===(!dn)){ var q2=B; B=C; C=q2; }
      var o=m.o||[0,0]; MB.tri(m,A,B,C,0,0,s,mat,tint,[(A[0]-o[0])/UM,(A[1]-o[1])/UM],[(B[0]-o[0])/UM,(B[1]-o[1])/UM],[(C[0]-o[0])/UM,(C[1]-o[1])/UM]); } },
  /* a prism: walls of the footprint ring from z0 to z1 (facade uv) and a flat roof at z1 (optional) */
  prism:function(m,ring,z0,z1,wallMat,roofMat,tint){ var r=MB.ringOut(ring), n=r.length/2, u=0; for(var i=0;i<n;i++){ var j=(i+1)%n; MB.wall(m,r[2*i],r[2*i+1],r[2*j],r[2*j+1],z0,z1,wallMat,tint,u); u+=Math.hypot(r[2*j]-r[2*i],r[2*j+1]-r[2*i+1])/UM; }
    if(roofMat!=null) MB.flat(m,r,z1,roofMat,tint); return r; },
  box:function(m,x0,y0,z0,x1,y1,z1,wallMat,roofMat,tint){ return MB.prism(m,[x0,y0,x1,y0,x1,y1,x0,y1],z0,z1,wallMat,roofMat,tint); },
  /* a vertical cylinder (a tower, a column, a tree trunk, a dome drum); seg sides */
  cyl:function(m,cx,cy,z0,z1,r,seg,mat,roofMat,tint){ var pts=[]; for(var i=0;i<seg;i++){ var a=i/seg*6.2832; pts.push(cx+Math.cos(a)*r, cy+Math.sin(a)*r); } return MB.prism(m,pts,z0,z1,mat,roofMat,tint); },
  /* a cone / pyramid over a ring from z0 to the apex at (ax,ay,z1) */
  cone:function(m,ring,z0,ax,ay,z1,mat,tint){ var r=MB.ringOut(ring), n=r.length/2; for(var i=0;i<n;i++){ var j=(i+1)%n, A=[r[2*i],r[2*i+1],z0], B=[r[2*j],r[2*j+1],z0], C=[ax,ay,z1]; var ux=B[0]-A[0], uy=B[1]-A[1], uz=0, vx=C[0]-A[0], vy=C[1]-A[1], vz=C[2]-A[2];
      var nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, l=Math.sqrt(nx*nx+ny*ny+nz*nz)||1; var L=Math.hypot(ux,uy)/UM; MB.tri(m,A,B,C,-nx/l,-ny/l,-nz/l,mat,tint,[0,0],[L,0],[L/2,Math.hypot(vx,vy,vz)/UM]); } },
  /* a gable roof over the box x0..x1 x y0..y1 at height z, ridge along 'x' or 'y', rise h; hip: a hipped end instead of a gable */
  gable:function(m,x0,y0,x1,y1,z,h,axis,mat,tint){ var mx=(x0+x1)/2, my=(y0+y1)/2;
    if(axis==='x'){ MB.quad(m,[x0,y1,z],[x1,y1,z],[x1,my,z+h],[x0,my,z+h],mat,tint); MB.quad(m,[x1,y0,z],[x0,y0,z],[x0,my,z+h],[x1,my,z+h],mat,tint);
      MB.tri(m,[x0,y1,z],[x0,my,z+h],[x0,y0,z],-1,0,0,mat,tint,[0,0],[(y1-y0)/UM/2,h/UM],[(y1-y0)/UM,0]); MB.tri(m,[x1,y0,z],[x1,my,z+h],[x1,y1,z],1,0,0,mat,tint,[0,0],[(y1-y0)/UM/2,h/UM],[(y1-y0)/UM,0]); }
    else { MB.quad(m,[x0,y0,z],[x0,y1,z],[mx,y1,z+h],[mx,y0,z+h],mat,tint); MB.quad(m,[x1,y1,z],[x1,y0,z],[mx,y0,z+h],[mx,y1,z+h],mat,tint);
      MB.tri(m,[x0,y0,z],[mx,y0,z+h],[x1,y0,z],0,-1,0,mat,tint,[(x1-x0)/UM,0],[(x1-x0)/UM/2,h/UM],[0,0]); MB.tri(m,[x1,y1,z],[mx,y1,z+h],[x0,y1,z],0,1,0,mat,tint,[(x1-x0)/UM,0],[(x1-x0)/UM/2,h/UM],[0,0]); } },   /* end faces: CCW for the viewer outside */
  /* a dome: a half-sphere of radius r on (cx,cy,z), rings x seg faces */
  dome:function(m,cx,cy,z,r,rings,seg,mat,tint){ for(var i=0;i<rings;i++){ var a0=i/rings*1.5708, a1=(i+1)/rings*1.5708; for(var j=0;j<seg;j++){ var b0=j/seg*6.2832, b1=(j+1)/seg*6.2832;
      var p=function(a,b){ return [cx+Math.cos(a)*Math.cos(b)*r, cy+Math.cos(a)*Math.sin(b)*r, z+Math.sin(a)*r]; }; var P0=p(a0,b0), P1=p(a0,b1), P2=p(a1,b1), P3=p(a1,b0);
      var nrm=function(P){ return [(P[0]-cx)/r,(P[1]-cy)/r,(P[2]-z)/r]; }; var n0=nrm(P0), n1=nrm(P1), n2=nrm(P2), n3=nrm(P3);
      MB.v(m,P0[0],P0[1],P0[2],n0[0],n0[1],n0[2],b0*r/UM,a0*r/UM,mat,tint); MB.v(m,P2[0],P2[1],P2[2],n2[0],n2[1],n2[2],b1*r/UM,a1*r/UM,mat,tint); MB.v(m,P1[0],P1[1],P1[2],n1[0],n1[1],n1[2],b1*r/UM,a0*r/UM,mat,tint);
      MB.v(m,P0[0],P0[1],P0[2],n0[0],n0[1],n0[2],b0*r/UM,a0*r/UM,mat,tint); MB.v(m,P3[0],P3[1],P3[2],n3[0],n3[1],n3[2],b0*r/UM,a1*r/UM,mat,tint); MB.v(m,P2[0],P2[1],P2[2],n2[0],n2[1],n2[2],b1*r/UM,a1*r/UM,mat,tint); } } },   /* CCW for the viewer outside */
  append:function(m,o){ for(var i=0;i<o.a.length;i++) m.a.push(o.a[i]); },
  done:function(m){ return new Float32Array(m.a); },
  count:function(m){ return m.a.length/10; }
};

/* ══ landmark builders (added by the landmarks part): ABSOLUTE map-unit coordinates, z up; shapes are built from MB.face, which orients every polygon by an "out" vector ══ */
MB.trin=function(m,A,B,C,nA,nB,nC,uA,uB,uC,mat,tint){ if(typeof mat==='string') mat=MAT[mat]; var ux=B[0]-A[0], uy=B[1]-A[1], uz=B[2]-A[2], vx=C[0]-A[0], vy=C[1]-A[1], vz=C[2]-A[2], gx=uy*vz-uz*vy, gy=uz*vx-ux*vz, gz=ux*vy-uy*vx;
  if(gx*gx+gy*gy+gz*gz<1e-10) return;
  if(gx*(nA[0]+nB[0]+nC[0])+gy*(nA[1]+nB[1]+nC[1])+gz*(nA[2]+nB[2]+nC[2])>0){ var t=B; B=C; C=t; t=nB; nB=nC; nC=t; t=uB; uB=uC; uC=t; }
  m.a.push(A[0],A[1],A[2],nA[0],nA[1],nA[2],uA[0],uA[1],mat,tint||0, B[0],B[1],B[2],nB[0],nB[1],nB[2],uB[0],uB[1],mat,tint||0, C[0],C[1],C[2],nC[0],nC[1],nC[2],uC[0],uC[1],mat,tint||0); };
/* a convex planar polygon P=[[x,y,z],...] whose outside is toward `out`; uv from the plane: walls u runs to the viewer's right, v is the height; roofs and floors u v = x y; k scales the uv (shader metres per real metre) */
MB.face=function(m,P,out,mat,tint,k,u0){ var n=P.length, i, nx=0, ny=0, nz=0, o=m.o||[0,0]; if(n<3) return;
  for(i=0;i<n;i++){ var a=P[i], b=P[(i+1)%n]; nx+=(a[1]-b[1])*(a[2]+b[2]); ny+=(a[2]-b[2])*(a[0]+b[0]); nz+=(a[0]-b[0])*(a[1]+b[1]); }
  var l=Math.sqrt(nx*nx+ny*ny+nz*nz); if(l<1e-9) return; nx/=l; ny/=l; nz/=l; if(nx*out[0]+ny*out[1]+nz*out[2]<0){ nx=-nx; ny=-ny; nz=-nz; }
  var N=[nx,ny,nz], kk=k||1, vert=Math.abs(nz)<.6, hx=ny, hy=-nx, hl=Math.hypot(hx,hy)||1; hx/=hl; hy/=hl;
  var uv=P.map(function(p){ return vert?[((p[0]-o[0])*hx+(p[1]-o[1])*hy)/UM*kk+(u0||0), p[2]/UM*kk]:[(p[0]-o[0])/UM*kk,(p[1]-o[1])/UM*kk]; });
  for(i=1;i<n-1;i++) MB.trin(m,P[0],P[i],P[i+1],N,N,N,uv[0],uv[i],uv[i+1],mat,tint); };
/* an axis-aligned block; skip: 1 south (y1) 2 north (y0) 4 east (x1) 8 west (x0) 16 top; tm = the top's material or null */
MB.slab=function(m,x0,y0,z0,x1,y1,z1,wm,tm,tint,k,skip){ skip=skip||0; var F=MB.face;
  if(!(skip&1)) F(m,[[x0,y1,z0],[x1,y1,z0],[x1,y1,z1],[x0,y1,z1]],[0,1,0],wm,tint,k);
  if(!(skip&2)) F(m,[[x0,y0,z0],[x1,y0,z0],[x1,y0,z1],[x0,y0,z1]],[0,-1,0],wm,tint,k);
  if(!(skip&4)) F(m,[[x1,y0,z0],[x1,y1,z0],[x1,y1,z1],[x1,y0,z1]],[1,0,0],wm,tint,k);
  if(!(skip&8)) F(m,[[x0,y0,z0],[x0,y1,z0],[x0,y1,z1],[x0,y0,z1]],[-1,0,0],wm,tint,k);
  if(tm!=null && !(skip&16)) F(m,[[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],[0,0,1],tm,tint,k); };
/* a flat polygon (any simple ring) at z, up (or down with dn) */
MB.cap=function(m,ring,z,mat,tint,k,dn){ var t=MB.tris(ring), s=dn?-1:1; for(var i=0;i<t.length;i+=3){ var a=t[i], b=t[i+1], c=t[i+2]; MB.face(m,[[ring[2*a],ring[2*a+1],z],[ring[2*b],ring[2*b+1],z],[ring[2*c],ring[2*c+1],z]],[0,0,s],mat,tint,k); } };
/* walls between two rings of the same size (flat x,y,x,y), rA at zA and rB at zB (a tower that tapers, a mansard, a drum); capMat: a flat lid on rB */
MB.loft=function(m,rA,zA,rB,zB,wm,tint,k,capMat){ var n=rA.length/2, sg=MB.area(rA)>0?1:-1, i, j;
  for(i=0;i<n;i++){ j=(i+1)%n; var dx=rA[2*j]-rA[2*i], dy=rA[2*j+1]-rA[2*i+1];
    MB.face(m,[[rA[2*i],rA[2*i+1],zA],[rA[2*j],rA[2*j+1],zA],[rB[2*j],rB[2*j+1],zB],[rB[2*i],rB[2*i+1],zB]],[dy*sg,-dx*sg,0],wm,tint,k); }
  if(capMat!=null) MB.cap(m,rB,zB,capMat,tint,k); };
/* a ring of quads between an outer and an inner ring (same size) at their own heights: a roof rim, a stand, a pavement; dn faces down */
MB.band=function(m,rO,zO,rI,zI,mat,tint,k,dn){ var n=rO.length/2, s=dn?-1:1;
  for(var i=0;i<n;i++){ var j=(i+1)%n; MB.face(m,[[rO[2*i],rO[2*i+1],zO],[rO[2*j],rO[2*j+1],zO],[rI[2*j],rI[2*j+1],zI],[rI[2*i],rI[2*i+1],zI]],[0,0,s],mat,tint,k); } };
/* a hipped / mansard roof over x0..x1 x y0..y1 from z: tiers [[inset,rise],...] one above the other; a flat lid of topMat when given */
MB.roofTiers=function(m,x0,y0,x1,y1,z,tiers,mat,tint,k,topMat){ var r=[x0,y0,x1,y0,x1,y1,x0,y1], zz=z;
  for(var i=0;i<tiers.length;i++){ var d=tiers[i][0], hw=(r[2]-r[0])/2, hd=(r[5]-r[1])/2, dx=Math.min(d,hw), dy=Math.min(d,hd), q=[r[0]+dx,r[1]+dy,r[2]-dx,r[3]+dy,r[4]-dx,r[5]-dy,r[6]+dx,r[7]-dy];
    MB.loft(m,r,zz,q,zz+tiers[i][1],mat,tint,k); r=q; zz+=tiers[i][1]; }
  if(topMat!=null && r[2]-r[0]>.05 && r[5]-r[1]>.05) MB.cap(m,r,zz,topMat,tint,k); return zz; };
/* a surface of revolution about (cx,cy): prof = [[r,z],...] from the bottom up (map units); soft: smooth normals between segments that bend gently */
MB.lathe=function(m,cx,cy,prof,seg,mat,tint,k,soft){ var np=prof.length, kk=k||1, sn=[], i, j, o=m.o||[0,0];
  for(i=0;i<np-1;i++){ var dr=prof[i+1][0]-prof[i][0], dz=prof[i+1][1]-prof[i][1], L=Math.hypot(dr,dz)||1; sn.push([dz/L,-dr/L]); }
  function nrm(si,pi){ var a=sn[si]; if(!soft) return a; var b=pi===si?sn[si-1]:sn[si+1]; if(!b) return a; if(a[0]*b[0]+a[1]*b[1]<.72) return a; var x=a[0]+b[0], z=a[1]+b[1], l=Math.hypot(x,z)||1; return [x/l,z/l]; }
  for(i=0;i<np-1;i++){ var p0=prof[i], p1=prof[i+1], n0=nrm(i,i), n1=nrm(i,i+1);
    for(j=0;j<seg;j++){ var a0=j/seg*6.2832, a1=(j+1)/seg*6.2832, c0=Math.cos(a0), s0=Math.sin(a0), c1=Math.cos(a1), s1=Math.sin(a1);
      var A=[cx+p0[0]*c0,cy+p0[0]*s0,p0[1]], B=[cx+p0[0]*c1,cy+p0[0]*s1,p0[1]], C=[cx+p1[0]*c1,cy+p1[0]*s1,p1[1]], D=[cx+p1[0]*c0,cy+p1[0]*s0,p1[1]];
      var nA=[n0[0]*c0,n0[0]*s0,n0[1]], nB=[n0[0]*c1,n0[0]*s1,n0[1]], nC=[n1[0]*c1,n1[0]*s1,n1[1]], nD=[n1[0]*c0,n1[0]*s0,n1[1]];
      var u0=a0*Math.max(p0[0],p1[0])/UM*kk, u1=a1*Math.max(p0[0],p1[0])/UM*kk, v0=p0[1]/UM*kk, v1=p1[1]/UM*kk;
      MB.trin(m,A,B,C,nA,nB,nC,[u0,v0],[u1,v0],[u1,v1],mat,tint); MB.trin(m,A,C,D,nA,nC,nD,[u0,v0],[u1,v1],[u0,v1],mat,tint); } } };
/* a column: base block, tapering shaft, flared capital, abacus (r = shaft radius at the foot) */
MB.col=function(m,cx,cy,z0,z1,r,seg,mat,tint,k){ var h=z1-z0, zb=z0+r*.55, zs=z1-r*1.15, zc=z1-r*.45;
  MB.slab(m,cx-r*1.3,cy-r*1.3,z0,cx+r*1.3,cy+r*1.3,zb,mat,mat,tint,k,0);
  MB.lathe(m,cx,cy,[[r*1.05,zb],[r*.86,zs],[r*.95,zs+.0001],[r*1.2,zc]],seg,mat,tint,k,true);
  MB.slab(m,cx-r*1.4,cy-r*1.4,zc,cx+r*1.4,cy+r*1.4,z1,mat,mat,tint,k,0); };
/* polygons stuck on a wall facing d=(dx,dy): pts are [u,v] (u to the viewer's right, v up, map units) about (cx,cy,z); off pushes them out of the wall */
MB.decal=function(m,cx,cy,z,dx,dy,pts,mat,tint,off,k){ var rx=dy, ry=-dx, o=off==null?.12:off, P=pts.map(function(q){ return [cx+rx*q[0]+dx*o, cy+ry*q[0]+dy*o, z+q[1]]; }); MB.face(m,P,[dx,dy,0],mat,tint,k||1); };
MB.archPts=function(w,h,seg){ var r=w/2, hs=Math.max(0,h-r), p=[[-r,0],[r,0]], t; seg=seg||8; for(t=0;t<=seg;t++){ var a=t/seg*3.14159; p.push([r*Math.cos(a),hs+r*Math.sin(a)]); } return p; };
MB.circPts=function(r,seg){ var p=[]; for(var t=0;t<seg;t++){ var a=t/seg*6.2832; p.push([r*Math.cos(a),r*Math.sin(a)]); } return p; };
/* a gabled pediment on the front d=(dx,dy) of something w wide centred at (cx,cy): triangle face at the front plus the two sloping roof sides back to `depth`; wm: the tympanum, rm: the roof */
MB.pediment=function(m,cx,cy,dx,dy,z,w,rise,depth,wm,rm,tint,k){ var rx=dy, ry=-dx, hw=w/2, F=MB.face, A=[cx-rx*hw,cy-ry*hw,z], B=[cx+rx*hw,cy+ry*hw,z], T=[cx,cy,z+rise], bx=-dx*depth, by=-dy*depth,
    A2=[A[0]+bx,A[1]+by,z], B2=[B[0]+bx,B[1]+by,z], T2=[T[0]+bx,T[1]+by,z+rise];
  F(m,[A,B,T],[dx,dy,0],wm,tint,k); F(m,[A,T,T2,A2],[-rx*rise,-ry*rise,hw],rm,tint,k); F(m,[B,T,T2,B2],[rx*rise,ry*rise,hw],rm,tint,k); };
/* steps down toward d=(dx,dy) (axis-aligned) from a landing whose front edge passes through (cx,cy) at height z: n steps of `rise` and `tread`, w wide */
MB.steps=function(m,cx,cy,dx,dy,w,n,rise,tread,z,mat,tint,k){ for(var i=1;i<=n;i++){ var d0=0, d1=i*tread, zt=z-i*rise, hw=w/2, x0,x1,y0,y1;
    if(dx===0){ x0=cx-hw; x1=cx+hw; if(dy>0){ y0=cy+d0; y1=cy+d1; } else { y0=cy-d1; y1=cy-d0; } } else { y0=cy-hw; y1=cy+hw; if(dx>0){ x0=cx+d0; x1=cx+d1; } else { x0=cx-d1; x1=cx-d0; } }
    MB.slab(m,x0,y0,0,x1,y1,zt,mat,mat,tint,k,dx===0?(dy>0?2:1):(dx>0?8:4)); } };
"""
