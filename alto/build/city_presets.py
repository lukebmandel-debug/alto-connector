"""Built-in city presets for the Memory Palace: New York City, Boston, Washington, DC and Chicago.

A preset is the set_up_palace parameters a careful person would pass for that city (Philadelphia's are the model:
see set_up_palace's docstring), so set_up_palace("Boston") draws Boston well with no other argument. Any explicit
argument still overrides its field. Every other city goes through city_setup (the same fields, derived from OSM).

Fields (all names spelled as OpenStreetMap spells them):
  place, area, bbox [s, w, n, e] (5-8 km a side),
  majors             streets that keep their labels (and are always grid lines),
  landmarks          places drawn and labelled,
  landmark_buildings [{name, label?, floors?, height_m?}]: floors / height_m are the real building's (Skyscraper
                     Center / Wikipedia); set_up_palace uses floors only when the user makes the building a tower
                     (gives it a `unit`), see buildings_for(),
  diagonals          the slanting avenues to keep,
  far_bank           True: the box faces another shore across a wide river and keeps it (Brooklyn, Cambridge),
  layout             the city's LayoutSpec as data (city_spec; Chicago's: shore "sea", must-parks), optional,
  channels           the rivers drawn whatever their length, each kept at least 40 page px (Chicago's three branches),
  river_names        [[name, lat, lon]] points on the water: each water band is named by the nearest,
  parks              parks drawn whatever their size,
  areas              label-only neighbourhood names [{name, lat, lon, rank 1-4}],
  rail_lines         hypothetical railways: none,
  transit            the real networks [{id, name, colour, kind, network, operator, route, refs}]: one family per
                     trunk line, matched on the route relations' network + ref (None: any ref of that network).
                     This is the data-driven shape palace_map._TRANSIT_FAMILIES has as tuples; C2's reader takes it.
Districts are not part of a preset: they come from the user's sections.
"""
from __future__ import annotations

import copy
import re


def _a(rows):
    return [{"name": n, "lat": la, "lon": lo, "rank": r} for n, la, lo, r in rows]


def _both(*names, sides=("West", "East")):
    """'34th Street' -> ['West 34th Street', 'East 34th Street'] (Manhattan's cross streets), likewise DC quadrants."""
    return [f"{s} {n}" for n in names for s in sides]


def _q(*names, quads=("Northwest", "Northeast", "Southeast", "Southwest")):
    return [f"{n} {q}" for n in names for q in quads]


