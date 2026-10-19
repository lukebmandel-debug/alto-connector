"""Plans for the first-person view's tests: a procedural STRESS plan (~200 rooms over three levels, every wall with doors, windows, slots, columns,
fixtures and stairs) built only from the schema, so the renderer is exercised the way a big museum would exercise it. Invented, not real data."""
from alto.build import building_schema as bs


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def stress_plan(nx=9, ny=8, levels=3, cw=9.0, cd=8.0):
    """nx * ny galleries on each of `levels` floors (default 216 rooms): an exterior loop wall with windows, interior grid walls with a door
    or an arch into every neighbour, two wall slots per gallery and a sculpture in some, columns, benches, a stair between every pair of levels."""
    W, H = nx * cw, ny * cd
    mats = ["parquet", "marble", "terrazzo", "plank", "parquet", "carpet"]
    walls_m = ["paint", "paint", "plaster", "paint", "wood", "limestone"]
    lights = ["art", "art", "sky", "mixed", "day", "art"]
    lv, wl, rm, st, cols, fx, sl = [], [], [], [], [], [], []
    for li in range(levels):
        e = li * 6.0
        lid = f"l{li}"
        lv.append({"id": lid, "n": f"Level {li + 1}", "lb": str(li + 1), "e": e, "h": 6.0})
        # exterior loop: a window in the middle of every bay, the main door on the ground floor
        ops, a = [], 0.0
        sides = [(W, nx, cw), (H, ny, cd), (W, nx, cw), (H, ny, cd)]
        for side, (L, n, size) in enumerate(sides):
            for i in range(n):
                c = a + (i + .5) * size
                if li == 0 and side == 0 and i == nx // 2:
                    ops.append({"k": "door", "a": c, "w": 3.0, "h": 4.0, "d": "double", "m": "bronze"})
                else:
                    ops.append({"k": "window", "a": c, "w": 1.8, "h": 2.6, "z": 1.2})
            a += L
        wl.append({"id": f"x{li}", "l": lid, "p": rect(0, 0, W, H), "loop": True, "t": 0.6, "m": "limestone", "k": "ext", "o": ops})
        for i in range(1, nx):            # north-south walls
            wo = [{"k": "arch" if (i + j + li) % 3 == 0 else "door", "a": (j + .5) * cd, "w": 2.4, "h": 3.6, "d": "none"} for j in range(ny)]
            wl.append({"id": f"v{li}-{i}", "l": lid, "p": [[i * cw, 0], [i * cw, H]], "t": 0.3, "m": "plaster", "o": wo})
        for j in range(1, ny):            # east-west walls
            wo = [{"k": "door" if (i + j) % 2 else "arch", "a": (i + .5) * cw, "w": 2.2, "h": 3.4, "d": "none"} for i in range(nx)]
            wl.append({"id": f"h{li}-{j}", "l": lid, "p": [[0, j * cd], [W, j * cd]], "t": 0.3, "m": "plaster", "o": wo})
        for i in range(nx):
            for j in range(ny):
                k = (i * 7 + j * 3 + li) % 6
                rid = f"r{li}-{i}-{j}"
                rm.append({"id": rid, "l": lid, "n": f"Gallery {li + 1}{i:01d}{j:01d}", "no": f"{li + 1}{i}{j}", "ty": "gallery",
                           "p": rect(i * cw, j * cd, (i + 1) * cw, (j + 1) * cd), "ch": 5.4, "fm": mats[k], "wm": walls_m[k],
                           "cm": "glass" if lights[k] == "sky" else "plaster", "li": {"k": lights[k]}})
                x0, y0 = i * cw, j * cd
                sl.append({"id": f"s{li}-{i}-{j}a", "rm": rid, "p": [x0 + cw * .3, y0 + .15 + (.15 if j == 0 else 0)], "z": 1.6, "sz": [1.4, 1.1], "fc": 90, "al": ["painting"]})
                sl.append({"id": f"s{li}-{i}-{j}b", "rm": rid, "p": [x0 + cw * .7, y0 + cd - .15], "z": 1.55, "sz": [0.7, 0.9], "fc": -90, "al": ["drawing", "print"]})
                if (i + j) % 4 == 0:
                    sl.append({"id": f"s{li}-{i}-{j}c", "rm": rid, "p": [x0 + cw * .5, y0 + cd * .5], "z": 1.0, "sz": [0.6, 0.9], "fc": 180, "al": ["sculpture"]})
                elif (i + j) % 4 == 2:
                    fx.append({"id": f"b{li}-{i}-{j}", "l": lid, "k": "bench", "p": [x0 + cw * .5, y0 + cd * .5], "rot": 0, "sz": [2.0, 0.55, 0.46], "m": "leather"})
                if (i * 3 + j) % 5 == 0:
                    cols.append({"id": f"c{li}-{i}-{j}", "l": lid, "p": [x0 + 1.4, y0 + 1.4], "r": 0.3, "o": "doric", "m": "marble"})
                if (i + 2 * j) % 7 == 3:
                    fx.append({"id": f"v{li}-{i}-{j}", "l": lid, "k": "case", "p": [x0 + cw * .78, y0 + cd * .45], "rot": 90, "sz": [1.2, 0.6, 1.5], "m": "wood"})
    for li in range(levels - 1):         # a straight stair in the room at grid (1, 1) of every level, rising north
        x0, y0 = 1 * cw + 3.0, 1 * cd + 1.2
        st.append({"id": f"st{li}", "k": "stair", "from": f"l{li}", "to": f"l{li + 1}", "fp": rect(x0, y0, x0 + 2.4, y0 + 5.6), "w": 2.0, "n": 36, "up": 90,
                   "fl": [{"a": [x0 + 1.2, y0 + .2, li * 6.0], "b": [x0 + 1.2, y0 + 5.6, (li + 1) * 6.0], "w": 2.0}]})
    st.append({"id": "lift", "k": "elevator", "from": "l0", "to": "l1", "fp": rect(cw * 4 + .8, cd * 3 + .8, cw * 4 + 2.6, cd * 3 + 2.6)})
    plan = {"v": 1, "id": "stress", "name": "Stress Museum (invented)", "kind": "museum", "c": 2,
            "src": [{"id": "gen", "t": "Generated for tests", "k": "estimate", "lic": "CC0"}],
            "lv": lv, "wl": wl, "rm": rm, "st": st, "cols": cols, "fx": fx, "sl": sl,
            "ex": {"gz": -0.6, "sh": [{"id": "body", "p": rect(0, 0, W, H), "h": levels * 6.0 + .6, "rf": {"k": "flat"}, "m": "limestone"}],
                   "stp": [{"id": "steps", "p": rect(W / 2 - 4, -3, W / 2 + 4, 0), "z0": -0.6, "z1": 0, "n": 4, "up": 90}],
                   "tr": [{"id": "plaza", "p": rect(W / 2 - 14, -14, W / 2 + 14, -3), "z": -0.6, "m": "granite", "n": "Plaza"}]},
            "en": [{"id": "main", "n": "Main door", "l": "l0", "p": [W / 2, 0], "fc": -90, "w": 3.0, "k": "main", "wall": "x0"}]}
    bs.validate_plan(plan)
    return plan
