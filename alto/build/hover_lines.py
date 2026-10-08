"""Hover lines on the clef, the wordmark and the timeline's name.

They lead somewhere (the homepage, the homepage, the top of the timeline) and say so
with a fine line that follows the shape of what is hovered: round the strokes of the
clef, round the letters of the wordmark and of the timeline's name, never a box.

Each is plain vector painting, so every engine draws the same line at every zoom
and pixel density:

  * the clef is strokes, so a copy of them, each a little wider and in the muted ink,
    sits behind the clef and shows a hair of itself all round it;
  * the wordmark is one filled path, which takes a muted stroke painted BEHIND its own
    fill (paint-order), so only the outer half of the stroke shows;
  * the timeline's name is text, so a copy of it with a text stroke sits behind it (a pseudo-element
    reading the name from data-t); paint-order is not honoured on HTML text, and a stroke over the
    fill would only make the name bold.

The stroke is sized from the mark's drawn size (the title bar is drawn at the page
zoom), so it is about a pixel and a half wherever the page is zoomed. No box around
anything changes (the way-back button keeps its distance from the clef; the homepage
and a timeline keep their title bars identical), and a phone has no hover.

The line touches the shape (no gap): a gap needs something to cut the line away from the
shape, and every way of doing that (an SVG mask or filter, painting the background colour
over it) either differs between Safari and Chrome or depends on what is behind the title bar.

Tried and dropped, so they are not tried again: an outline on an <svg> paints only its
four corners in WebKit and a 1px outline or shadow is a sub-pixel line under the page
zoom (nothing showed in Safari); a box of the right size beside each mark (not the
"form fitting" asked for); an SVG filter that grows the shape and takes the shape out of
the result (WebKit draws filters at one pixel per CSS pixel, so the line was a faint
smear on a retina screen, and Chrome drew it blocky)."""

CSS = """
/* hover lines (hover_lines.py) */
#title-bar .brand-mark .alto-ring{ display:none; }
html:not(.mobile):not(.printing) #title-bar .brand-mark:hover .alto-ring{ display:inline; }
#title-bar .brand-mark .alto-ring path{ stroke:var(--muted); }
#title-bar .brand-mark .alto-ring path.alto-head{ fill:var(--muted); }
html:not(.mobile):not(.printing) #title-bar .brand-mark:hover,
html:not(.mobile):not(.printing) #title-bar .brand-word:hover{ overflow:visible; }
html:not(.mobile):not(.printing) #title-bar .brand-word:hover .alto-word{
  stroke:var(--muted); stroke-width:var(--alto-hlw, 0); stroke-linejoin:round; paint-order:stroke fill; }
html:not(.mobile):not(.printing) #title-bar #title-text{ position:relative; z-index:0; }
html:not(.mobile):not(.printing):not(.alto-editing) #title-bar #title-text:hover::before{
  content:attr(data-t); position:absolute; left:0; top:0; z-index:-1; white-space:pre; pointer-events:none;
  color:var(--muted); -webkit-text-stroke:var(--alto-hlt, 2px) var(--muted); }
"""

# The line is this many drawn pixels wide outside the shape; the strokes below are twice it
# (half of a stroke is under the shape).
LINE = 1.0
TLINE = 0.6      # the name's letters are thin serifs: a finer line

JS = r"""(function(){
  var bar=document.getElementById('title-bar'); if(!bar || bar.getAttribute('data-hl')) return; bar.setAttribute('data-hl','1');
  var NS='http://www.w3.org/2000/svg', LINE=__LINE__, TLINE=__TLINE__;
  var mark=bar.querySelector('.brand-mark'), word=bar.querySelector('.brand-word'), ring=null;
  // The clef's strokes, copied behind it. Each copy keeps its own width in data-w; fit() adds the line.
  if(mark){
    var ink=mark.querySelector('.alto-ink'), head=mark.querySelector('.alto-head');
    if(ink && ink.parentNode){
      ring=document.createElementNS(NS,'g'); ring.setAttribute('class','alto-ring'); ring.setAttribute('aria-hidden','true');
      ring.setAttribute('fill','none'); ring.setAttribute('stroke-linecap','round'); ring.setAttribute('stroke-linejoin','round');
      [ink, head].forEach(function(src){
        if(!src) return; var c=src.cloneNode(true);
        c.removeAttribute('stroke'); c.removeAttribute('fill'); c.removeAttribute('id');
        Array.prototype.forEach.call(c.querySelectorAll('[id]'), function(e){ e.removeAttribute('id'); });
        var own=[]; if(c.nodeName==='path') own.push(c); Array.prototype.push.apply(own, c.querySelectorAll('path'));
        own.forEach(function(p){
          var host=p, w=null; while(host && host!==c.parentNode && w==null){ var a=host.getAttribute && host.getAttribute('stroke-width'); if(a!=null) w=parseFloat(a); host=host.parentNode; }
          if(w==null && src.getAttribute('stroke-width')!=null) w=parseFloat(src.getAttribute('stroke-width'));
          p.setAttribute('data-w', isFinite(w) ? w : 0);
        });
        ring.appendChild(c);
      });
      ink.parentNode.insertBefore(ring, ink);
    }
  }
  // drawn pixels -> the mark's own units
  function perPx(svg){
    var vb=svg.viewBox && svg.viewBox.baseVal, r=svg.getBoundingClientRect();
    return vb && vb.width && r.width ? vb.width / r.width : 0;
  }
  function fit(){
    var k;
    if(mark && ring && (k=perPx(mark))){
      Array.prototype.forEach.call(ring.querySelectorAll('path'), function(p){
        // a nested stroke-width on the path's own group is replaced by one on the path
        p.setAttribute('stroke-width', (+p.getAttribute('data-w') || 0) + 2*LINE*k);
      });
    }
    if(word && (k=perPx(word))) word.style.setProperty('--alto-hlw', (2*LINE*k).toFixed(3));
    // text-stroke is in CSS pixels of the element it sits on, which the title bar's zoom scales
    var tt=document.getElementById('title-text');
    if(tt){ tt.setAttribute('data-t', tt.textContent); var z=tt.getBoundingClientRect().height / (tt.offsetHeight || 1) || 1; tt.style.setProperty('--alto-hlt', (2*TLINE/z).toFixed(2)+'px'); }
  }
  [mark, word, document.getElementById('title-text')].forEach(function(e){ if(e) e.addEventListener('mouseenter', fit); });
})();"""


def block() -> str:
    return ('<style id="alto-hl-css">' + CSS + '</style><script id="alto-hl-js">'
            + JS.replace("__LINE__", str(LINE)).replace("__TLINE__", str(TLINE)) + "</script>")
