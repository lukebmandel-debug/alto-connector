# Washington, D.C.: Memory Palace preset and gate report

Preset `dc` (`alto/build/city_presets.py`), branch `alto-city-dc` on `alto-city-core` (from v1.9.189).
Box [38.865, -77.072, 38.925, -76.982], about 7.8 x 6.7 km: the core of L'Enfant's plan with the National Mall and the
Capitol at its middle; west to Georgetown and the Potomac, east past Lincoln Park to the Anacostia, north to Florida
Avenue and U Street, south to the Navy Yard and East Potomac Park.

## Result

**89.8 / 100, PASS**: no row fails. Built offline from the OSM cache with the fill-in buildings and the rules doc's
100-building, 6-section brief: `python -m alto.build.city_gate dc --cache DIR --fill`; JSON in `docs/cities/dc_gate.json`.

| row | rule | w | status | measured |
|---|---|---|---|---|
| G1 | domains sane | 3 | ok | domains: 3 domains (grid -0.1° 33.9 km², free 0.0° 3.2 km², free 0.0° 1.2 km²) |
| G2 | phantom lines | 6 | ok | phantom: 52 of 231 lattice lines (23%) are under 25% real (median coverage 0.57) |
| G3 | landmark/stop displacement | 6 | warn | displacement: 52 points; 0 over 1.5 blocks, worst 1.30 (Foggy Bottom–GWU) |
| G4 | order | 6 | ok | order: 0 stop-order swaps; 0 of 18 avenues cross streets out of order |
| G5 | side of river/seam | 8 | ok | side: 0 of 10410 points on the wrong side (10364 lots checked) |
| G6 | seams | 6 | ok | seam_fidelity: no seams; tjoin: no lines end on a seam; cross_seam: 0 non-hinge lines cross a seam |
| G7 | dangling ends | 5 | warn | ends: 0 line ends land on nothing inside the grid; 7 run past its edge |
| G8 | avenues | 3 | ok | avenues: 25 avenues; 0 break the rules |
| G9 | transit | 6 | ok | transit: 0 transit problems (red 41 turns stray 1.9, blue 18 turns stray 2.3, orange 18 turns stray 1.5, silver 18 turns stray 1.5, green 10 turns stray 1.2, yellow 3 turns stray 1.1) |
| G10 | highways | 4 | warn | 10 highways, 0 problems, 2 warnings (12th Street Expressway 1 turns stray 1.1 x 2/2, 9th Street Expressway 0 turns stray 0.5 x 2/2, E Street Expressway 0 turns stray 0.3 x 2/2, I-66 1 turns stray 0.9 x 2/2, I-395 7 turns stray 0.8 x 5/5, I-695 4 turns stray 1.8 x 3/4, US-1 2 turns stray 0.5 x 1/1, US-29 1 turns stray 1.1 x 2/2, US-50 2 turns stray 0.6 x 2/2, DC-295 1 turns stray 0.2 x 2/2) |
| G11 | cut blocks | 3 | ok | cut: 0 of 2550 blocks cut or open (0.0%) |
| G12 | data size per km2 | 3 | ok | size: 18031x16120 px, 372 streets, 42 kB packed (0.84x Philadelphia 1.9.78 per km²) |
| G13 | page overlap | 3 | ok | overlap: one page region |
| G14 | landmark spacing / fronts | 6 | ok | spacing: 135 landmark pair-axes; 0 drawn too far or too close in blocks; median drawn/real N-S 1.09, E-W 1.1; fronts: 4 landmark fronts; 0 over 1.0 block from the line of the street they stand on |
| G15 | dry land | 5 | ok | 0 points in water (-); 4 bands, 0 under 40 px; channels missing: none |
| G16 | parks | 3 | warn | 36 parks drawn; must-parks missing 0, named missing 4; 0 streets through a park (18 more the real street does too); 4 landmarks on a park |
| G17 | landmarks | 4 | ok | 15 landmarks drawn (8-24); 0 card overlaps |
| G18 | labels | 4 | ok | 7 top names at the whole-city zoom (x0.056): 0 overlap each other, 0 under a landmark name, 0 off the glass (4 landmark-name pairs meet: the page shows one) |
| G19 | page bytes | 6 | ok | stored page 525 KB with 100 buildings (fail > 976 KB, warn > 900 KB) |
| G20 | tiles | 3 | ok | base 121 KB gz (max 350); 56 tiles, largest 5 KB gz (max 64); 73 KB gz in all |
| G21 | build time | 2 | warn | set_up 91.1 s from the cache (warn > 60 s); map from cache |
| G22 | determinism | 3 | ok | two builds give identical map data |

