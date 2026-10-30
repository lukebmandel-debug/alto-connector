# Chicago: Memory Palace preset and gate report

Preset `chicago` (`alto/build/city_presets.py`), branch `alto-city-chicago` on `alto-city-core` (from v1.9.189).
Box [41.853, -87.668, 41.910, -87.595], about 6.3 x 6.0 km: the Loop, the Near North Side to Division Street and Navy Pier,
the Near South Side to the edge of Chinatown, the West Loop to Ashland Avenue, the Lake Michigan shore.

## Result

**90.8 / 100, PASS**: no row fails. Built offline from the OSM cache with the fill-in buildings and the rules doc's
100-building, 6-section brief; JSON in `docs/cities/chicago_gate.json`.

| row | rule | w | status | measured |
|---|---|---|---|---|
| G1 | domains sane | 3 | ok | domains: 1 domains (grid -1.1° 27.6 km²) |
| G2 | phantom lines | 6 | ok | phantom: 17 of 89 lattice lines (19%) are under 25% real (median coverage 0.43) |
| G3 | landmark/stop displacement | 6 | warn | displacement: 64 points; 0 over 1.5 blocks, worst 1.47 (Merchandise Mart) |
| G4 | order | 6 | ok | order: 0 stop-order swaps; 0 of 6 avenues cross streets out of order |
| G5 | side of river/seam | 8 | ok | side: 0 of 6686 points on the wrong side (6626 lots checked) |
| G6 | seams | 6 | ok | seam_fidelity: no seams; tjoin: no lines end on a seam; cross_seam: 0 non-hinge lines cross a seam |
| G7 | dangling ends | 5 | warn | ends: 0 line ends land on nothing inside the grid; 4 run past its edge |
| G8 | avenues | 3 | ok | avenues: 7 avenues; 0 break the rules |
| G9 | transit | 6 | ok | transit: 0 transit problems (blue 16 turns stray 1.5, brown 6 turns stray 0.6, green 3 turns stray 0.9, orange 5 turns stray 0.9, pink 4 turns stray 0.5, purple 5 turns stray 0.6, red 7 turns stray 0.9, metra2 8 turns stray 0.8, nictd 2 turns stray 1.0) |
| G10 | highways | 4 | warn | 3 highways, 0 problems, 1 warnings (I-90 2 turns stray 1.3 x 6/6, I-290 1 turns stray 1.0 x 4/4, US-41 4 turns stray 1.3 x 3/6) |
| G11 | cut blocks | 3 | ok | cut: 0 of 1674 blocks cut or open (0.0%) |
| G12 | data size per km2 | 3 | ok | size: 8860x13990 px, 138 streets, 18 kB packed (0.48x Philadelphia 1.9.78 per km²) |
| G13 | page overlap | 3 | ok | overlap: one page region |
| G14 | landmark spacing / fronts | 6 | ok | spacing: no landmark pairs to compare; fronts: 21 landmark fronts; 0 over 1.0 block from the line of the street they stand on |
| G15 | dry land | 5 | ok | 0 points in water (-); 3 bands, 0 under 40 px; channels missing: none |
| G16 | parks | 3 | warn | 14 parks drawn; must-parks missing 0, named missing 2; 0 streets through a park (3 more the real street does too); 0 landmarks on a park |
| G17 | landmarks | 4 | ok | 15 landmarks drawn (8-24); 0 card overlaps |
| G18 | labels | 4 | ok | 3 top names at the whole-city zoom (x0.064): 0 overlap each other, 0 under a landmark name, 0 off the glass (5 landmark-name pairs meet: the page shows one) |
| G19 | page bytes | 6 | ok | stored page 528 KB with 100 buildings (fail > 976 KB, warn > 900 KB) |
| G20 | tiles | 3 | ok | base 81 KB gz (max 350); 33 tiles, largest 3 KB gz (max 64); 38 KB gz in all |
| G21 | build time | 2 | ok | set_up 13.6 s from the cache (warn > 60 s); map from cache |
| G22 | determinism | 3 | ok | two builds give identical map data |

## How the city is drawn