NYC = {
    "place": "New York City",
    "area": "Lower and Midtown Manhattan to 59th Street, with Brooklyn's and Queens's facing shores "
            "(Brooklyn Heights, DUMBO, Williamsburg, Greenpoint, Long Island City)",
    "bbox": [40.695, -74.02, 40.765, -73.94],
    "far_bank": True,
    # the water between the island and its far banks is drawn as bands (build/city_water.py); each is named by the nearest of these
    # points (on the water, beside the shore the band follows)
    "river_names": [["Hudson River", 40.7950, -74.0000], ["Hudson River", 40.7700, -74.0090], ["Hudson River", 40.7475, -74.0125],
                    ["Hudson River", 40.7250, -74.0190], ["East River", 40.7900, -73.9300], ["East River", 40.7650, -73.9560],
                    ["East River", 40.7400, -73.9660], ["East River", 40.7150, -73.9740], ["East River", 40.7050, -73.9830]],
    "majors": ["Broadway", "5th Avenue", "6th Avenue", "7th Avenue", "7th Avenue South",
               "8th Avenue", "9th Avenue", "10th Avenue", "11th Avenue", "12th Avenue", "Park Avenue",
               "Park Avenue South", "Madison Avenue", "Lexington Avenue", "3rd Avenue", "2nd Avenue", "1st Avenue",
               "Avenue A", "Avenue B", "Avenue C", "Avenue D", "Bowery", "West Street", "FDR Drive", "South Street",
               "Water Street", "Church Street", "Hudson Street", "Varick Street", "West Broadway", "Lafayette Street",
               "Centre Street", "Canal Street", "Grand Street", "Delancey Street", "East Broadway", "Chambers Street",
               "Greenwich Avenue", "East 59th Street",
               *_both("Houston Street", "14th Street", "23rd Street", "34th Street", "42nd Street", "57th Street"),
               # Brooklyn and Queens
               "Kent Avenue", "Bedford Avenue", "Metropolitan Avenue", "Flushing Avenue",
               "Cadman Plaza West", "Vernon Boulevard", "Jackson Avenue", "McGuinness Boulevard",
               "Manhattan Avenue"],
    "landmarks": ["Empire State Building", "One World Trade Center", "Chrysler Building", "Flatiron Building",
                  "Grand Central Terminal", "Pennsylvania Station", "Woolworth Building", "New York City Hall", "Times Square",
                  "Rockefeller Center", "United Nations Headquarters", "Madison Square Garden", "Washington Square Park",
                  "Union Square", "Bryant Park", "Madison Square Park", "National September 11 Memorial & Museum",
                  "Trinity Church", "Saint Patrick's Cathedral", "Stephen A. Schwarzman Building", "One Vanderbilt",
                  "Brooklyn Bridge Park", "The High Line"],
    "landmark_buildings": [
        {"name": "Empire State Building", "floors": 102, "height_m": 443},
        {"name": "One World Trade Center", "label": "One WTC", "floors": 94, "height_m": 541},
        {"name": "Chrysler Building", "floors": 77, "height_m": 319},
        {"name": "Woolworth Building", "floors": 57, "height_m": 241},
        {"name": "Flatiron Building", "floors": 22, "height_m": 87},
        {"name": "30 Rockefeller Plaza", "label": "30 Rock", "floors": 66, "height_m": 259},
        {"name": "432 Park Avenue", "floors": 85, "height_m": 426},
        {"name": "Bank of America Tower", "floors": 55, "height_m": 366},
        {"name": "One Vanderbilt", "height_m": 427},
        {"name": "Grand Central Terminal", "label": "Grand Central"},
        {"name": "Pennsylvania Station", "label": "Penn Station"},
        {"name": "New York City Hall", "label": "City Hall", "art": "nych"},
        {"name": "David N. Dinkins Manhattan Municipal Building", "label": "Municipal Building", "floors": 40, "height_m": 177},
        {"name": "United Nations Headquarters", "label": "United Nations"},
    ],
    "diagonals": ["Broadway"],
    "parks": ["Washington Square Park", "Union Square Park", "Madison Square Park", "Bryant Park", "Battery Park",
              "City Hall Park", "Gramercy Park", "Tompkins Square Park", "Stuyvesant Square", "Columbus Park",
              "Seward Park", "Hudson River Park", "The High Line", "Brooklyn Bridge Park", "McCarren Park",
              "Gantry Plaza State Park", "Domino Park", "Cadman Plaza Park", "Sara D. Roosevelt Park",
              "John V. Lindsay East River Park"],
    "areas": _a([
        ["Midtown", 40.7549, -73.9840, 1], ["Chelsea", 40.7465, -74.0014, 1], ["Greenwich Village", 40.7336, -74.0027, 1],
        ["East Village", 40.7265, -73.9815, 1], ["Lower East Side", 40.7150, -73.9843, 1], ["SoHo", 40.7233, -74.0030, 1],
        ["Tribeca", 40.7163, -74.0086, 1], ["Financial District", 40.7075, -74.0113, 1],
        ["Brooklyn Heights", 40.6960, -73.9950, 1], ["Williamsburg", 40.7081, -73.9571, 1],
        ["Greenpoint", 40.7300, -73.9540, 1], ["Long Island City", 40.7447, -73.9485, 1],
        ["West Village", 40.7358, -74.0036, 2], ["Chinatown", 40.7158, -73.9970, 2], ["Flatiron District", 40.7401, -73.9903, 2],
        ["Gramercy Park", 40.7368, -73.9845, 2], ["Murray Hill", 40.7479, -73.9757, 2], ["Hell's Kitchen", 40.7638, -73.9918, 2],
        ["Hudson Yards", 40.7536, -74.0010, 2], ["Battery Park City", 40.7115, -74.0160, 2], ["DUMBO", 40.7033, -73.9881, 2],
        ["Hunters Point", 40.7420, -73.9560, 2], ["Turtle Bay", 40.7527, -73.9680, 2],
        ["Little Italy", 40.7191, -73.9973, 3], ["Nolita", 40.7230, -73.9955, 3], ["NoHo", 40.7275, -73.9925, 3],
        ["Meatpacking District", 40.7409, -74.0080, 3], ["Kips Bay", 40.7420, -73.9800, 3],
        ["Stuyvesant Town", 40.7316, -73.9778, 3], ["Garment District", 40.7547, -73.9916, 3], ["Civic Center", 40.7135, -74.0035, 3],
        ["Theater District", 40.7590, -73.9865, 3], ["Tudor City", 40.7489, -73.9715, 4], ["Two Bridges", 40.7110, -73.9905, 4],
        ["Vinegar Hill", 40.7037, -73.9823, 4], ["Hudson Square", 40.7265, -74.0075, 4], ["Alphabet City", 40.7250, -73.9790, 3],
        ["Brooklyn Navy Yard", 40.7000, -73.9700, 3], ["Koreatown", 40.7477, -73.9869, 4], ["NoMad", 40.7450, -73.9880, 4],
    ]),
    "rail_lines": [],
    "transit": [
        {"id": "irt7", "name": "Broadway–Seventh Avenue Line", "colour": "#EE352E", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["1", "2", "3"]},
        {"id": "lex", "name": "Lexington Avenue Line", "colour": "#00933C", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["4", "5", "6", "<6>"]},
        {"id": "flu", "name": "Flushing Line", "colour": "#B933AD", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["7", "<7>"]},
        {"id": "ind8", "name": "Eighth Avenue Line", "colour": "#0039A6", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["A", "C", "E"]},
        {"id": "ind6", "name": "Sixth Avenue Line", "colour": "#FF6319", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["B", "D", "F", "<F>", "M"]},
        {"id": "bmtb", "name": "Broadway Line", "colour": "#FCCC0A", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["N", "Q", "R", "W"]},
        {"id": "nas", "name": "Nassau Street Line", "colour": "#996633", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["J", "Z"]},
        {"id": "can", "name": "Canarsie Line", "colour": "#A7A9AC", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["L"]},
        {"id": "cross", "name": "Crosstown Line", "colour": "#6CBE45", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["G"]},
        {"id": "shut", "name": "42nd Street Shuttle", "colour": "#808183", "kind": "metro", "network": "NYC Subway",
         "operator": "Metropolitan Transportation Authority", "route": "subway", "refs": ["S"]},
        {"id": "path", "name": "PATH", "colour": "#0082C6", "kind": "metro", "network": "PATH",
         "operator": "Port Authority of New York and New Jersey", "route": "subway", "refs": None},
        {"id": "lirr", "name": "Long Island Rail Road", "colour": "#4D5357", "kind": "rail", "network": "LIRR",
         "operator": "Metropolitan Transportation Authority", "route": "train", "refs": None},
        {"id": "njt", "name": "NJ Transit", "colour": "#1A2B57", "kind": "rail", "network": "NJ Transit",
         "operator": "NJ Transit", "route": "train", "refs": None},
        {"id": "mnr", "name": "Metro-North Railroad", "colour": "#0039A6", "kind": "rail", "network": "Metro-North Railroad",
         "operator": "Metropolitan Transportation Authority", "route": "train", "refs": None},
    ],
}

