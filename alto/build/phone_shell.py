"""The phone shell: one owner of a phone page's screen edges (chunk 2 of ORG/phone-ui-audit-1111.md, rows E1, E2, E4, E5).

Every top-level phone page (timeline card view, whole view, homepage) runs on the runway (runway.py): Safari shows the document's own pixels
above and below the body box under its bars. Until now those pixels were #page-bg, Classic's sunset gradient, whatever style or format was on
screen (a black Retro page got brown strips, a pale Holographic one peach), and the root colour and theme-color stayed Classic's too.

The shell, inline in <head> (a few hundred bytes, before first layout):
  * finds the page's GROUND at the top and the foot of the screen: the first opaque layer among the page's own grounds (#nav / #title-bar at the
    top, #app, #canvas, #projects-wrap, body) under the screen's centre line. None (Classic: the ground IS #page-bg) = nothing to do, the runway
    already shows #page-bg's real pixels;
  * paints it: the root colour, theme-color and two strips in the runway (#sh-top / #sh-foot, document pixels above and below the body box) in
    the ground's own edge colours. _altoShell.paint(top, foot) does the same by hand for a format that knows better;
  * publishes the real screen box as CSS variables --sh-top, --sh-foot, --sh-left, --sh-right (the safe-area insets) and --sh-h (the visual
    viewport's height), and the classes sh-portrait / sh-landscape on <html>;
  * in landscape, moves the screen-corner chrome (clef, corner tiles, chip row ends) clear of the Dynamic Island: each piece at the left or right
    edge gets .sh-l / .sh-r, which translate it by the inset (the `translate` property, so it never fights a piece's own transform).
Chunk 2b (Sim 1111c S4, S8, S9):
  * Classic's whole view: no opaque ground, but the board is #page-bg's gradient under #page-glass, while the root (what Safari shows behind its bars and
    at the side strips) had its own, differently scaled sunset. The root gets the board's picture, frosted the same, at the board's box (board()).
    Classic's card view stays as it was;
  * a top-level page on a phone runs the shell even without the runway (the homepage in landscape is its desktop layout): the root colour and
    theme-color take the ground (#page-bg's own plain colour counts as one; Classic's gradient and a chosen photo do not), no strips;
  * landscape: the whole view's #canvas sits between the side insets (the unit chips and numerals run to the board's edges) and is refitted when the
    insets change, unless a finger zoomed it; the homepage's bar, list and corner buttons move in by the insets too.
It re-reads all of it on load, on rotation / resize, and whenever <html>'s classes change (a style, dark mode, the whole view).

?shell=0 on the address turns all of it off (the old path, untouched) until every Simulator row of chunk 2 has passed."""

