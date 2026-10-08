"""Hover lines on the clef, the wordmark and the timeline's name.

They lead somewhere (the homepage, the homepage, the top of the timeline) and say so
with the same hair line round them that the right-edge tabs draw. The line is a real
border of one visual pixel (--chip-rule, the chips' rule): an outline on an <svg> paints
only its four corners in WebKit, and a 1px outline or shadow is thinner than a device
pixel at the page zoom, so neither showed in Safari.

It must not change the boxes it surrounds (the clef's right edge is what the way-back
button keeps its distance from, and the homepage and a timeline keep their title bars
identical), so the line is drawn BESIDE them: a pseudo-element for the name, and for the
two <svg>s, which have none, a span each after them in the bar, shown by a sibling
selector (:hover ~). The spans are sized from the engine's own title bar: the clef is 42px
high and the wordmark 26px, 26px in from each edge, centred on the bar (a test measures
that they still enclose their marks)."""

CSS = """
/* hover lines (hover_lines.py) */
html:not(.mobile) #title-text{ position:relative; }
html:not(.mobile) #title-text::after{ content:''; position:absolute; inset:-2px -8px; box-sizing:border-box;
  border:var(--chip-rule, 1px) solid transparent; border-radius:7px; pointer-events:none; transition:border-color .18s; }
html:not(.mobile) #title-text:hover::after{ border-color:var(--muted); }
html:not(.mobile) #title-bar .alto-hl{ position:absolute; top:50%; transform:translateY(-50%); box-sizing:content-box;
  border:var(--chip-rule, 1px) solid transparent; border-radius:7px; pointer-events:none; transition:border-color .18s; }
html:not(.mobile) #alto-hl-mark{ left:calc(22px - var(--chip-rule, 1px)); width:calc(42px * 78 / 98 + 8px); height:46px; }
html:not(.mobile) #alto-hl-word{ right:calc(22px - var(--chip-rule, 1px)); width:calc(26px * 190.7 / 85.1 + 8px); height:30px; }
html:not(.mobile) #title-bar .brand-mark:hover ~ #alto-hl-mark,
html:not(.mobile) #title-bar .brand-word:hover ~ #alto-hl-word{ border-color:var(--muted); }
html.mobile #title-bar .alto-hl, html.printing #title-bar .alto-hl{ display:none; }
"""

JS = r"""(function(){
  var bar=document.getElementById('title-bar'); if(!bar || document.getElementById('alto-hl-mark')) return;
  ['mark','word'].forEach(function(k){
    var s=document.createElement('span'); s.id='alto-hl-'+k; s.className='alto-hl'; s.setAttribute('aria-hidden','true'); bar.appendChild(s);
  });
})();"""


def block() -> str:
    return '<style id="alto-hl-css">' + CSS + '</style><script id="alto-hl-js">' + JS + "</script>"
