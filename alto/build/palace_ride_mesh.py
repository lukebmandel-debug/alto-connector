"""The mesh format shared by every part of the first-person city (renderer, landmarks, scenery) and a small builder for it.

A MESH is a flat Float32Array of triangles, 10 floats a vertex:  x y z  nx ny nz  u v  mat tint
  x y        map units (1 unit = 1/1.3 m: SCALE in palace_skyline.py); z is UP, in map units; the ground is z = 0
  nx ny nz   unit normal
  u v        facade coordinates in METRES: u along a wall (from its first corner), v up the wall from the wall's base
             (a floor-to-floor of 3.4 m is v = 3.4); for roofs and floors u v are the world x y / 1.3 (metres)
  mat        material id, see MAT below (the renderer's shader picks brick / stone / glass ... by it)
  tint       0..1, a per-building random number (brick colour, window pattern, lit windows at night): the renderer reads it
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
  quad:function(m,A,B,C,D,mat,tint,uv){ var ux=B[0]-A[0], uy=B[1]-A[1], uz=B[2]-A[2], vx=D[0]-A[0], vy=D[1]-A[1], vz=D[2]-A[2], nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, l=Math.sqrt(nx*nx+ny*ny+nz*nz)||1; nx/=l; ny/=l; nz/=l;
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
      MB.tri(m,A,B,C,0,0,s,mat,tint,[A[0]/UM,A[1]/UM],[B[0]/UM,B[1]/UM],[C[0]/UM,C[1]/UM]); } },
  /* a prism: walls of the footprint ring from z0 to z1 (facade uv) and a flat roof at z1 (optional) */
  prism:function(m,ring,z0,z1,wallMat,roofMat,tint){ var r=MB.ringOut(ring), n=r.length/2, u=0; for(var i=0;i<n;i++){ var j=(i+1)%n; MB.wall(m,r[2*i],r[2*i+1],r[2*j],r[2*j+1],z0,z1,wallMat,tint,u); u+=Math.hypot(r[2*j]-r[2*i],r[2*j+1]-r[2*i+1])/UM; }
    if(roofMat!=null) MB.flat(m,r,z1,roofMat,tint); return r; },
  box:function(m,x0,y0,z0,x1,y1,z1,wallMat,roofMat,tint){ return MB.prism(m,[x0,y0,x1,y0,x1,y1,x0,y1],z0,z1,wallMat,roofMat,tint); },
  /* a vertical cylinder (a tower, a column, a tree trunk, a dome drum); seg sides */
  cyl:function(m,cx,cy,z0,z1,r,seg,mat,roofMat,tint){ var pts=[]; for(var i=0;i<seg;i++){ var a=i/seg*6.2832; pts.push(cx+Math.cos(a)*r, cy+Math.sin(a)*r); } return MB.prism(m,pts,z0,z1,mat,roofMat,tint); },
  /* a cone / pyramid over a ring from z0 to the apex at (ax,ay,z1) */
  cone:function(m,ring,z0,ax,ay,z1,mat,tint){ var r=MB.ringOut(ring), n=r.length/2; for(var i=0;i<n;i++){ var j=(i+1)%n, A=[r[2*i],r[2*i+1],z0], B=[r[2*j],r[2*j+1],z0], C=[ax,ay,z1]; var ux=B[0]-A[0], uy=B[1]-A[1], uz=0, vx=C[0]-A[0], vy=C[1]-A[1], vz=C[2]-A[2];
      var nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, l=Math.sqrt(nx*nx+ny*ny+nz*nz)||1; var L=Math.hypot(ux,uy)/UM; MB.tri(m,A,B,C,nx/l,ny/l,nz/l,mat,tint,[0,0],[L,0],[L/2,Math.hypot(vx,vy,vz)/UM]); } },
  /* a gable roof over the box x0..x1 x y0..y1 at height z, ridge along 'x' or 'y', rise h; hip: a hipped end instead of a gable */
  gable:function(m,x0,y0,x1,y1,z,h,axis,mat,tint){ var mx=(x0+x1)/2, my=(y0+y1)/2;
    if(axis==='x'){ MB.quad(m,[x0,y1,z],[x1,y1,z],[x1,my,z+h],[x0,my,z+h],mat,tint); MB.quad(m,[x1,y0,z],[x0,y0,z],[x0,my,z+h],[x1,my,z+h],mat,tint);
      MB.tri(m,[x0,y1,z],[x0,my,z+h],[x0,y0,z],-1,0,0,mat,tint,[0,0],[(y1-y0)/UM/2,h/UM],[(y1-y0)/UM,0]); MB.tri(m,[x1,y0,z],[x1,my,z+h],[x1,y1,z],1,0,0,mat,tint,[0,0],[(y1-y0)/UM/2,h/UM],[(y1-y0)/UM,0]); }
    else { MB.quad(m,[x0,y0,z],[x0,y1,z],[mx,y1,z+h],[mx,y0,z+h],mat,tint); MB.quad(m,[x1,y1,z],[x1,y0,z],[mx,y0,z+h],[mx,y1,z+h],mat,tint);
      MB.tri(m,[x1,y0,z],[mx,y0,z+h],[x0,y0,z],0,-1,0,mat,tint,[0,0],[(x1-x0)/UM/2,h/UM],[(x1-x0)/UM,0]); MB.tri(m,[x0,y1,z],[mx,y1,z+h],[x1,y1,z],0,1,0,mat,tint,[0,0],[(x1-x0)/UM/2,h/UM],[(x1-x0)/UM,0]); } },
  /* a dome: a half-sphere of radius r on (cx,cy,z), rings x seg faces */
  dome:function(m,cx,cy,z,r,rings,seg,mat,tint){ for(var i=0;i<rings;i++){ var a0=i/rings*1.5708, a1=(i+1)/rings*1.5708; for(var j=0;j<seg;j++){ var b0=j/seg*6.2832, b1=(j+1)/seg*6.2832;
      var p=function(a,b){ return [cx+Math.cos(a)*Math.cos(b)*r, cy+Math.cos(a)*Math.sin(b)*r, z+Math.sin(a)*r]; }; var P0=p(a0,b0), P1=p(a0,b1), P2=p(a1,b1), P3=p(a1,b0);
      var nrm=function(P){ return [(P[0]-cx)/r,(P[1]-cy)/r,(P[2]-z)/r]; }; var n0=nrm(P0), n1=nrm(P1), n2=nrm(P2), n3=nrm(P3);
      MB.v(m,P0[0],P0[1],P0[2],n0[0],n0[1],n0[2],b0*r/UM,a0*r/UM,mat,tint); MB.v(m,P1[0],P1[1],P1[2],n1[0],n1[1],n1[2],b1*r/UM,a0*r/UM,mat,tint); MB.v(m,P2[0],P2[1],P2[2],n2[0],n2[1],n2[2],b1*r/UM,a1*r/UM,mat,tint);
      MB.v(m,P0[0],P0[1],P0[2],n0[0],n0[1],n0[2],b0*r/UM,a0*r/UM,mat,tint); MB.v(m,P2[0],P2[1],P2[2],n2[0],n2[1],n2[2],b1*r/UM,a1*r/UM,mat,tint); MB.v(m,P3[0],P3[1],P3[2],n3[0],n3[1],n3[2],b0*r/UM,a1*r/UM,mat,tint); } } },
  append:function(m,o){ for(var i=0;i<o.a.length;i++) m.a.push(o.a[i]); },
  done:function(m){ return new Float32Array(m.a); },
  count:function(m){ return m.a.length/10; }
};
"""