BOSTON = {
    "place": "Boston",
    "area": "Back Bay, Beacon Hill, Downtown, the North End, the South End, the Fenway and the Seaport, "
            "with Cambridge (Kendall Square, MIT) and Charlestown across the Charles",
    "bbox": [42.333, -71.105, 42.378, -71.035],
    "far_bank": True,
    "majors": ["Massachusetts Avenue", "Commonwealth Avenue", "Beacon Street", "Boylston Street", "Newbury Street",
               "Marlborough Street", "Huntington Avenue", "Columbus Avenue", "Tremont Street", "Washington Street",
               "Shawmut Avenue", "Harrison Avenue", "Albany Street", "Cambridge Street", "Charles Street",
               "Storrow Drive", "Memorial Drive", "Atlantic Avenue", "Congress Street", "Summer Street",
               "State Street", "Court Street", "Causeway Street", "Hanover Street", "Commercial Street",
               "Dartmouth Street", "Arlington Street", "Berkeley Street", "Clarendon Street", "Stuart Street",
               "Kneeland Street", "Seaport Boulevard", "Northern Avenue", "Brookline Avenue",
               # Cambridge and Charlestown
               "Main Street", "Broadway", "Vassar Street", "Rutherford Avenue"],
    "landmarks": ["Massachusetts State House", "Faneuil Hall", "Old North Church", "Old State House", "Boston Public Library",
                  "Trinity Church", "Prudential Tower", "200 Clarendon", "Fenway Park", "TD Garden", "Paul Revere House",
                  "Museum of Science", "Bunker Hill Monument", "USS Constitution", "Quincy Market", "Boston City Hall",
                  "Old South Meeting House", "Winthrop Center", "Massachusetts Institute of Technology", "South Station", "North Station"],
    "landmark_buildings": [
        {"name": "200 Clarendon", "label": "John Hancock Tower", "floors": 62, "height_m": 241},
        {"name": "Prudential Tower", "floors": 52, "height_m": 228},
        {"name": "Four Seasons Hotel One Dalton", "label": "One Dalton", "floors": 61, "height_m": 226},
        {"name": "Winthrop Center", "floors": 53, "height_m": 210},
        {"name": "Millenium Tower", "label": "Millennium Tower", "floors": 60, "height_m": 208},
        {"name": "Custom House Tower", "floors": 32, "height_m": 151},
        {"name": "Massachusetts State House", "label": "State House"},
        {"name": "Faneuil Hall"},
        {"name": "Old North Church"},
        {"name": "Boston Public Library"},
        {"name": "Trinity Church"},
        {"name": "Fenway Park"},
        {"name": "South Station"},
        {"name": "North Station"},
    ],
    "diagonals": ["Massachusetts Avenue", "Huntington Avenue", "Columbus Avenue", "Commonwealth Avenue"],
    "parks": ["Boston Common", "Boston Public Garden", "Commonwealth Ave Mall", "Charles River Esplanade",
              "Back Bay Fens", "Copley Square", "Christopher Columbus Waterfront Park", "Rose Kennedy Greenway",
              "Norman B. Leventhal Park", "Paul Revere Mall", "Statler Park", "Southwest Corridor Park", "Peters Park",
              "Langone Park", "City Square Park"],
    "areas": _a([
        ["Back Bay", 42.3503, -71.0810, 1], ["Beacon Hill", 42.3588, -71.0707, 1], ["North End", 42.3647, -71.0542, 1],
        ["Downtown", 42.3555, -71.0590, 1], ["South End", 42.3410, -71.0720, 1], ["Fenway", 42.3450, -71.1000, 1],
        ["Charlestown", 42.3750, -71.0600, 1], ["Cambridge", 42.3650, -71.0950, 1],
        ["West End", 42.3640, -71.0660, 2], ["Financial District", 42.3560, -71.0550, 2], ["Chinatown", 42.3500, -71.0620, 2],
        ["Seaport", 42.3500, -71.0420, 2], ["Kendall Square", 42.3629, -71.0861, 2], ["East Cambridge", 42.3700, -71.0800, 2],
        ["Government Center", 42.3597, -71.0590, 3], ["Theater District", 42.3510, -71.0645, 3], ["Fort Point", 42.3510, -71.0490, 3],
        ["Kenmore Square", 42.3489, -71.0952, 3], ["Cambridgeport", 42.3590, -71.1030, 3], ["Bay Village", 42.3486, -71.0687, 4],
        ["Leather District", 42.3507, -71.0577, 4], ["Bulfinch Triangle", 42.3640, -71.0610, 4], ["Lower Roxbury", 42.3365, -71.0790, 4],
    ]),
    "rail_lines": [],
    "transit": [
        {"id": "red", "name": "Red Line", "colour": "#DA291C", "kind": "metro", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "subway", "refs": ["Red"]},
        {"id": "orange", "name": "Orange Line", "colour": "#ED8B00", "kind": "metro", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "subway", "refs": ["Orange"]},
        {"id": "blue", "name": "Blue Line", "colour": "#003DA5", "kind": "metro", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "subway", "refs": ["Blue"]},
        {"id": "green", "name": "Green Line", "colour": "#00843D", "kind": "tram", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "light_rail", "refs": ["B", "C", "D", "E", "Green"]},
        {"id": "silver", "name": "Silver Line", "colour": "#7C878E", "kind": "brt", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "bus", "refs": ["SL1", "SL2", "SL3", "SL4", "SL5", "SLW"]},
        {"id": "cr", "name": "Commuter Rail", "colour": "#80276C", "kind": "rail", "network": "MBTA",
         "operator": "Massachusetts Bay Transportation Authority", "route": "train", "refs": None},
    ],
}

