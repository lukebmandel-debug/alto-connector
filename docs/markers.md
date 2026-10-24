# Map markers: one behaviour for every map-like format (1.9.145)

Luke, 2026-10-22, on the Museum Palace blueprint: "When you're zooming in ... all the little buttons for nodes are shifting so much
and changing size that it looks like it's really glitchy. So anywhere this could be a problem across these sorts of formats, I want
you to make sure that there's an elegant solution."

A *marker* is anything pinned to a point of a map that should stay readable at every zoom: node chips, room pills, names, number
tags, unit chips. The map itself (streets, walls, bodies) scales with the zoom; markers do not.

## The rules

1. **Pinned, one size.** A marker sits at its anchor's place on screen plus an offset, and keeps one size on screen. While a zoom
   or pan runs, the only per-frame change is its transform (`translate3d`). Nothing is measured, laid out or re-chosen per frame.
2. **Layout once, after the gesture.** Collision placement (which side of a crowded anchor a marker takes) and level of detail
   (a title after the number, which names show) are decided when the gesture settles (~170 ms after the last input), and the
   change glides (~0.3 s) instead of jumping.
3. **Held decisions.** A marker keeps the place it had while that place is still free (tested with a few px of slack); a nearer
   place must be *clearly* free to win it back. Zoom thresholds are bands (on below one value, off above another), so nothing
   flips at the edge of a threshold.
4. **Fade, never pop.** Level-of-detail changes and hidden markers fade (opacity, then `visibility`), never `display:none`.
5. **Safari pinch.** A trackpad pinch in Safari is `gesturestart/gesturechange/gestureend` (scale since the start), not a
   ctrl-wheel. Handle both, `preventDefault` both.

## The module: `alto/build/markers.py`

`MARKERS_JS` defines `window.AltoMarkers` (idempotent, ~3 KB raw, ~0.9 KB gz) and `MARKERS_CSS` its two classes. Put it in a
**hosted** script where the page is near its size cap (the Museum blueprint prepends it to `/bldg/palace-building-*.js`).

| call | what it does |
|---|---|
| `AltoMarkers.settle(done, ms)` | returns `{poke(), now(), busy}`. `poke()` on every zoom/pan input; `done()` runs once, `ms` (170) after the last. |
| `AltoMarkers.place(items, st, o)` | stable collision placement in screen px. `items`: `[{id, x, y, w, h, c:[[dx,dy],...]}]`, most important first, `c` = allowed offsets nearest-home first. `st`: the layer's memory object (keep it across calls). `o`: `{gap, slack:3, ok(x,y,w,h), hide}`. Returns `{id: {dx, dy, on}}`. |
| `AltoMarkers.band(was, v, lo, hi)` | a held threshold: true above `hi`, false below `lo`, else `was`. |
| `AltoMarkers.at(el, x, y)` | `transform: translate3d(x px, y px, 0)`. |
| `AltoMarkers.show(el, on)` | toggles `.alto-mk-off` (fade out, then `visibility:hidden`). |
| `AltoMarkers.glide(layer, step, ms)` / `stop(layer)` | a settled re-layout glides: `step(k)` runs each frame with `k` eased 0..1 (~0.32 s) and the caller puts each marker k of the way from where it was to where it goes; `stop()` at the next input freezes them where they are. Driven in JS, never a CSS transition: WebKit let a running transform transition go on after its class was removed (blueprint fix, 2026-10-23). |
| `AltoMarkers.reg(key, fn)` / `debug(key)` | tests: `fn()` returns `[{id, x, y, w, h, ax, ay, op}]` in client px (`ax/ay` = the anchor). |

Give every marker the class `alto-mk`, put them in one absolutely positioned layer (`pointer-events:none` on the layer, `auto`
on the markers) over the map, and position each with `left:0; top:0` plus `AltoMarkers.at`.

## The pattern (from `palace_building_asset.py`)

