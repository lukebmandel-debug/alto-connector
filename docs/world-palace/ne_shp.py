"""Minimal reader for a Natural Earth polygon shapefile (.shp + .dbf): returns GeoJSON-like features (every ring its own polygon, as build_world_geo expects)."""
import struct


def read(base):
    with open(base + ".dbf", "rb") as f:
        d = f.read()
    n, hl, rl = struct.unpack("<IHH", d[4:12])
    fields, p = [], 32
    while d[p] != 0x0D:
        fields.append((d[p:p + 11].split(b"\0")[0].decode("ascii"), chr(d[p + 11]), d[p + 16]))
        p += 32
    recs = []
    for i in range(n):
        r, o, props = d[hl + i * rl: hl + (i + 1) * rl], 1, {}
        for name, t, ln in fields:
            v = r[o:o + ln].decode("utf-8", "replace").replace("\0", "").strip()
            o += ln
            if t in "NF":
                try:
                    v = float(v) if ("." in v or "e" in v.lower()) else int(v)
                except ValueError:
                    v = None
            props[name] = v if v != "" else None
        recs.append(props)
    with open(base + ".shp", "rb") as f:
        s = f.read()
    out, p = [], 100
    while p < len(s):
        ln = struct.unpack(">i", s[p + 4:p + 8])[0] * 2
        c = s[p + 8:p + 8 + ln]
        p += 8 + ln
        t = struct.unpack("<i", c[:4])[0]
        if t == 0:
            out.append(None)
            continue
        assert t == 5, t
        npart, npts = struct.unpack("<ii", c[36:44])
        parts = list(struct.unpack("<%di" % npart, c[44:44 + 4 * npart])) + [npts]
        q = 44 + 4 * npart
        pts = [struct.unpack("<dd", c[q + 16 * i: q + 16 * i + 16]) for i in range(npts)]
        out.append({"type": "MultiPolygon", "coordinates": [[[list(x) for x in pts[a:b]]] for a, b in zip(parts, parts[1:])]})
    assert len(out) == len(recs)
    return [{"properties": r, "geometry": g} for r, g in zip(recs, out)]