DC = {
    "place": "Washington, D.C.",
    # the box: the core of L'Enfant's plan, about 7.8 x 6.7 km, the National Mall and the Capitol at its middle: west to
    # Georgetown and the Potomac, east past Lincoln Park to the Anacostia, north to Florida Avenue (the old Boundary
    # Street) and U Street, south to the Navy Yard and East Potomac Park. The Potomac is the city's edge (wide, west and
    # south): Virginia across it is not drawn (palace_map's wide-river rule), nor its stations and highways.
    "area": "L'Enfant's city: the National Mall and the Capitol, Downtown, Foggy Bottom and the Georgetown edge, "
            "Dupont and Logan Circles, Capitol Hill, Navy Yard and the Anacostia River",
    "bbox": [38.865, -77.072, 38.925, -76.982],
    # short in the box, but real water: the Anacostia (east) and the Washington Channel (between the Southwest Waterfront
    # and East Potomac Park); Rock Creek is long enough to be drawn anyway
    "channels": ["Anacostia River", "Washington Channel"],
    "layout": {"name": "dc", "builder": "engine", "must_parks": ["National Mall"]},
    "majors": [*_q("Pennsylvania Avenue", quads=("Northwest", "Southeast")),
               *_q("Constitution Avenue", quads=("Northwest", "Northeast")),
               *_q("Independence Avenue", quads=("Southwest", "Southeast")),
               *_q("Massachusetts Avenue", quads=("Northwest", "Northeast", "Southeast")),
               *_q("New York Avenue", quads=("Northwest", "Northeast")),
               "Connecticut Avenue Northwest", "Vermont Avenue Northwest", "New Hampshire Avenue Northwest",
               *_q("Rhode Island Avenue", quads=("Northwest", "Northeast")),
               *_q("Virginia Avenue", quads=("Northwest", "Southeast")),
               *_q("Maryland Avenue", quads=("Northeast", "Southwest")),
               *_q("New Jersey Avenue", quads=("Northwest", "Southeast")),
               *_q("Florida Avenue", quads=("Northwest", "Northeast")),
               "Wisconsin Avenue Northwest", "Georgia Avenue Northwest", "Maine Avenue Southwest",
               "North Capitol Street Northwest", "North Capitol Street Northeast", "East Capitol Street",
               "South Capitol Street Southeast", "South Capitol Street Southwest",
               *_q("K Street", quads=("Northwest", "Northeast")), *_q("H Street", quads=("Northwest", "Northeast")),
               *_q("M Street", quads=("Northwest", "Southeast", "Southwest")), "U Street Northwest", "P Street Northwest",
               "E Street Northwest", "F Street Northwest", "I Street Northwest", "L Street Northwest",
               "7th Street Northwest", "7th Street Southwest", "9th Street Northwest", "14th Street Northwest",
               "14th Street Southwest", "15th Street Northwest", "16th Street Northwest", "17th Street Northwest",
               "18th Street Northwest", "23rd Street Northwest", "8th Street Southeast", "4th Street Southwest",
               "Rock Creek and Potomac Parkway Northwest"],
    "landmarks": ["United States Capitol", "White House", "Washington Monument", "Lincoln Memorial",
                  "Jefferson Memorial", "Washington Union Station", "Library of Congress, Thomas Jefferson Building",
                  "Supreme Court of the United States", "Smithsonian Institution Building", "National Air and Space Museum",
                  "National Museum of Natural History", "National Gallery of Art", "John F. Kennedy Center for the Performing Arts",
                  "Ford's Theatre", "Dupont Circle", "Watergate Complex", "Nationals Park", "Capital One Arena",
                  "U.S. National Archives", "Eisenhower Executive Office Building", "National Museum of American History",
                  "National Museum of African American History and Culture", "E. Barrett Prettyman Federal Courthouse",
                  "Old City Hall"],
    "landmark_buildings": [
        {"name": "United States Capitol", "label": "the Capitol", "floors": 5, "height_m": 88},
        {"name": "White House"},
        {"name": "Washington Monument", "height_m": 169},
        {"name": "Lincoln Memorial"},
        {"name": "Jefferson Memorial"},
        {"name": "Library of Congress, Thomas Jefferson Building", "label": "Library of Congress"},
        {"name": "Supreme Court of the United States", "label": "Supreme Court"},
        {"name": "Washington Union Station", "label": "Union Station"},
        {"name": "Smithsonian Institution Building", "label": "the Castle"},
        {"name": "U.S. National Archives", "label": "National Archives"},
        {"name": "National Air and Space Museum", "label": "Air and Space Museum"},
        {"name": "National Museum of Natural History", "label": "Natural History Museum"},
        {"name": "National Museum of American History", "label": "American History Museum"},
        # two of the three courthouses (the Supreme Court is above): OSM's own names
        {"name": "E. Barrett Prettyman Federal Courthouse", "label": "Prettyman Courthouse"},
        {"name": "Old City Hall", "label": "DC Court of Appeals"},
    ],
    "diagonals": [*_q("Pennsylvania Avenue", quads=("Northwest", "Southeast")),
                  *_q("Massachusetts Avenue", quads=("Northwest", "Northeast", "Southeast")),
                  *_q("New York Avenue", quads=("Northwest", "Northeast")), "Connecticut Avenue Northwest",
                  *_q("Rhode Island Avenue", quads=("Northwest", "Northeast")), "Vermont Avenue Northwest",
                  "New Hampshire Avenue Northwest", *_q("Virginia Avenue", quads=("Northwest", "Southeast")),
                  *_q("Maryland Avenue", quads=("Northeast", "Southwest")),
                  *_q("New Jersey Avenue", quads=("Northwest", "Southeast")), "Delaware Avenue Northeast",
                  "Delaware Avenue Southwest", "Louisiana Avenue Northwest", "Indiana Avenue Northwest",
                  "North Carolina Avenue Southeast", "South Carolina Avenue Southeast", "Kentucky Avenue Southeast",
                  "Potomac Avenue Southeast", "Florida Avenue Northwest", "Florida Avenue Northeast",
                  "Maine Avenue Southwest"],
    "parks": ["National Mall", "The Ellipse", "Lafayette Square", "Constitution Gardens", "West Potomac Park",
              "East Potomac Park", "Dupont Circle", "Logan Circle", "Thomas Circle", "Scott Circle", "Farragut Square",
              "McPherson Square", "Franklin Square", "Mount Vernon Square", "Judiciary Square", "Stanton Park",
              "Lincoln Park", "Garfield Park", "Folger Park", "Seward Square", "Washington Circle Park",
              "Georgetown Waterfront Park", "The Yards Park", "Canal Park", "Upper Senate Park", "Meridian Hill/Malcolm X Park"],
    "areas": _a([
        ["Capitol Hill", 38.8880, -76.9970, 1], ["Georgetown", 38.9097, -77.0654, 1], ["Downtown", 38.9020, -77.0300, 1],
        ["National Mall", 38.8910, -77.0230, 1], ["Dupont Circle", 38.9096, -77.0434, 1], ["Foggy Bottom", 38.8990, -77.0500, 1],
        ["Navy Yard", 38.8760, -77.0030, 1],
        ["West End", 38.9050, -77.0500, 2], ["Logan Circle", 38.9096, -77.0298, 2], ["Shaw", 38.9126, -77.0215, 2],
        ["U Street", 38.9170, -77.0290, 2], ["Penn Quarter", 38.8960, -77.0220, 2], ["Chinatown", 38.8999, -77.0219, 2],
        ["NoMa", 38.9070, -77.0040, 2], ["Southwest Waterfront", 38.8770, -77.0200, 2], ["Near Northeast", 38.9000, -76.9900, 2],
        ["Adams Morgan", 38.9215, -77.0425, 2], ["Kalorama", 38.9170, -77.0530, 2],
        ["Mount Vernon Square", 38.9035, -77.0225, 3], ["Judiciary Square", 38.8960, -77.0165, 3], ["Federal Triangle", 38.8935, -77.0280, 3],
        ["Bloomingdale", 38.9160, -77.0110, 3], ["LeDroit Park", 38.9170, -77.0180, 3], ["Eckington", 38.9140, -77.0010, 3],
        ["Truxton Circle", 38.9105, -77.0130, 3], ["Near Southeast", 38.8790, -76.9950, 3], ["Barracks Row", 38.8805, -76.9950, 4],
        ["Swampoodle", 38.9030, -77.0040, 4], ["Hillsdale", 38.8660, -76.9880, 4],
    ]),
    "rail_lines": [],
    "transit": [
        {"id": "red", "name": "Red Line", "colour": "#BF0D3E", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["R"]},
        {"id": "orange", "name": "Orange Line", "colour": "#ED8B00", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["O"]},
        {"id": "blue", "name": "Blue Line", "colour": "#009CDE", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["B"]},
        {"id": "silver", "name": "Silver Line", "colour": "#919D9D", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["S"]},
        {"id": "green", "name": "Green Line", "colour": "#00B140", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["G"]},
        {"id": "yellow", "name": "Yellow Line", "colour": "#FFD100", "kind": "metro", "network": "Washington Metro",
         "operator": "Washington Metropolitan Area Transit Authority", "route": "subway", "refs": ["Y"]},
        {"id": "dcs", "name": "DC Streetcar", "colour": "#C8102E", "kind": "tram", "network": "DC Streetcar",
         "operator": "District Department of Transportation", "route": "tram", "refs": None},
        {"id": "marc", "name": "MARC", "colour": "#F7941D", "kind": "rail", "network": "MARC",
         "operator": "Maryland Transit Administration", "route": "train", "refs": None},
        {"id": "vre", "name": "Virginia Railway Express", "colour": "#E73035", "kind": "rail",
         "network": "Virginia Railway Express", "operator": "Keolis", "route": "train", "refs": None},
    ],
}