```js
S.mkSet = AltoMarkers.settle(function(){ layout(true); }, 170);
function onViewChange(){            // every wheel / pinch / drag frame
  AltoMarkers.stop(S.layer); S.mkSet.poke(); move();
}
function move(){                    // per frame: transforms only
  S.markers.forEach(function(m){ AltoMarkers.at(m, ax(m) + m._o[0] - m._w / 2, ay(m) + m._o[1]); });
}
function layout(glide){             // once per settle
  S.near = AltoMarkers.band(S.near, zoom, LO, HI);           // level of detail, held
  var at = AltoMarkers.place(items(), S.st, {gap: 3});       // places, held
  S.markers.forEach(function(m){ m._o = [at[m.id].dx, at[m.id].dy]; AltoMarkers.show(m, at[m.id].on); });
  if(glide) AltoMarkers.glide(S.layer, function(k){ /* m._o = from + (to - from) * k */ move(); }); else move();
}
```

Work in the layer's own (unzoomed) px: anchor = (map point − view origin) × (layer width / view width). Never position with
`getBoundingClientRect` numbers directly: under Safari's page `zoom` those are zoomed px.

## Where it is applied

- **Museum Palace blueprint** (`palace_building_asset.py`): the chips moved out of the SVG into an HTML layer driven by the
  module; Safari pinch; eased +/− buttons; viewBox no longer rounded to 1 cm (it moved the whole drawing in ~3 px steps close in).
- **System** (`solar_draw.py`, all 2D styles): the same rules inline (the page is at its size cap): labels decided once a zoom
  settles, held places, level-of-detail thresholds as 4% bands, level-of-detail by fade, re-layout glides (`#canvas.sol-glide`).
- **City Mind Palace** (`palace.py`): a zoom runs as one transform of the whole board (the city is far too heavy to lay out
  per frame), and in WebKit any change inside its 11,000-shape drawing costs ~100-300 ms: a style or transform on even 20 labels,
  an opacity fade of the label layers, an inherited custom property on `#world`. So building number tags (HTML) keep their size by
  their own inline `scale` (free); names ride with the board and are fitted once it settles; a tag sent aside keeps its place
  while free (no glide: anything moving over the drawing repaints it every frame); the settle is confirmed a frame later (input queued behind a long frame never triggers a mid-pinch
  re-layout).
- **Map motion** (Luke, same day: "Frame rate of movement in mind palace map mode is glitchy"): what animates on the map (a
  route's flowing dashes, the transit chip route, a trip's rider) is drawn in `#pal-fx`, a mirror layer over the drawing, not
  inside it; the engine's pan variables are registered non-inherited on palace pages (`@property --pan-x … inherits:false`),
  so a fly / focus frame restyles `#world` alone; the station and directions pulses run three times, not forever. Measured
  frame times are in the release notes. Page bytes: net under v1.9.146.
- **Lanes**: measured clean. Its overview zoom scales the cards with the board (map content, one transform), and nothing hops.
- **3D Star chart** (`solar_3d.py`): labels follow their bodies per frame with `left/top` and appear / disappear by `display` at a
  size threshold. Left for the session that owns that file (it had uncommitted work there): move them to `translate3d` and fade
  them by the body's on-screen radius.

## Level of detail never moves a marker (blueprint fix, 2026-10-23)

Luke, 2026-10-23: "i still felt like the blueprint was glitchy with the card labels when zooming in/out." Measured in WebKit on a page
shaped like civ-pro-museum (47 chips on the ground floor): after a settle the chips glided by CSS transition, the next wheel event
removed the class, and WebKit let the transition run on, so chips drifted ~15 px a frame beside their anchors and then snapped (up to
380 px); and the title threshold widened every chip, so the whole set was re-placed (up to 233 px). Now the glide is driven per frame
(above), markers are placed by their short form only (the number), and a title is shown only where it has room, growing to the right
from the number's fixed left edge. A chip moves only when its number must step aside.

## Verifying

`AltoMarkers.debug(key)` each animation frame during a scripted zoom; jitter = frame-to-frame change of (marker − anchor) while
the gesture runs (should be ≤ 0.5 px) and of the marker's size (should be 0); after the settle, the largest single-frame move
should be a glide's step, not a jump.