SHELL_JS = r"""(function(){
var de=document.documentElement;
if(/[?&]shell=0/.test(location.search)){de.classList.add('sh-off');return;}
var S=window._altoShell={top:null,foot:null};
var PH=/Mobi|iPhone|iPod|Android/i.test(navigator.userAgent)&&window.top===window;
// Before first layout (sim1111f S8, ?dbg=1 in the real Simulator): Mobile Safari ignores theme-color and tints its landscape toolbar from the root's
// background colour as it stands at the first layout, and again only on a turn; a Holo look that lands 1.6 s later left the strip peach. So the root
// takes the colour this page last painted (per address, look, theme and orientation), else the look's known ground, before anything is laid out.
var HG=__HOLO__;
if(PH)de.classList.add('sh-ph');
// (sim1112b S1) Which way up: the phone's own answer where it gives one. A new tab's <head> runs before the tab has its size (innerWidth / innerHeight are
// not yet the screen's), and orientationchange comes ~80 ms before the first resize: the window's box said "portrait" both times, so the root kept
// Classic's peach at the one layout Safari tints its toolbar from.
function land(){var o=window.orientation;return PH&&typeof o==='number'&&/iPhone|iPod/.test(navigator.userAgent)?Math.abs(o)===90:innerWidth>innerHeight;}      // (an iPhone's 0 is upright; a tablet's need not be)
function sig(){var k=window._altoBg&&window._altoBg.key,st='';try{st=k&&localStorage.getItem(/-bg$/.test(k)?k.replace(/-bg$/,'-style'):k+'-style')||'';}catch(e){}
 var dk=de.classList.contains('dark');try{dk=dk||localStorage.getItem('alto-theme-v1')==='dark';}catch(e){}
 var ld=land(),w=de.classList.contains('phone-whole')||window._altoPhoneWhole,bg=de.classList.contains('alto-bg');
 return {st:st,dk:dk,ld:ld,w:w,bg:bg,home:(!st||st==='classic')&&de.classList.contains('alto-home')&&!bg&&ld,k:location.pathname+'|'+st+'|'+(dk?'d':'l')+'|'+(w?'w':'c')+'|'+(ld?'L':'P')};}
// The kept colours: {key: [#rrggbb, day]}, written only from a measured ground (S.paint). One is used only if it is whole, under 30 days old, not Classic's
// own default root / theme-color (the peach a page shows before anything is measured: never worth keeping, and what a wrong entry was), and, on Classic's
// homepage on its side, near the header glass it must be. Anything else is dropped, so one bad entry cannot colour the loads after it.
var BAD=/^#(ffc98a|ffc59e)$/i;
function day(){return Math.floor(Date.now()/864e5);}
function far(a,b){var d=0;for(var i=1;i<7;i+=2)d=Math.max(d,Math.abs(parseInt(a.substr(i,2),16)-parseInt(b.substr(i,2),16)));return d;}
function store(){try{var o=JSON.parse(localStorage.getItem('alto-sh-root')||'{}');return o&&typeof o==='object'&&!o.pop?o:{};}catch(e){return {};}}
function known(g){return g.st==='holo'?HG[g.dk?'dark':'light']:g.st==='retro'?'#000000':
 !g.st&&g.w&&!g.bg?'#b4d6ff':      // (Classic's board top: the page's first stop under the glass)
 // (sim1112a R7) Classic's homepage on its side: its header glass over the page's gradient at the screen's top (homeTop() below measures the same)
 g.home?(g.dk?'__HOME_D__':'__HOME_L__'):null;}
function pick(g){var v=store()[g.k],c=v&&v.pop&&/^#[0-9a-f]{6}$/i.test(v[0])&&day()-v[1]>=0&&day()-v[1]<=30&&!BAD.test(v[0])?v[0]:null,kn=known(g);
 if(c&&g.home&&far(c,kn)>24)c=null;return c||kn;}
function keep(c){if(!PH)return;try{var g=sig();if(c&&(BAD.test(c)||!/^#[0-9a-f]{6}$/i.test(c)))c=null;if(S.kept===g.k+'='+c)return;S.kept=g.k+'='+c;var o=store(),v=o[g.k];if(c?v&&v.pop&&v[0]===c&&v[1]===day():!v)return;if(c)o[g.k]=[c,day()];else delete o[g.k];
 var ks=Object.keys(o);ks.forEach(function(n){var q=o[n];if(!q||!q.pop||!(day()-q[1]<=30))delete o[n];});ks=Object.keys(o);if(ks.length>60)delete o[ks[0]];localStorage.setItem('alto-sh-root',JSON.stringify(o));}catch(e){}}
// (theme-color too: its tag comes after this script in <head> and the theme script writes its own peach / brown into it, so until the first measured pass the
// tag is watched and says what the root says)
function root(c){de.style.setProperty('background-color',c,'important');S.rc=c;var m=document.getElementById('meta-theme');if(m&&m.content!==c)m.content=c;
 if(!S.mo&&!S.ran&&window.MutationObserver){S.mo=new MutationObserver(function(){var m=document.getElementById('meta-theme');if(m&&S.rc&&m.content!==S.rc)m.content=S.rc;});S.mo.observe(de,{childList:true,subtree:true,attributes:true,attributeFilter:['content']});}}
(function early(){if(!PH)return;var g=sig(),c=pick(g);S.o=g.ld;if(c){root(c);S.early=c;}})();
// A turn: Safari tints its toolbar again as the screen turns, long before the measured pass below (150 ms after the last resize, ~570 ms in). So the root takes the
// new way up's colour at once, on orientationchange itself: the kept one, else the look's known one; a homepage with neither goes back to its stylesheet's.
function turn(){if(!PH)return;var g=sig();if(S.o===g.ld)return;S.o=g.ld;var c=pick(g);S.turned=c;if(c)root(c);
 else if(de.classList.contains('alto-home')&&!S.board){['background','background-color'].forEach(function(n){de.style.removeProperty(n);});
  // (sim1112c T3: theme-color too. It still said the header glass of the page on its side; it says what a page opened this way up says)
  if(S.rc&&!de.classList.contains('alto-bg')&&window.setThemeMeta)window.setThemeMeta(de.classList.contains('dark'));S.rc=null;}}
function rgb(s){var p=(s||'').match(/[\d.]+/g);return p&&p.length>2?{r:+p[0],g:+p[1],b:+p[2],a:p.length>3?+p[3]:1}:null;}
function hex(c){return '#'+[c.r,c.g,c.b].map(function(v){return ('0'+Math.round(v).toString(16)).slice(-2);}).join('');}
var GR=/^(app|canvas|projects-wrap|wpal-root)$/,TOP=/^(nav|title-bar)$/;
// (fable, 11 Nov) A strip is never a flat band where the ground is not flat: it carries the ground's own repeating layers (Holo's grid, the System's star
// tiles) on the ground's own lattice, over the ground's edge colour, so the picture the reader sees runs on under Safari's bars.
function split(s){var o=[],d=0,a=0;for(var i=0;i<s.length;i++){var ch=s.charAt(i);if(ch==='(')d++;else if(ch===')')d--;else if(ch===','&&!d){o.push(s.slice(a,i).trim());a=i+1;}}o.push(s.slice(a).trim());return o;}
function lay(e,end){var c=getComputedStyle(e),R=e.getBoundingClientRect(),im=c.backgroundImage==='none'?[]:split(c.backgroundImage),sz=split(c.backgroundSize),ps=split(c.backgroundPosition),rp=split(c.backgroundRepeat),o=[],base=null;
 im.forEach(function(g,i){var s=sz[i%sz.length],p=ps[i%ps.length],r=rp[i%rp.length],m,cs;
  if(i===im.length-1&&/^(linear|radial)-gradient/.test(g)){cs=(g.match(/rgba?\([^)]+\)/g)||[]).map(rgb);if(cs.length>1&&cs[0].a>.9&&cs[cs.length-1].a>.9){base=/^radial/.test(g)?cs[cs.length-1]:cs[end?cs.length-1:0];return;}}
  // a soft glow laid out in % of the ground's box (the System's nebulae) runs on past the box at the same place and size, in px
  if(s==='auto'&&(m=g.match(/^radial-gradient\(([\d.]+)% ([\d.]+)% at ([\d.]+)% ([\d.]+)%, (.*)\)$/))){o.push({rad:[m[1]/100*R.width,m[2]/100*R.height,R.left+m[3]/100*R.width,R.top+m[4]/100*R.height,m[5]]});return;}
  if(r!=='repeat'||(s==='auto'&&!/^(url\(|repeating-)/.test(g)))return;
  m=p.match(/^(-?[\d.]+)(px|%) (-?[\d.]+)(px|%)$/);if(!m||(m[2]==='%'&&+m[1])||(m[4]==='%'&&+m[3]))return;
  if(s==='auto'){if(!/^url/.test(g))s=R.width+'px '+R.height+'px';}else if(!/^[\d.]+px [\d.]+px$/.test(s))return;
  o.push({g:g,s:s,x:R.left+ +m[1],y:R.top+ +m[3]});});
 if(!base){var b=rgb(c.backgroundColor);if(b&&b.a>.9)base=b;}
 return {o:o,base:base};}
// #page-glass (a white veil, pointer-events:none) lies over some grounds (Holo's card view) and under others (its whole view): it is made hittable for the
// one lookup, so the hit order, which is the paint order, says which; a strip then goes under the glass or over it exactly as its ground does
function ground(y,end){var pg=document.getElementById('page-glass'),L=[],u=0,es;if(pg)pg.style.pointerEvents='auto';es=document.elementsFromPoint(innerWidth/2,y);if(pg)pg.style.pointerEvents='';
 for(var i=0;i<es.length;i++){var e=es[i];if(e===de)break;if(e===pg){u=1;continue;}
  if(e===document.body||GR.test(e.id)||(!end&&TOP.test(e.id))){var l=lay(e,end);L=L.concat(l.o);if(l.base)return {c:hex(l.base),L:L,u:u};}}
 // #page-bg's own plain colour: it already runs through the runway itself (real pixels), so the root takes the colour and no strip is laid over it
 var pb=document.getElementById('page-bg');if(pb&&!de.classList.contains('alto-bg')){var b=rgb(getComputedStyle(pb).backgroundColor);if(b&&b.a>.9)return {c:hex(b),real:1};}
 return null;}
// Classic's whole view: the board is #page-bg's gradient under #page-glass; the root gets the same picture at the same place (the runway box), so whatever Safari shows
// behind its bars and at the side strips is the board's own continuation, never the root's differently scaled gradient
// (sim1111f S4: the board the reader sees is #glass-slab, the units' own colour bands at .7 over that picture; the root now carries the slab's gradient
// too, at the slab's own box, and its plain colour is the board's colour at the screen's top: Safari tints its landscape bars from that colour alone)
function stops(g){var o=[],re=/(rgba?\([^)]+\))\s*([\d.]+)%/g,m;while((m=re.exec(g)))o.push([rgb(m[1]),+m[2]/100]);return o;}
function at(st,f){if(!st.length)return null;if(f<=st[0][1])return st[0][0];for(var i=1;i<st.length;i++)if(f<=st[i][1]){var a=st[i-1],b=st[i],u=(f-a[1])/Math.max(b[1]-a[1],1e-6);
 return {r:a[0].r+(b[0].r-a[0].r)*u,g:a[0].g+(b[0].g-a[0].g)*u,b:a[0].b+(b[0].b-a[0].b)*u,a:a[0].a+(b[0].a-a[0].a)*u};}return st[st.length-1][0];}
function over(t,u){return {r:t.r*t.a+u.r*(1-t.a),g:t.g*t.a+u.g*(1-t.a),b:t.b*t.a+u.b*(1-t.a),a:1};}
// the board's colour at a screen point: the slab's band over the glass over the page's own gradient there (150deg, as #page-bg draws it)
function pbAt(ps,R,x,y){var A=150*Math.PI/180,dx=Math.sin(A),dy=-Math.cos(A),len=Math.abs(R.width*dx)+Math.abs(R.height*dy);
 return at(ps,Math.min(1,Math.max(0,((x-R.left-R.width/2)*dx+(y-R.top-R.height/2)*dy)/len+.5)));}
function slab(){var sl=document.getElementById('glass-slab'),c=sl&&getComputedStyle(sl);if(!sl||!de.classList.contains('phone-whole')||c.display==='none'||c.visibility==='hidden'||c.backgroundImage==='none')return null;
 var R=sl.getBoundingClientRect();return R.width>2&&R.height>2?sl:null;}
function board(){var pb=document.getElementById('page-bg'),pg=document.getElementById('page-glass'),sl=slab(),w=document.getElementById('world');
 if(!pb||!de.classList.contains('phone-whole'))return null;var g=getComputedStyle(pb).backgroundImage;if(de.classList.contains('alto-bg')||!/^linear-gradient\(150deg/.test(g))return sl?{sl:sl}:null;
 var glc=pg&&getComputedStyle(pg).backgroundColor,gl=rgb(glc),ps=stops(g),PR=pb.getBoundingClientRect(),sg=sl&&getComputedStyle(sl).backgroundImage,SR=sl&&sl.getBoundingClientRect(),
  hz=sg&&/^linear-gradient\(90deg, rgba/.test(sg),ss=sg&&/^linear-gradient\((90deg, )?rgba/.test(sg)&&SR.height>0?stops(sg):null;
 // the slab's gradient runs over its own top / height (its box is drawn taller for the runway), in #world's zoomed px; its backdrop is saturated and brightened
 var z=w&&parseFloat(getComputedStyle(w).zoom)||1,st=sl&&parseFloat(sl.style.top),sh=sl&&parseFloat(sl.style.height),GT=SR&&(isNaN(st)||isNaN(sh)?SR.top:(w?w.getBoundingClientRect().top:0)+st*z),GH=SR&&(isNaN(st)||isNaN(sh)?SR.height:sh*z);
 var bf=sl?getComputedStyle(sl).backdropFilter||getComputedStyle(sl).webkitBackdropFilter||'':'',sa=+((bf.match(/saturate\(([\d.]+)/)||[])[1]||1),br=+((bf.match(/brightness\(([\d.]+)/)||[])[1]||1);
 var fx=function(c){var R=c.r,G=c.g,B=c.b,cl=function(v){return Math.max(0,Math.min(255,v*br));};
  return {r:cl((.213+.787*sa)*R+(.715-.715*sa)*G+(.072-.072*sa)*B),g:cl((.213-.213*sa)*R+(.715+.285*sa)*G+(.072-.072*sa)*B),b:cl((.213-.213*sa)*R+(.715-.715*sa)*G+(.072+.928*sa)*B),a:1};};
 var col=function(x,y){var c=pbAt(ps,PR,x,y)||{r:255,g:201,b:138,a:1};if(gl&&gl.a>0)c=over(gl,c);if(ss){var t=at(ss,hz?(x-SR.left)/SR.width:(y-GT)/GH);if(t)c=over(t,fx(c));}return hex(c);};
 return {img:(gl&&gl.a>0?'linear-gradient('+glc+','+glc+'),':'')+g,c:col(innerWidth/2,0),sl:sl};}
// The board's continuation where Safari shows the page round the board: the runway above and below it, the bands beside it (4 px upright, the insets on its
// side). (fable, 11 Nov) Each is the glass slab itself carried on: the slab's own gradient laid on the slab's own box, through the slab's own backdrop filter,
// over the same #page-bg and #page-glass (which already run through the runway). The browser draws both by one recipe, so there is no seam to see; the
// sampled colours they replace were up to 10 levels off the board (lanes: 100, its slab runs sideways). Where the slab stops short of an edge, so do they.
function bstrips(bd){var ids=['sh-bt','sh-bb','sh-bl','sh-br'],sl=bd&&bd.sl,cv=document.getElementById('canvas');
 if(!sl||!document.body){ids.forEach(function(i){var e=document.getElementById(i);if(e)e.remove();});return;}
 var B=document.body.getBoundingClientRect(),SR=sl.getBoundingClientRect(),CR=cv?cv.getBoundingClientRect():B,c=getComputedStyle(sl),w=document.getElementById('world'),z=w&&parseFloat(getComputedStyle(w).zoom)||1,
  bf=(c.backdropFilter||c.webkitBackdropFilter||'none').replace(/blur\(([\d.]+)px\)/,function(m,v){return 'blur('+(v*z).toFixed(2)+'px)';}),      // (the slab's blur is drawn under #world's zoom)
  img=c.backgroundImage,hz=/^linear-gradient\(90deg/.test(img),cs=img.match(/rgba?\([^)]+\)/g)||[],flat=function(k){return 'linear-gradient('+k+','+k+')';},
  bt=hz||c.backgroundClip!=='padding-box'?0:(parseFloat(c.borderTopWidth)||0)*z,
  l=Math.max(SR.left,CR.left)-B.left,r=Math.min(SR.right,CR.right)-B.left,t=Math.max(SR.top,CR.top)-B.top,b=Math.min(SR.bottom,CR.bottom)-B.top,W=B.width,H=B.height,
  up=t<=1,dn=b>=H-1,y0=up?0:t,y1=dn?H:b,
  box=[up?[0,-80,W,80]:0,dn?[0,H,W,140]:0,l>.5&&y1>y0?[0,y0,l,y1-y0]:0,W-r>.5&&y1>y0?[r,y0,W-r,y1-y0]:0];
 ids.forEach(function(i,n){var e=document.getElementById(i),q=box[n];if(!q){if(e)e.remove();return;}
  if(!e){e=document.createElement('div');e.id=i;e.setAttribute('aria-hidden','true');var pg=document.getElementById('page-glass');
   if(pg&&pg.parentNode)pg.parentNode.insertBefore(e,pg.nextSibling);else document.body.appendChild(e);}
  // the slab's bands run on past its box: a sideways slab (lanes) at any height, an upright one in its first / last colour above / below its box
  // (clear_top.py draws the slab's first colour as a border above its box, so the gradient keeps its stops: the gradient's own box starts under that border)
  var gx=SR.left-B.left-q[0],gy=Math.round(SR.top+bt-B.top-q[1]),gh=Math.round(SR.height-bt),L=[hz?img+' '+gx+'px 0px / '+SR.width+'px 100% no-repeat':img+' 0px '+gy+'px / 100% '+gh+'px no-repeat'];
  if(hz&&cs.length){gx=Math.round(gx);var gw=Math.round(SR.width);L[0]=img+' '+gx+'px 0px / '+gw+'px 100% no-repeat';if(gx>0)L.push(flat(cs[0])+' 0px 0px / '+gx+'px 100% no-repeat');
   if(gx+gw<q[2])L.push(flat(cs[cs.length-1])+' '+(gx+gw)+'px 0px / '+Math.ceil(q[2]-gx-gw)+'px 100% no-repeat');}
  if(!hz&&cs.length){if(gy>0)L.push(flat(bt&&rgb(c.borderTopColor).a>0?c.borderTopColor:cs[0])+' 0px 0px / 100% '+gy+'px no-repeat');if(gy+gh<q[3])L.push(flat(cs[cs.length-1])+' 0px '+(gy+gh)+'px / 100% '+Math.ceil(q[3]-gy-gh)+'px no-repeat');}
  var css='position:absolute;z-index:0;pointer-events:none;left:'+q[0]+'px;top:'+q[1]+'px;width:'+q[2]+'px;height:'+q[3]+'px;background:'+L.join(',')+';opacity:'+c.opacity+';-webkit-backdrop-filter:'+bf+';backdrop-filter:'+bf;      // (on a chosen background the slab is half clear, with no filter: so are they)
  if(e.style.cssText!==css)e.style.cssText=css;});}
function lcss(q,ox,oy){return q.rad?'radial-gradient('+q.rad[0].toFixed(1)+'px '+q.rad[1].toFixed(1)+'px at '+(q.rad[2]-ox).toFixed(1)+'px '+(q.rad[3]-oy).toFixed(1)+'px, '+q.rad[4]+') 0px 0px / 100% 100% no-repeat':
  q.g+' '+(q.x-ox)+'px '+(q.y-oy)+'px / '+q.s+' repeat';}
function strip(id,top,col,g,side){var s=document.getElementById(id),pg=document.getElementById('page-glass');if(!s&&document.body){s=document.createElement('div');s.id=id;s.setAttribute('aria-hidden','true');
  if(pg&&pg.parentNode)pg.parentNode.insertBefore(s,pg.nextSibling);else document.body.appendChild(s);}      // (above the glass: its white is not laid over the strip, as it is not over the ground)
 if(!s)return;var B=document.body.getBoundingClientRect(),oy=top?B.top-80:B.bottom,
  bg=((g&&g.L)||[]).map(function(q){return lcss(q,B.left,oy);}).concat([col]).join(','),
  css='position:absolute;left:0;right:0;z-index:'+(pg&&!(g&&g.u)?0:-1)+';pointer-events:none;'+(top?'top:-80px;height:80px':'bottom:-140px;height:140px')+';background:'+bg;
 // on its side the whole view's canvas sits between the island's insets: the bands beside it carry the ground on too (side = [x, width] in the body)
 if(side){oy=B.top;bg=((g&&g.L)||[]).map(function(q){return lcss(q,B.left+side[0],oy);}).concat([col]).join(',');
  css='position:absolute;top:0;bottom:0;left:'+side[0]+'px;width:'+side[1]+'px;z-index:'+(pg&&!(g&&g.u)?0:-1)+';pointer-events:none;background:'+bg;}
 if(s.style.cssText!==css)s.style.cssText=css;}
function sides(t,g){var cv=document.getElementById('canvas'),B=document.body.getBoundingClientRect(),CR=cv&&de.classList.contains('phone-whole')&&cv.getBoundingClientRect(),
 l=CR?CR.left-B.left:0,r=CR?B.right-CR.right:0;
 [['sh-gl',l>.5&&[0,l]],['sh-gr',r>.5&&[B.width-r,r]]].forEach(function(q){var e=document.getElementById(q[0]);if(!t||!q[1]||(g&&g.real)){if(e)e.remove();return;}strip(q[0],1,t,g,q[1]);});}
// (sim1112a R7) Classic's homepage on a phone on its side (its desktop layout, no runway): no opaque ground, so the root kept Classic's peach and Safari's toolbar was a flat
// peach band over a page whose top is the header's pale glass. Its ground at the screen's top is that glass over the page's own gradient there: the root and theme-color take it.
function homeTop(){var pb=document.getElementById('page-bg'),tb=document.getElementById('title-bar'),pg=document.getElementById('page-glass');
 if(!pb||!tb||!de.classList.contains('alto-home')||de.classList.contains('alto-bg')||de.classList.contains('rw'))return null;
 var st=sig().st;if(st&&st!=='classic')return null;      // (a chosen Retro / Holo look that has not arrived yet: its own ground is on its way, Classic's is not kept for it)
 var g=getComputedStyle(pb).backgroundImage;if(!/^linear-gradient\(150deg/.test(g))return null;
 var c=pbAt(stops(g),pb.getBoundingClientRect(),innerWidth/2,0);if(!c)return null;
 [pg&&getComputedStyle(pg).backgroundColor,getComputedStyle(tb).backgroundColor,getComputedStyle(tb,'::before').backgroundColor].forEach(function(k){var q=rgb(k);if(q&&q.a>0)c=over(q,c);});
 return {c:hex(c),real:1};}
// the homepage's name tab hangs over that header glass, and frost over a pane that is already .82 white is a solid white box. The glass (#title-bar::before, pages.py) is cut away
// under the tab, so the tab frosts the page itself, as the corner toggles do: where the tab is, in the bar's own px
function hole(){var tb=document.getElementById('title-bar'),t=document.getElementById('title-text');if(!tb||!t||!de.classList.contains('alto-home'))return;
 var B=tb.getBoundingClientRect(),T=t.getBoundingClientRect(),z=parseFloat(getComputedStyle(tb).zoom)||1,v={'--hx0':(Math.round(T.left)+.5-B.left)/z,'--hx1':(Math.round(T.right)-.5-B.left)/z,'--hy':(Math.round(T.bottom)-.5-B.top)/z};      // (the tab is painted on whole px; half a px under its edge, never a hairline of bare page beside it)
 for(var n in v){var q=v[n].toFixed(2)+'px';if(tb.style.getPropertyValue(n)!==q)tb.style.setProperty(n,q);}}
S.paint=function(t,f,gt,gf){S.top=t;S.foot=f||t;var m=document.getElementById('meta-theme'),bd=!t&&de.classList.contains('rw')&&board();
 ['background-image','background-size','background-repeat','background-position'].forEach(function(n){de.style.removeProperty(n);});S.board=0;
 if(bd&&bd.c){S.board=1;var v={'background':bd.c,'background-image':bd.img,'background-size':'100% calc(100dvh + 220px)','background-repeat':'no-repeat','background-position':'0 0'};
  for(var n in v)de.style.setProperty(n,v[n],'important');if(m&&m.content!==bd.c)m.content=bd.c;keep(bd.c);}
 bstrips(bd);
 if(bd&&!bd.c)S.board=1;
 sides(de.classList.contains('rw')?t:null,gt);
 if(!t){if(!bd||!bd.c){de.style.removeProperty('background');keep(null);}['sh-top','sh-foot'].forEach(function(i){var s=document.getElementById(i);if(s)s.remove();});return;}
 de.style.setProperty('background',t,'important');if(m&&m.content!==t)m.content=t;keep(t);
 if(!de.classList.contains('rw')||(gt&&gt.real)){['sh-top','sh-foot'].forEach(function(i){var s=document.getElementById(i);if(s)s.remove();});return;}
 strip('sh-top',1,t,gt);strip('sh-foot',0,S.foot,gf);};
// the insets and which way up, as the layout has them now. On every resize as it comes (sim1112b S6): the horizontal timeline is laid out again inside the same
// resize, and with the last way up's insets still on the canvas its first card was placed 62 px off.
function ins(){var p=document.getElementById('sh-probe');
 if(!p){p=document.createElement('div');p.id='sh-probe';p.style.cssText='position:absolute;visibility:hidden;pointer-events:none;top:0;left:0';document.body.appendChild(p);}
 var c=getComputedStyle(p),L=parseFloat(c.paddingLeft)||0,R=parseFloat(c.paddingRight)||0,vv=window.visualViewport,land=innerWidth>innerHeight;
 de.style.setProperty('--sh-top',c.paddingTop);de.style.setProperty('--sh-foot',c.paddingBottom);de.style.setProperty('--sh-left',L+'px');de.style.setProperty('--sh-right',R+'px');
 de.style.setProperty('--sh-h',(vv?vv.height:innerHeight)+'px');de.classList.toggle('sh-landscape',land);de.classList.toggle('sh-portrait',!land);return [L,R,land];}
function measure(){var q=ins(),L=q[0],R=q[1],land=q[2];
 var k=L+'/'+R+'/'+innerWidth;if(S.k&&S.k!==k)S.touched=0;S.k=k;
 [].forEach.call(document.querySelectorAll('.sh-l,.sh-r'),function(e){e.classList.remove('sh-l','sh-r');});
 if(!land||!(L||R))return;var W=innerWidth,all=document.querySelectorAll('body *');
 for(var i=0;i<all.length;i++){var e=all[i];if(e.closest('#world,#canvas svg,.sh-l,.sh-r,#nav-drawer,#detail-page,#notes-panel')||/^sh-[bg][tblr]$/.test(e.id))continue;
  var s=getComputedStyle(e);if((s.position!=='absolute'&&s.position!=='fixed')||s.display==='none'||s.visibility==='hidden')continue;
  var r=e.getBoundingClientRect();if(r.width<4||r.height<4||r.width>W*.4||r.left<0||r.right>W)continue;
  if(L&&r.left<L+4)e.classList.add('sh-l');else if(R&&r.right>W-R-4)e.classList.add('sh-r');}}
function run(){if(S.mo){S.mo.disconnect();S.mo=null;}S.ran=1;if(!(PH||de.classList.contains('rw'))||!document.body)return;de.classList.add('sh');measure();lanes();
 hole();var h=innerHeight,g1=ground(1,0),g2=ground(h-1,1);if(!g1&&PH)g1=homeTop();S.paint(g1&&g1.c,g2&&g2.c,g1,g2);refit();}
// the horizontal timeline's slab runs through the canvas's side padding (lanes.py slabX()): placed before the insets were known, or before a turn changed them, it is placed again
function lanes(){var c=document.getElementById('canvas'),sl=document.getElementById('glass-slab');if(!c||!sl||!de.classList.contains('alto-lanes')||!window._altoLanesSlab)return;
 var pl=de.classList.contains('phone-whole')&&parseFloat(getComputedStyle(c).paddingLeft)||0;if(Math.abs(-(parseFloat(sl.style.left)||0)-pl)>.5){try{window._altoLanesSlab();}catch(x){}}}
// the whole view's fitted board wider than the canvas between the insets (fitted before they were known, or a turn changed them): fit it again, unless a finger has zoomed it since
function refit(){var P=window._altoPhone,c=document.getElementById('canvas');if(S.touched||!de.classList.contains('phone-whole')||!P||!P.ov||P.ov.s>=.999||!c)return;
 if(c.scrollWidth>c.clientWidth+1){try{P.ovSet(0);c.scrollLeft=0;}catch(x){}}}
// (sim1112c T3) html.sh-fx: the homepage on its side has its header and its two ground layers fixed to the screen only once the page has been touched or has
// scrolled (SHELL_CSS); until then they lie at the top of the page, where they look the same
function fx(){if(!S.fx){S.fx=1;de.classList.add('sh-fx');}}
addEventListener('touchstart',function(){S.touched=1;fx();},{passive:true,capture:true});
addEventListener('scroll',function(){if(!S.fx&&!de.classList.contains('rw')&&(window.pageYOffset||0)>0)fx();},{passive:true});
var sf=0;addEventListener('scroll',function(){if(!S.board||sf)return;sf=requestAnimationFrame(function(){sf=0;if(S.board)S.paint(null,null);});},{passive:true,capture:true});
var tm;function soon(){clearTimeout(tm);tm=setTimeout(run,150);}
S.run=run;
document.addEventListener('DOMContentLoaded',function(){run();
 new MutationObserver(soon).observe(de,{attributes:true,attributeFilter:['class']});
});
addEventListener('load',function(){run();setTimeout(run,1600);setTimeout(run,4000);});
function rs(){turn();if(document.body&&de.classList.contains('sh'))ins();soon();}
addEventListener('resize',rs);addEventListener('orientationchange',rs);
})();"""