## How the city is drawn

- One grid at -0.1 degrees: the lettered streets (A to W Street) are its rows, the numbered streets its columns, both
  `must` lines. Two small free domains (Georgetown's edge, the Navy Yard bend) are drawn as free streets. Lines one
  street shares across a quadrant line (I Street Northwest / Northeast) are named per span, split on the crossing street.
- The L'Enfant avenues are forced `diagonals` drawn by `city_avenues.draw`: octilinear, at most 2 bends a piece, never
  also drawn as a lattice row (Pennsylvania, Rhode Island and New York are 21-24 degrees off, under the 25-degree snap).
  A piece that crosses two streets in the other order than the real avenue is split at a lattice node (at most twice).
  The circles are drawn as blocks.
- Water: the Potomac is the city's wide edge (a broad band west and south; Virginia across it is not drawn, nor
  Rosslyn's station or the George Washington Parkway). The Anacostia and the Washington Channel are preset `channels`;
  Rock Creek stops at its mouth. The Tidal Basin and the Reflecting Pools are still water: no block and no park cell.
- The National Mall is a lattice hole: its OSM pieces (the Mall, the Washington Monument Grounds) are one green, no street
  runs through it, and the Monument and the Castle stand in it with no street round them.
- 15 landmark cards, among them the Capitol, the White House, the Monument, the Lincoln and Jefferson Memorials, the
  Library of Congress, Union Station, the Castle and three Smithsonian museums. For a law palace there are three
  courthouses: the Supreme Court (federal), Prettyman (federal; OSM "E. Barrett Prettyman Federal Courthouse") and the
  DC Court of Appeals (Old City Hall). There are 36 parks.
- Transit and highways: the Metro's six lines in shared lanes downtown, and Union Station. I-395, I-695, I-66, US-29
  (Whitehurst Freeway) and US-50 are highways; K Street stays a street. Rock Creek and Potomac Parkway is a primary road
  in OSM, so it is drawn as an avenue, not a highway.

## Fixed on the way (general engine rules, not DC-only code)

| was | now |
|---|---|
| Pennsylvania, Rhode Island, New York Avenue drawn twice (a row and a diagonal) | a diagonal avenue is not also a lattice line |
| the wide edge river was a band only on an east edge; the Potomac drew narrow, hugged into the Mall | wide on any side; hugged to the blocks only on the east |
| Little River (Virginia) drawn; Rock Creek's run-off crossed the Potomac | a creek on the cut far bank is dropped; a tributary stops at its mouth |
| blocks and park cells in the Tidal Basin and the Reflecting Pool | still water of 0.5 ha or more takes no block and no park |
| Rosslyn station and the GW Parkway kept after the far bank was cut away | the far-bank cut also cuts the real transit and highways |
| the Mall's OSM pieces read as holes in each other; a line drawn between two parks that meet | one green; a segment between two parks is inside the park |
| a street drawn round the Monument and the Castle | a landmark standing in a park counts as park |
| Maryland Avenue through Stanton Park, North Capitol Street through Upper Senate Park | a line is cut at a small park its real street does not cross |
| avenue order 7 of 15 (Florida, Rhode Island, New Hampshire, Vermont ...) | 0 of 18: a piece that swaps two real crossings is split at a node, judged on the real streets' crossings (a street that ends on the avenue counts) |
| lots on the wrong side of Rock Creek | none (core's wrong-bank rule, now on for DC through `channels`) |
| displacement measured in 240 x 170 blocks on a 240 x 280 lattice | in the root lattice's own block |
| an avenue error string in the stage timings crashed the build it was meant to spare | timings sum numbers only |

## What is left

- G21 (warn): set-up 91 s from the cache (the avenue order splits cost about 30 s); the limit is 60 s.
- G16 (warn): Logan, Thomas, Scott and Washington Circles are not drawn as parks (each is smaller than a block); the
  Monument and the Castle stand in the Mall's green (as in reality).
- G3 (warn): Foggy Bottom-GWU station is 1.3 blocks from its mapped place. G7 (warn): 7 lines run past the grid's edge.
  G10 (warn): two highways with more turns than the rule likes; 0 problems.
- Rock Creek and Potomac Parkway is a primary road in OSM, so it is drawn as an avenue, not a highway (the brief listed it
  as a highway; forcing it would need a per-preset override).
- Not measured here: Art's look check (some avenues are drawn as several short pieces where they leave the blocks),
  the blind audit (14 views), Safari, the full test suite.
