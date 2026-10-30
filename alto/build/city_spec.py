"""LayoutSpec: a city's layout as data, the part of a hand-built layout (city_manhattan, the NYC preset) that is not
code. Rules doc section 11: "extract a LayoutSpec data record {root axes list, children [{region, angle, hinges}],
shore source, must-parks, budget} and let city_engine.build take it. NYC becomes the first spec".

    spec = city_spec.get("manhattan")             # the NYC spec (city_manhattan.NYC)
    spec = city_spec.from_dict(params["layout"])  # what city_setup.auto_params or a preset carries
    g = city_engine.build(m, det, ..., spec=spec)

builder "axes": the root lattice is the fixed, hand-ordered list `root_axes` (city_manhattan draws it: every numbered
street a row, `children` its own even grids at their own angles hinged on real streets, the shore from the land
raster). builder "engine": city_engine's own detected domains and lattices; the spec adds only what data decides
(must-parks, the fill budget, the shore source, the river names), and its `children` record what detect found.
Pure data: no I/O, no engine imports at module level.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

BUILDERS = ("axes", "engine")
SHORES = ("raster", "sea", "rivers")


@dataclass(frozen=True)
class Child:
    """A child lattice. region: ("west_of", axis label, north row, south row) = west of that root axis between two
    numbered rows; ("south_of", row) = everything south of that row; ("domain", id) = a detected domain (engine).
    angle: degrees off the root (None: the region's own real angle, clamped to +-clamp). hinges: the real streets it
    hinges on (seams, never one of its own lines). cap: (most columns, most rows). tip_rows: unnamed rows at the
    region's own street spacing carry the grid on to the land's tip (Manhattan's Battery)."""
    region: tuple
    hinges: tuple = ()
    angle: float | None = None
    clamp: float = 30.0
    cap: tuple = (99, 99)
    tip_rows: bool = False


@dataclass(frozen=True)
class LayoutSpec:
    name: str
    builder: str = "engine"
    root_axes: tuple = ()           # [(label, (OSM names...), ((from row northwards, label), ...))], west to east
    hinge_axis: str = ""            # the root axis the children hang on (Manhattan: 6th Avenue)
    base_row: int = 0               # the root's southmost numbered row (Houston Street = 0)
    row_alias: tuple = ()           # ((lower-case street name, row number), ...)
    major_rows: tuple = ()          # row numbers whose street keeps its label
    children: tuple = ()            # (Child, ...)
    shore: str = "rivers"           # "raster": the land raster of the water polygons (piers off); "sea": one sea body at
                                    # the glass edge; "rivers": the rivers as bands, nothing else
    shore_cell_m: float = 25.0      # the land raster's cell: under half the narrowest channel that must stay open
    must_parks: tuple = ()          # parks the lattice must keep whatever their size (a lattice would swallow them)
    fill_budget: int | None = None  # packed fill-in chars; None: palace_fillin.budget() computes it from the page
    river_names: tuple = ()         # ((name, lat, lon), ...): a water band is named by the nearest of these points
    far: tuple = ()                 # ((far-bank name, side "w"|"e", height share), ...)
    bridges: tuple = ()             # bridges drawn across a band to the far bank
    extra: dict = field(default_factory=dict, compare=False)   # anything a builder reads that is not above

    def __post_init__(self):
        if self.builder not in BUILDERS:
            raise ValueError("LayoutSpec.builder: one of %s" % (BUILDERS,))
        if self.shore not in SHORES:
            raise ValueError("LayoutSpec.shore: one of %s" % (SHORES,))
        if self.builder == "axes" and not self.root_axes:
            raise ValueError("LayoutSpec: builder 'axes' needs root_axes")

    def axis_index(self, label):
        return next((k for k, a in enumerate(self.root_axes) if a[0] == label), None)

    def alias(self) -> dict:
        return dict(self.row_alias)

    def hinge_names(self) -> set:
        return {n for c in self.children for n in c.hinges}

    def to_dict(self) -> dict:
        d = asdict(self)
        return _plain(d)


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def _tup(v):
    if isinstance(v, (list, tuple)):
        return tuple(_tup(x) for x in v)
    return v


def from_dict(d) -> LayoutSpec:
    """A spec from its JSON form (to_dict), a LayoutSpec (as is), or a registered name ("manhattan")."""
    if isinstance(d, LayoutSpec):
        return d
    if isinstance(d, str):
        sp = get(d)
        if sp is None:
            raise ValueError("unknown layout %r" % d)
        return sp
    d = dict(d)
    kids = tuple(Child(**{**c, "region": _tup(c["region"]), "hinges": _tup(c.get("hinges", ())),
                          "cap": _tup(c.get("cap", (99, 99)))}) if isinstance(c, dict) else c for c in d.pop("children", ()))
    for k in ("root_axes", "row_alias", "major_rows", "must_parks", "river_names", "far", "bridges"):
        if k in d:
            d[k] = _tup(d[k])
    return LayoutSpec(children=kids, **d)


def get(name):
    """A registered spec by name: "manhattan" (the NYC preset's Commissioners' Grid). None if unknown."""
    if name == "manhattan":
        from .city_manhattan import NYC
        return NYC
    return None


def resolve(layout):
    """m["layout"] / a preset's `layout` -> a LayoutSpec, or None (no layout: the engine as it is)."""
    if not layout:
        return None
    try:
        return from_dict(layout)
    except (TypeError, ValueError):
        return None