SHELL_CSS = ("html.rw #nav-drawer:not(.open):not(#_){box-shadow:none!important;}"
             # (sim1112b S1) Classic's homepage on a phone on its side: the root is the header glass's colour from the stylesheet itself, so it is there at the first layout
             # and at the layout of a turn whatever the script knows by then (the script's own measured colour, set inline, still wins)
             "@media (orientation:landscape) and (min-width:641px){html.sh-ph.alto-home:not(.alto-bg):not(.alto-retro):not(.alto-holo):not(.rw){background-color:__HOME_L__;}"
             "html.sh-ph.alto-home.dark:not(.alto-bg):not(.alto-retro):not(.alto-holo):not(.rw){background-color:__HOME_D__;}}"
             # (sim1112c T3) Classic's homepage opened on its side and turned upright: Safari's status-bar zone was a flat band of the root's colour (peach / brown) over the
             # upright page. A page opened upright has nothing fixed to the screen's top at any layout (the runway); this one had its header and its two ground layers
             # there from its first layout on. Until the page is touched or scrolls they are absolute at the page's top, the same pixels; then fixed, as before.
             "@media (orientation:landscape) and (min-width:641px) and (max-height:480px){html.sh-ph.alto-home:not(.alto-retro):not(.alto-holo):not(.sh-fx) :is(#page-bg,#page-glass,#title-bar):not(#_){position:absolute;}}"
             # lanes zoomed out (always, on a phone on its side): the board is #lanes-ov-sky, the slab faded out. The layer itself runs through the runway and
             # under the island's insets (the real background, not a strip), and the slab's strips fade with the slab
             "html.rw #lanes-ov-sky:not(#_){top:-80px!important;bottom:-140px!important;left:0!important;right:0!important;}"
             "html.rw :is(#sh-bt,#sh-bb,#sh-bl,#sh-br){transition:opacity .62s cubic-bezier(.25,.2,.4,1);}"
             "html.rw body:has(#lanes-ov-sky) :is(#sh-bt,#sh-bb,#sh-bl,#sh-br):not(#_){opacity:0!important;}"
             "#sh-probe{padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px);}"
             "html.sh.sh-landscape .sh-l:not(#_){translate:var(--sh-left) 0;}"
             "html.sh.sh-landscape .sh-r:not(#_){translate:calc(0px - var(--sh-right)) 0;}"
             # the whole view's board (unit chips and their numerals run to its edges) sits between the side insets; the shell refits it when they change
             "html.sh.sh-landscape.phone-whole:not(.alto-lanes) #canvas:not(#_){left:var(--sh-left,0px)!important;right:var(--sh-right,0px)!important;width:auto!important;}"
             # (sim1112a R4) the horizontal timeline: a canvas cut off at the insets cut its lines and its ground there, with strips beside it that never matched on a real phone. Its canvas runs
             # the screen's full width: the board is held between the insets by the canvas's own padding, the lines and the slab (lanes.py slabX()) run on under them
             "html.sh.sh-landscape.phone-whole.alto-lanes #canvas:not(#_){left:0!important;right:0!important;width:auto!important;padding-left:var(--sh-left,0px)!important;padding-right:var(--sh-right,0px)!important;}"
             # the homepage in landscape (its desktop layout, no runway): the bar's clef / wordmark, the list and the corner buttons clear of the island
             "html.sh.sh-landscape.alto-home #title-bar:not(#_){left:var(--sh-left);right:var(--sh-right);width:auto;}"
             "html.sh.sh-landscape.alto-home #projects-wrap:not(#_){margin-left:var(--sh-left);margin-right:var(--sh-right);}"
             "html.sh.sh-landscape.alto-home :is(#search-btn,#info-btn,#bg-toggle):not(#_){translate:calc(0px - var(--sh-right)) 0;}"
             "html.sh.sh-landscape.alto-home #account-btn:not(#_){translate:var(--sh-left) 0;}")