- One grid at about -1.1 degrees (the brief said -1.7; this is what the street field measures). The Chicago River splits it
  into two domains that city_engine joins back into one lattice (same angle, same block shape, shared street names), so
  every block is the same size and both banks keep their numbering. Diagonals: Milwaukee, Ogden (West and North) and
  Kingsbury, octilinear, at most two bends.
- Water: the river's three branches are preset `channels`, each a 100 px band, meeting at one point (Wolf Point);
  Lake Michigan is one sea body east of the shore (`city_coast.py`: OSM has the lake as a water relation, not a coastline).
- 15 landmark cards (towers at real height, the three courthouses for a law palace: Dirksen federal, Daley Center state,
  City Hall-County Building city), 14 parks, the CTA L (7 lines; the elevated Loop's five lines run in shared lanes
  7 px apart), Metra Electric and the South Shore Line, I-90/94, I-290 and Lake Shore Drive as highways.

## Fixed on the way (general, now on alto-city-core)

| was | now |
|---|---|
| no lake at all (the street query has no coastline and Lake Michigan is no water polygon there) | `city_coast.py`: one sea body from the shore's own OSM ways |
| only the South Branch drawn (a river shorter than 0.6 x the box was a creek); the three bands crossed at Wolf Point | named `channels` drawn whatever their length, run off the glass only where they leave the box |
| heavy lines ran through Grant Park to the lake | big parks are lattice holes; only a line whose real street crosses the park (Columbus Drive) stays |
| avenue order: Milwaukee 3/14, Ogden 2/10, Upper Wacker 1/8 | 0: order-aware avenue paths; crossings under 50 m apart are one intersection (Milwaukee/Halsted/Grand are 2 m apart) |
| 4 lots on the wrong bank of the North Branch | lots whose real place is across the water are dropped |
| two track stubs (a stop no street carried was dropped: Racine, Millennium Station) | track trimmed a block past the last drawn stop |

## What is left

- Warnings: Merchandise Mart stands 1.47 blocks from its real place; 4 line ends run past the lattice edge (Balbo Drive,
  Roosevelt Road, Lake Shore Drive, Elston Avenue); US-41 (Lake Shore Drive) has 1 of 3 interchanges off a crossing
  street; Northerly Island and Polk Bros Park are named but get no cells.
- Navy Pier is a named landmark but not a card: the lattice ends at the lakefront, so a card could only stand on the
  shore block, 13 blocks from the pier (G3 fails it). Drawing the pier needs a spur of lattice into the lake.
- Racine (Blue Line) and Millennium Station (Metra Electric) are not drawn as stops (no drawn street carries them).
  Of the Metra lines only Metra Electric (Millennium Station's) comes through the transit snap; the lines into Union
  Station, Ogilvie and LaSalle Street are not drawn (not diagnosed; each has only its terminal and a stop or two in the
  box). Union Station shows as a landmark card.
- The labels row is a Python estimate of the page's own sizes at a 1440 x 900 whole-city zoom; the five landmark-name
  pairs that meet there are left to the page's own priority rule. Footprint-scale (G17) and transit reach are not measured.
- Still to do on Home Desktop: Art's look check, the blind audit (14 WebKit views), the full test suite, the release.

## NYC

`docs/cities/nyc_gate.json`: the gate on the Manhattan street fixture only. The LayoutSpec extraction leaves NYC's layout
byte-identical (fixture hash 334b3e50a5e1edc1 before and after, pinned in `tests/test_city_core.py`). On that fixture G16/G17
fail because it has no parks or landmarks, and G5 reports 392 lots on the wrong side of the designed Hudson/East River bands,
the same on v1.9.189; it compares the bands with the OSM centre lines and needs a look with the full NYC build. G19-G22
need the five-borough build, not run in the cloud.

## Run it

    python -m alto.build.city_gate chicago --cache DIR --fetch --fill --json OUT.json --md OUT.md   # first run fetches
    python -m alto.build.city_gate chicago --cache DIR --fill                                         # then offline

`--fetch` uses the repo's own Overpass code (mirror fallback; from the cloud only overpass.openstreetmap.fr answered).
