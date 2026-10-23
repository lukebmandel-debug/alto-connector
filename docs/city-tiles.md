# City tiles: the palace's city off the page (1.9.146)

A private page is one Firestore document (about 976 KB stored), and a city at full detail (all five boroughs of New York) is many times
that. Since this release the page carries only what the cards need, and the city comes from the site, in files named by the hash of
their content (immutable, kept by browsers).

| file | made | holds | budget (gzipped) |
|---|---|---|---|
| page core (`window._ALTO_PALACE`) | build | the cards: lots they stand on, floors, numbers, near streets, districts; the map's scalars and what the user's material decides (landmarks, banners, hypothetical lines and stops) | ≤ 40 KB of city data |
| `/cmap/b-<h12>.json` (base) | build (`palace_tiles.strip`) | the rest of the processed map: water, land, parks, roads at every zoom, transit, names, the zone round the cards at full detail, the lots, the fill-in's towers and the zone's level 2 | ≤ 350 KB (`BASE_MAX`; the build warns) |
| `/cmap/t-<h10>.json` (tiles) | set_up (`palace_tiles.cut`) | one 2048 px cell's detail outside the zone: blocks, loose lines, minor streets and their names, small parks, close-in neighbourhood names, levels 2-4 of the buildings | ≤ 64 KB (`TILE_MAX`; a bigger cell is split in quarters) |

## How a page gets its city

- **timeline.html and the offline copy** carry everything inline, between `/*<alto-cmap>*/` markers, plus the tiles within
  `OFFLINE_REACH` cells of the zone. Past those cells an offline copy shows the overview.
- **The site's pages** (private and hosted) come from `palace_tiles.strip`. It writes the base to the blob folder (`ALTO_TILES_DIR`,
  default `~/.cache/alto/cmap`) and replaces the inline city with the core and `LOADER_JS`. That loader is a synchronous request for
  the base, merged into `window._ALTO_PALACE` before the palace script runs, so nothing else changes.
  - A base that cannot be loaded leaves `P.none`: the cards stay usable.
- **Tiles** come from `TILES_JS`, spliced into the palace script only when `m.ct` has cells.
  - It runs when a view is at most `CT_ON` px wide; past `CT_OFF` the tiles fade out. The two values form a held band, as in
    docs/markers.md.
  - Cells in view plus one of margin are fetched centre-first, at most 4 at once, and drawn one per frame. Each tile's groups go
    under the base's own drawing in each layer.
  - Cells more than 3 away leave the DOM.
  - The buildings join the fill-in, where tiers 3-4 are drawn on the canvas.
  - Both the board and the phone's map page load tiles.
  - `window._altoCity.ensure(box, cb)` and `.streets(box)` are for code that needs the streets of a box outside the zone.

## Publishing

`palace_assets.BLOB_FOLDERS` includes `cmap`. Each `regenerate_site` publishes:
- every base the site's private pages name;
- every base those pages ever named (`published-<site>.txt` in the blob folder; a share is a copy of a page and still names its base);
- every tile those bases name.

A named file the blob folder lacks becomes a stale note, never a silent loss. Headers:
- bases: one literal immutable rule each;
- tiles: one regex rule with a one-week max-age. There may be thousands of tiles, and a 404 must not be cached for a year.

## New York at full detail (`city_outer_lattice.py`)

Brooklyn, Queens, the Bronx, Staten Island and upper Manhattan are drawn in place on Manhattan's page, through
`city_boroughs.Outer` (affine plus Manhattan's shore field). Each is processed a box of about 8 km at a time:

- `city_domains.detect` finds the grids. Membership uses the detection's own cells rasterised on the page (`Labels`), never the
  simplified polygons, which overlap.
- Each grid is straightened at its page angle. Its lines sit on a locally even ladder (`_even`), so neighbouring blocks are one
  size while the grid follows the real city.
- A block is a face of the street lattice: the cells joined across every side no street runs along. A face needs streets along
  half its edge (`ENCLOSED`) and must be smaller than `MAX_BLOCK_PX2`.
- Non-grid areas are smoothed real streets.
- Buildings are cached OSM footprints (`bld-*.json`) snapped into their face (`fill_records`) and encoded in the fill-in's own
  format.
- Also drawn:
  - tunnels under the water and ferries (`palace_crossings.py`);
  - the boroughs' landmarks with their own art (`LANDMARKS`, `palace_skyline`);
  - every neighbourhood name close in.
