"""Synthetic cities for the city-engine v2 tests (no network): a square grid with numbered columns and named rows,
an avenue that cuts across it, a tilted second grid, and an irregular (free) street network."""
import math

W, H = 2600, 2000
BBOX = [39.95, -75.17, 39.95 + H / 110574, -75.17 + W / (math.cos(math.radians(39.95 + H / 221148)) * 111320)]
ORD = {1: "st", 2: "nd", 3: "rd"}


def _ord(i):
    return "%d%s" % (i, "th" if 10 <= i % 100 <= 20 else ORD.get(i % 10, "th"))


def grid_city(diagonal=True, river=True, cols=18, rows=16, dx=130, dy=110, x0=100, y0=100):
    """Columns '1st Street'.. at x0 + i*dx, rows 'Row A Street'.. at y0 + j*dy, all through streets; an avenue from
    the north-west to the south-east at about 35 degrees (two OSM ways, one gap); a river along the bottom."""
    streets = []
    for i in range(cols):
        x = x0 + i * dx
        streets.append({"n": "North %s Street" % _ord(i + 1), "k": 3, "p": [x, 0, x, H / 2]})
        streets.append({"n": "South %s Street" % _ord(i + 1), "k": 3, "p": [x, H / 2, x, H]})
    for j in range(rows):
        y = y0 + j * dy
        if river and y > H - 260:
            continue
        streets.append({"n": "Row %s Street" % chr(65 + j), "k": 2 if j % 4 == 0 else 3, "p": [0, y, W, y]})
    if diagonal:
        # an avenue across the grid, slightly wavy, in two ways with a 60 px gap between them
        a = [(160 + t * 70, 140 + t * 49 + 12 * math.sin(t / 2)) for t in range(0, 14)]
        b = [(160 + t * 70, 140 + t * 49 + 12 * math.sin(t / 2)) for t in range(15, 30)]
        streets.append({"n": "Diagonal Avenue", "k": 2, "p": [v for q in a for v in q]})
        streets.append({"n": "Diagonal Avenue", "k": 2, "p": [v for q in b for v in q]})
    m = {"v": 1, "place": "Testville", "bbox": list(BBOX), "scale": 1.0, "W": W, "H": H,
         "attribution": "© OpenStreetMap contributors", "streets": streets, "trails": [], "rails": [],
         "parks": [], "majors": ["Row A Street"],
         "stations": [{"n": "Central", "x": x0 + 5 * dx + 3, "y": y0 + 4 * dy + 2, "k": "rail", "l": ["L"]}],
         "landmarks": [{"n": "Town Hall", "x": x0 + 8.5 * dx, "y": y0 + 6.5 * dy,
                        "r": [[x0 + 8 * dx + 10, y0 + 6 * dy + 10, x0 + 9 * dx - 10, y0 + 6 * dy + 10,
                               x0 + 9 * dx - 10, y0 + 7 * dy - 10, x0 + 8 * dx + 10, y0 + 7 * dy - 10]]}]}
    if river:
        m["water"] = [[0, H - 200, W, H - 200, W, H, 0, H]]
        m["rivers"] = [{"n": "Test River", "p": [0, H - 120, W / 2, H - 140, W, H - 120]}]
    else:
        m["water"], m["rivers"] = [], []
    return m


def tilted_streets(cx, cy, ang_deg, n=8, step=120, L=1200, prefix="Tilt"):
    """A second grid turned by ang_deg about (cx, cy): n lines each way."""
    a = math.radians(ang_deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for fam, (ux, uy) in (("h", (c, s)), ("v", (-s, c))):
        nx, ny = -uy, ux
        for k in range(-(n // 2), n - n // 2):
            ox, oy = cx + nx * k * step, cy + ny * k * step
            p = [ox - ux * L / 2, oy - uy * L / 2, ox + ux * L / 2, oy + uy * L / 2]
            out.append({"n": "%s %s%d Street" % (prefix, fam.upper(), k + n), "k": 3, "p": p})
    return out


def free_city(n_rad=10, rings=(250, 500, 800), cx=1300, cy=1000):
    """No grid: radial streets out of a central place and ring roads, with a few short lanes."""
    streets = []
    for i in range(n_rad):
        a = 2 * math.pi * i / n_rad + 0.13 * math.sin(i)
        pts = [(cx + r * math.cos(a + 0.0004 * r), cy + r * math.sin(a + 0.0004 * r)) for r in range(60, 1000, 40)]
        streets.append({"n": "Radial %d Road" % i, "k": 2 if i % 3 == 0 else 3, "p": [v for q in pts for v in q]})
    for j, R in enumerate(rings):
        pts = [(cx + R * math.cos(t / 40 * 2 * math.pi) * (1 + .08 * math.sin(3 * t / 40 * 2 * math.pi)),
                cy + R * math.sin(t / 40 * 2 * math.pi)) for t in range(41)]
        streets.append({"n": "Ring %d" % j, "k": 3, "p": [v for q in pts for v in q]})
    streets.append({"n": "Little Lane", "k": 5, "p": [cx + 300, cy - 20, cx + 330, cy - 60]})
    m = {"v": 1, "place": "Freetown", "bbox": list(BBOX), "scale": 1.0, "W": 2600, "H": 2000,
         "streets": streets, "trails": [], "rails": [], "parks": [], "water": [], "rivers": [], "majors": [],
         "stations": [], "landmarks": [{"n": "The Cross", "x": cx + 10, "y": cy + 5, "r": []}]}
    return m
