"""Bakes the ride's two material-detail textures (palace_ride_gfx.py, alto/assets/tex/alto-tex0.png, alto-tex1.png) in a headless browser.

Original procedural work (periodic value noise and cellular noise, seamless at 512 px), so it carries no third-party licence; see alto/assets/tex/NOTICE.
Each channel is one material's grey detail, normalised to mean .5 / sd .17 so the shader can multiply it in without shifting the colour:
  tex0  R asphalt (aggregate in bitumen, patches)   G concrete (grain, pores, trowel marks)   B roof gravel (lit pebbles)
  tex1  R brick face (speckle, iron spots, firing)    G limestone (mottling, fine grain)        B grime (vertical rain streaks, drips)
Re-run:  python -m alto.build.palace_tex_bake   (needs Playwright with WebKit or Chromium)
"""
from __future__ import annotations

import base64
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "tex"

BAKE_JS = r"""
() => {
  const N = 512;
  function rng(s){ return function(){ s=(Math.imul(s,1664525)+1013904223)|0; return ((s>>>8)&0xffffff)/16777216; }; }
  function hash2(x,y,s){ let h=Math.imul(x,374761393)^Math.imul(y,668265263)^Math.imul(s,2147483647); h=Math.imul(h^(h>>>13),1274126177); return ((h^(h>>>16))>>>0)/4294967296; }
  function vnoise(u,v,P,s){ const x=u*P, y=v*P, xi=Math.floor(x), yi=Math.floor(y), fx=x-xi, fy=y-yi, sx=fx*fx*(3-2*fx), sy=fy*fy*(3-2*fy);
    const m=(a)=>((a%P)+P)%P, a=hash2(m(xi),m(yi),s), b=hash2(m(xi+1),m(yi),s), c=hash2(m(xi),m(yi+1),s), d=hash2(m(xi+1),m(yi+1),s);
    return a+(b-a)*sx+(c-a)*sy+(a-b-c+d)*sx*sy; }
  function fbm(u,v,P,oct,s){ let t=0,a=.5,w=0; for(let i=0;i<oct;i++){ t+=a*vnoise(u,v,P,s+i*17); w+=a; a*=.5; P*=2; } return t/w; }
  function worley(u,v,P,s){ const x=u*P, y=v*P, xi=Math.floor(x), yi=Math.floor(y); let f1=9,f2=9,id=0,gx=0,gy=0;
    for(let j=-1;j<=1;j++) for(let i=-1;i<=1;i++){ const cx=xi+i, cy=yi+j, mx=((cx%P)+P)%P, my=((cy%P)+P)%P, px=cx+hash2(mx,my,s), py=cy+hash2(mx,my,s+1), dx=px-x, dy=py-y, d=Math.sqrt(dx*dx+dy*dy);
      if(d<f1){ f2=f1; f1=d; id=hash2(mx,my,s+2); gx=dx; gy=dy; } else if(d<f2) f2=d; }
    return [f1,f2,id,gx,gy]; }
  function norm(a){ let m=0; for(const x of a) m+=x; m/=a.length; let v=0; for(const x of a) v+=(x-m)*(x-m); const sd=Math.sqrt(v/a.length)||1;
    return a.map(x=>Math.max(0,Math.min(1,.5+(x-m)/sd*.17))); }
  function chan(f){ const a=new Array(N*N); for(let y=0;y<N;y++) for(let x=0;x<N;x++) a[y*N+x]=f(x/N,y/N); return norm(a); }
  const asphalt=chan((u,v)=>{ const w=worley(u,v,150,11), edge=Math.min(1,(w[1]-w[0])*3), st=w[2]*w[2];
    return .30*st*(.6+.4*edge)+.32*fbm(u,v,128,2,3)+.25*fbm(u,v,4,3,5)-.10*Math.max(0,fbm(u,v,6,3,9)-.58)*4; });
  const concrete=chan((u,v)=>{ const w=worley(u,v,150,21), pore=w[0]<.11?(.11-w[0])*7:0;
    return .45*fbm(u,v,32,4,23)+.25*fbm(u,v,3,3,27)+.12*vnoise(u,v,256,29)-.55*pore+.015*Math.sin((u*3+fbm(u,v,4,2,31)*.6)*6.2832*6); });
  const gravel=chan((u,v)=>{ const w=worley(u,v,96,41), sh=Math.max(0,1-w[0]*2.2), lit=(w[3]*.6-w[4]*.8);
    return .5*w[2]+.45*sh*(.6+lit)-.35*Math.max(0,.18-(w[1]-w[0]))*4+.12*vnoise(u,v,256,43); });
  const brick=chan((u,v)=>{ const w=worley(u,v,60,51), spot=w[0]<.07&&w[2]>.75?1:0;
    return .35*fbm(u,v,64,3,53)+.25*fbm(u,v,4,3,57)+.15*vnoise(u,v,256,59)-.35*spot; });
  const lime=chan((u,v)=>{ const w=worley(u,v,40,61), fos=w[0]<.05&&w[2]>.6?1:0;
    return .5*fbm(u,v,3,4,63)+.22*fbm(u,v,48,3,67)+.1*vnoise(u,v,256,69)-.2*fos; });
  const grime=chan((u,v)=>{ const s1=fbm(u,v*.0+v,1,1,71); const st=fbm(u,v/16,64,3,73)*1.0, dr=Math.pow(Math.max(0,fbm(u,v/8,24,2,77)-.45),1.5)*3*(1-v*.6);
    return .5*st-.6*dr+.2*fbm(u,v,4,3,79)+0*s1; });
  function png(r,g,b){ const c=document.createElement('canvas'); c.width=N; c.height=N; const x=c.getContext('2d'), im=x.createImageData(N,N);
    for(let i=0;i<N*N;i++){ im.data[4*i]=Math.round(r[i]*255); im.data[4*i+1]=Math.round(g[i]*255); im.data[4*i+2]=Math.round(b[i]*255); im.data[4*i+3]=255; }
    x.putImageData(im,0,0); return c.toDataURL('image/png'); }
  return [png(asphalt,concrete,gravel), png(brick,lime,grime)];
}
"""


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.webkit.launch()
        pg = b.new_page()
        pg.set_content("<!doctype html><title>bake</title>")
        urls = pg.evaluate(BAKE_JS)
        b.close()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, u in zip(("alto-tex0.png", "alto-tex1.png"), urls):
        (OUT / name).write_bytes(base64.b64decode(u.split(",", 1)[1]))
        print(name, (OUT / name).stat().st_size)


if __name__ == "__main__":
    main()