# Classic's homepage on a phone on its side: the header glass over the page's gradient at the top centre of an 874 x 292 screen, as homeTop() measures it
# (tests/test_phone_sim1112a.py holds the two equal). Only a first load's first layout uses these; after it the page's own measured colour is kept.
HOME_TOP = {"light": "#f7eef0", "dark": "#1b141a"}


def _strip_comments(js: str) -> str:
    return "\n".join(l for l in js.split("\n") if not l.lstrip().startswith("//"))


def head_block() -> str:
    """<head> markup for every top-level phone page (timeline and homepage); inert on a computer (no html.rw) and with ?shell=0."""
    import json
    from .holo import TOKENS
    from . import phone_touch
    js = _strip_comments(SHELL_JS).replace("__HOLO__", json.dumps({k: v["bg"] for k, v in TOKENS.items()}))
    js = js.replace("__HOME_L__", HOME_TOP["light"]).replace("__HOME_D__", HOME_TOP["dark"])
    return ('<script id="alto-shell-js">' + js + '</script>\n'
            '<style id="alto-shell">' + SHELL_CSS.replace("__HOME_L__", HOME_TOP["light"]).replace("__HOME_D__", HOME_TOP["dark"]) + '</style>\n'
            '<style id="alto-touch">' + phone_touch.CSS + '</style>')