CHICAGO = {
    "place": "Chicago",
    "area": "The Loop, the Near North Side (River North, Streeterville, the Gold Coast, Navy Pier), the Near South Side "
            "(South Loop, the Museum Campus) and the West Loop to Ashland Avenue, with the Lake Michigan shore",
    "bbox": [41.853, -87.668, 41.910, -87.595],
    # one grid at -1.7 degrees; the river splits it but both banks keep their numbering (city_engine joins them across);
    # Lake Michigan is one sea body at the east edge (city_coast: OSM draws it as a lake relation, not a coastline)
    "layout": {"name": "chicago", "builder": "engine", "shore": "sea", "must_parks": ["Millennium Park"]},
    "channels": ["Chicago River", "North Branch Chicago River", "South Branch Chicago River"],
    "river_names": [["Chicago River", 41.8886, -87.6206], ["Chicago River", 41.8875, -87.6290],
                    ["North Branch Chicago River", 41.8930, -87.6400], ["North Branch Chicago River", 41.9030, -87.6500],
                    ["South Branch Chicago River", 41.8782, -87.6377], ["South Branch Chicago River", 41.8649, -87.6347],
                    ["Lake Michigan", 41.8900, -87.6000], ["Lake Michigan", 41.8650, -87.6050]],
    "majors": ["North Michigan Avenue", "South Michigan Avenue", "North State Street", "South State Street",
               "North Wabash Avenue", "South Wabash Avenue", "North Dearborn Street", "North Clark Street", "South Clark Street",
               "North LaSalle Drive", "North Wells Street", "South Wells Street", "North Franklin Street", "South Canal Street",
               "South Clinton Street", "South Jefferson Street", "South Desplaines Street", "North Halsted Street",
               "South Halsted Street", "South Racine Avenue", "North Ashland Avenue", "South Ashland Avenue",
               "North Columbus Drive", "South Columbus Drive", "North Lake Shore Drive",
               "North Jean Baptiste Point DuSable Lake Shore Drive", "South DuSable Lake Shore Drive",
               "South Wacker Drive",
               "West Division Street", "West Chicago Avenue", "West Grand Avenue", "East Grand Avenue", "West Ontario Street",
               "East Ontario Street", "West Ohio Street", "West Kinzie Street", "West Hubbard Street", "East Illinois Street",
               "West Lake Street", "West Randolph Street", "East Randolph Street", "West Washington Boulevard",
               "West Madison Street", "West Monroe Street", "West Adams Street", "West Jackson Boulevard",
               "West Van Buren Street", "West Congress Parkway", "West Harrison Street", "West Polk Street", "West Taylor Street",
               "West Roosevelt Road", "East Roosevelt Road", "West 18th Street", "North Milwaukee Avenue", "North Ogden Avenue",
               "West Ogden Avenue", "North Kingsbury Street"],
    "landmarks": ["Willis Tower", "Aon Center", "Trump International Hotel & Tower Chicago", "875 N Michigan",
                  "Chicago Board of Trade Building", "Cloud Gate", "Chicago Water Tower", "Chicago Union Station",
                  "The Art Institute of Chicago", "Navy Pier", "Richard J. Daley Center",
                  "Dirksen Federal Building and US Courthouse", "Cook County Building", "Merchandise Mart", "Wrigley Building",
                  "Tribune Tower", "Buckingham Fountain", "Field Museum", "Shedd Aquarium", "Chicago Theatre", "The Rookery",
                  "Harold Washington Library Center"],
    "landmark_buildings": [
        {"name": "Willis Tower", "floors": 108, "height_m": 442},
        {"name": "Trump International Hotel & Tower Chicago", "label": "Trump Tower", "floors": 98, "height_m": 423},
        {"name": "Aon Center", "floors": 83, "height_m": 346},
        {"name": "875 N Michigan", "label": "John Hancock Center", "floors": 100, "height_m": 344},
        {"name": "Chicago Board of Trade Building", "label": "Board of Trade", "floors": 44, "height_m": 184},
        {"name": "Richard J. Daley Center", "label": "Daley Center", "floors": 31, "height_m": 197},
        {"name": "Dirksen Federal Building and US Courthouse", "label": "Dirksen Courthouse", "floors": 30, "height_m": 117},
        {"name": "Cook County Building", "label": "City Hall–County Building"},
        {"name": "Chicago Union Station", "label": "Union Station"},
        {"name": "The Art Institute of Chicago", "label": "Art Institute"},
        {"name": "Chicago Water Tower", "label": "Water Tower"},
        {"name": "Merchandise Mart"},
        {"name": "Wrigley Building"},
        {"name": "Tribune Tower", "floors": 36, "height_m": 141},
        {"name": "Navy Pier"},
        {"name": "Cloud Gate", "label": "Cloud Gate (the Bean)"},
    ],
    "diagonals": ["North Milwaukee Avenue", "North Ogden Avenue", "West Ogden Avenue", "North Kingsbury Street"],
    "parks": ["Millennium Park", "Grant Park", "Maggie Daley Park", "Burnham Park", "Northerly Island", "Skinner Park",
              "Jane Addams Park", "Ping Tom Memorial Park", "Polk Bros Park", "Arrigo Park", "Ogden Plaza",
              "Chicago Women's Park and Gardens", "Washington Square", "Lake Shore Park", "Seward Park"],
    "areas": _a([
        ["The Loop", 41.8816, -87.6295, 1], ["Near North Side", 41.9000, -87.6346, 1], ["Near South Side", 41.8567, -87.6248, 1],
        ["Gold Coast", 41.9049, -87.6287, 2], ["River North", 41.8922, -87.6314, 2], ["Streeterville", 41.8927, -87.6197, 2],
        ["South Loop", 41.8658, -87.6258, 2], ["West Loop", 41.8822, -87.6531, 2], ["Little Italy", 41.8694, -87.6568, 2],
        ["Pilsen", 41.8570, -87.6619, 2], ["Old Town", 41.9076, -87.6385, 2], ["Chinatown", 41.8545, -87.6330, 2],
        ["Magnificent Mile", 41.8950, -87.6243, 3], ["Fulton Market District", 41.8867, -87.6533, 3],
        ["Greektown", 41.8784, -87.6476, 3], ["Printer's Row", 41.8735, -87.6290, 3], ["Lakeshore East", 41.8866, -87.6174, 3],
        ["Museum Campus", 41.8663, -87.6158, 3], ["Cabrini-Green", 41.8988, -87.6409, 3], ["Dearborn Park", 41.8674, -87.6290, 3],
        ["Financial District", 41.8794, -87.6323, 4], ["Jewelers Row", 41.8821, -87.6262, 4], ["Fulton River District", 41.8865, -87.6425, 4],
        ["Central Station", 41.8642, -87.6214, 4], ["East Pilsen", 41.8574, -87.6412, 4],
        ["Near West Side", 41.8740, -87.6560, 3],       # (its middle is west of the box: named where the box holds it)
    ]),
    "rail_lines": [],
    "transit": [
        {"id": "red", "name": "Red Line", "colour": "#C60C30", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Red"]},
        {"id": "blue", "name": "Blue Line", "colour": "#00A1DE", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Blue"]},
        {"id": "brown", "name": "Brown Line", "colour": "#62361B", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Brown"]},
        {"id": "green", "name": "Green Line", "colour": "#009B3A", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Green"]},
        {"id": "orange", "name": "Orange Line", "colour": "#F9461C", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Orange"]},
        {"id": "pink", "name": "Pink Line", "colour": "#E27EA6", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Pink"]},
        {"id": "purple", "name": "Purple Line", "colour": "#522398", "kind": "metro", "network": "CTA",
         "operator": "Chicago Transit Authority", "route": "subway", "refs": ["Purple"]},
        {"id": "metra", "name": "Metra", "colour": "#005195", "kind": "rail", "network": "Metra",
         "operator": "Metra", "route": "train", "refs": None},
        {"id": "nictd", "name": "South Shore Line", "colour": "#A82618", "kind": "rail", "network": "NICTD",
         "operator": "NICTD", "route": "train", "refs": None},
    ],
}

PRESETS = {"nyc": NYC, "boston": BOSTON, "dc": DC, "chicago": CHICAGO}

ALIASES = {
    "nyc": ("nyc", "new york", "new york city", "new york, ny", "new york ny", "manhattan", "manhattan, new york",
            "new york, new york"),
    "boston": ("boston", "boston, ma", "boston, massachusetts", "boston ma"),
    "dc": ("dc", "d.c.", "washington", "washington dc", "washington d.c.", "washington, dc", "washington, d.c.",
           "washington d c", "district of columbia"),
    "chicago": ("chicago", "chicago, il", "chicago, illinois", "chicago il", "chicago illinois"),
}

FIELDS = ("place", "area", "bbox", "majors", "landmarks", "landmark_buildings", "diagonals", "parks", "areas",
          "rail_lines", "transit")


def _key(place: str) -> str:
    k = re.sub(r"\s+", " ", str(place or "").strip().lower())
    k = re.sub(r",?\s*(usa|us|united states( of america)?)$", "", k).strip(" ,")
    return k


def find(place: str):
    """The preset id for a place name ('NYC', 'Manhattan', 'Boston', 'Washington, D.C.' ...), or None."""
    k = _key(place)
    for pid, names in ALIASES.items():
        if k in names:
            return pid
    return None


def get(place_or_id: str):
    """A deep copy of the preset (by id or by place name), or None."""
    pid = place_or_id if place_or_id in PRESETS else find(place_or_id)
    return copy.deepcopy(PRESETS[pid]) if pid else None


def buildings_for(preset: dict, given=None) -> list:
    """The landmark_buildings to pass on: the user's own list (each entry with a `unit` and no `floors` gets the
    preset's real floor count when the preset knows the building), else the preset's, without floors/height
    (floors only mean something with a unit)."""
    known = {str(b["name"]).lower(): b for b in preset.get("landmark_buildings") or []}
    known.update({str(b.get("label")).lower(): b for b in preset.get("landmark_buildings") or [] if b.get("label")})
    if given is None:
        return [{k: v for k, v in b.items() if k in ("name", "label", "page", "art")} for b in preset.get("landmark_buildings") or []]
    out = []
    for b in given:
        b = dict(b)
        k = known.get(str(b.get("name") or "").lower()) or known.get(str(b.get("label") or "").lower())
        if b.get("unit") is not None and b.get("floors") is None and k and isinstance(k.get("floors"), int) and k["floors"] >= 2:
            b["floors"] = k["floors"]
        out.append(b)
    return out


def heights(preset: dict) -> dict:
    """{building name: {floors?, height_m?}} — the real heights the preset knows (towers drawn in proportion)."""
    return {b["name"]: {k: b[k] for k in ("floors", "height_m") if k in b}
            for b in preset.get("landmark_buildings") or [] if "floors" in b or "height_m" in b}


TRANSIT_KEYS = {"id", "name", "colour", "kind", "network", "operator", "route", "refs"}


def check_transit(transit) -> None:
    """palace.transit: [{id, name, network, route, ...}] (brief validation)."""
    from .brief import BriefError
    if transit in (None, []):
        return
    if not isinstance(transit, list) or len(transit) > 24:
        raise BriefError("palace.transit: a list of at most 24 transit families")
    for i, f in enumerate(transit):
        if not isinstance(f, dict) or set(f) - TRANSIT_KEYS:
            raise BriefError(f"palace.transit[{i}]: only {sorted(TRANSIT_KEYS)}")
        for k in ("id", "name", "network", "route"):
            if not isinstance(f.get(k), str) or not f[k].strip():
                raise BriefError(f"palace.transit[{i}]: needs {k} (text)")
        if f.get("refs") is not None and not (isinstance(f["refs"], list) and all(isinstance(r, str) for r in f["refs"])):
            raise BriefError(f"palace.transit[{i}].refs: a list of route refs, or null for any")


# ── courthouses (law palaces: city_courts) ──────────────────────────────────
# name: as OpenStreetMap spells it (checked against the cached OSM, see _qa/docs/C1.md); aka: other spellings tried
# when the map differs; level: federal | state | city (city = municipal / county / family / superior / district);
# levels: every level the building houses; lat/lon: the building (from OSM where found, else the court's own
# published address placed by knowledge: src "knowledge").
def _c(name, level, lat, lon, label=None, levels=None, aka=(), src="osm", addr=""):
    return {"name": name, "level": level, "lat": lat, "lon": lon, **({"label": label} if label else {}),
            "levels": levels or [level], "aka": list(aka), "src": src, "addr": addr}


COURTS = {
    "philadelphia": [
        _c("James A. Byrne United States Courthouse", "federal", 39.9506, -75.1510, label="Byrne U.S. Courthouse",
           aka=("James A. Byrne Courthouse", "James A. Byrne U.S. Courthouse"), addr="601 Market Street"),
        _c("Robert N.C. Nix Sr. Federal Building", "federal", 39.9513, -75.1562, label="Nix Federal Courthouse",
           aka=("Robert N. C. Nix Sr. Federal Building and U.S. Courthouse", "Robert N.C. Nix, Sr. Federal Building",
                "Nix Federal Building"), addr="900 Market Street"),
        _c("Justice Juanita Kidd Stout Center for Criminal Justice", "state", 39.9540, -75.1617,
           label="Criminal Justice Center", levels=["state", "city"],
           aka=("Philadelphia Justice Center", "Criminal Justice Center"), addr="1301 Filbert Street"),
        _c("Philadelphia City Hall", "city", 39.9524, -75.1636, label="City Hall", levels=["city", "state"],
           aka=("City Hall",), src="knowledge (a landmark: found by the names query)", addr="1 Penn Square"),
        _c("Family Court", "city", 39.9551, -75.1648, label="Family Court",
           aka=("Family Court Building", "Philadelphia Family Court"),
           addr="1501 Arch Street"),
    ],
    "nyc": [
        _c("Thurgood Marshall United States Courthouse", "federal", 40.7146, -74.0025, label="Thurgood Marshall Courthouse",
           aka=("Thurgood Marshall U.S. Courthouse", "Thurgood Marshall US Courthouse"), addr="40 Foley Square"),
        _c("Daniel Patrick Moynihan United States Courthouse", "federal", 40.7134, -74.0019, label="Moynihan Courthouse",
           aka=("Daniel Patrick Moynihan U.S. Courthouse", "Daniel Patrick Moynihan US Courthouse"), addr="500 Pearl Street"),
        _c("Theodore Roosevelt United States Courthouse", "federal", 40.6963, -73.9903, label="Roosevelt Courthouse (EDNY)",
           aka=("Theodore Roosevelt U.S. Courthouse",), addr="225 Cadman Plaza East, Brooklyn"),
        _c("New York County Supreme Court", "state", 40.7144, -74.0013, label="NY Supreme Court (60 Centre St)",
           aka=("New York County Courthouse", "New York State Supreme Court"), addr="60 Centre Street"),
        _c("Appellate Division Courthouse of New York State", "state", 40.7423, -73.9868, label="Appellate Division",
           aka=("Appellate Division New York State Supreme Court", "Appellate Division Courthouse"), addr="27 Madison Avenue"),
        _c("New York City Criminal Court", "city", 40.7160, -74.0011, label="Criminal Court (100 Centre St)",
           aka=("Manhattan Criminal Court", "Criminal Courts Building", "Manhattan Criminal Courts Building"),
           addr="100 Centre Street"),
        _c("New York City Civil Court", "city", 40.7167, -74.0016, label="Civil Court (111 Centre St)",
           aka=("Manhattan Civil Courthouse", "Civil Court of the City of New York"), addr="111 Centre Street"),
        _c("New York City Family Court", "city", 40.7156, -74.0020, label="Family Court", src="knowledge",
           addr="60 Lafayette Street"),
        _c("Surrogate's Courthouse", "city", 40.7140, -74.0039, label="Surrogate's Court",
           aka=("Hall of Records", "Surrogate's Court"), addr="31 Chambers Street"),
    ],
    "boston": [
        _c("John Joseph Moakley United States Courthouse", "federal", 42.3539, -71.0470, label="Moakley Courthouse",
           aka=("John Joseph Moakley US Courthouse", "Moakley US Courthouse"),
           addr="1 Courthouse Way"),
        _c("John Adams Courthouse", "state", 42.3594, -71.0606, label="John Adams Courthouse (SJC)",
           aka=("Suffolk County Courthouse",), addr="1 Pemberton Square"),
        _c("Suffolk County Courthouse", "city", 42.3590, -71.0601, label="Suffolk Superior Court",
           aka=("Three Pemberton Square", "Suffolk Superior Court"), addr="3 Pemberton Square"),
        _c("Edward W. Brooke Courthouse", "city", 42.3627, -71.0614, label="Brooke Courthouse",
           aka=("Edward W. Brooke Court House", "Brooke Courthouse"), addr="24 New Chardon Street"),
    ],
    "chicago": [
        _c("Dirksen Federal Building and US Courthouse", "federal", 41.8786, -87.6297, label="Dirksen Courthouse",
           aka=("Everett McKinley Dirksen United States Courthouse", "Dirksen Federal Building"), addr="219 South Dearborn Street"),
        _c("Richard J. Daley Center", "state", 41.8842, -87.6302, label="Daley Center (Circuit Court of Cook County)",
           aka=("Daley Center",), addr="50 West Washington Street"),
        _c("Cook County Building", "city", 41.8837, -87.6318, label="City Hall–County Building", levels=["city"],
           aka=("City Hall–County Building", "Chicago City Hall"), addr="118 North Clark Street"),
    ],
    "dc": [
        _c("Supreme Court of the United States", "federal", 38.8906, -77.0044, label="Supreme Court",
           aka=("United States Supreme Court Building", "Supreme Court Building"), addr="1 First Street NE"),
        _c("E. Barrett Prettyman United States Courthouse", "federal", 38.8928, -77.0161, label="Prettyman Courthouse",
           aka=("E. Barrett Prettyman U.S. Courthouse", "E. Barrett Prettyman Federal Courthouse", "Prettyman Courthouse"),
           addr="333 Constitution Avenue NW"),
        _c("Howard T. Markey National Courts Building", "federal", 38.8996, -77.0350, label="National Courts Building",
           aka=("National Courts Building",), addr="717 Madison Place NW"),
        _c("Historic District of Columbia Courthouse", "state", 38.8956, -77.0181, label="DC Court of Appeals",
           aka=("Old City Hall", "District of Columbia City Hall", "D.C. Court of Appeals", "Historic Courthouse"),
           src="knowledge (not tagged as a courthouse on OSM)",
           addr="430 E Street NW"),
        _c("H. Carl Moultrie I Courthouse", "city", 38.8944, -77.0177, label="Moultrie Courthouse (Superior Court)",
           aka=("H. Carl Moultrie Courthouse", "Moultrie Courthouse", "Superior Court of the District of Columbia"),
           addr="500 Indiana Avenue NW"),
    ],
}
