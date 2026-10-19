"""Curated buildings: plans Alto ships for famous public buildings, so a Building Palace of one needs no plan upload.

    set_up_building(timeline_id, building="pma")        the Philadelphia Museum of Art (pma.py)
    set_up_building(timeline_id, building="test-pavilion")   the tiny invented fixture (not a real building)

A curated plan is the same data any plan is (build/building_schema.py); it is checked on the way in like any other. `CURATED` maps the token to a loader returning a
fresh plan dict; `describe()` lists them for the tool's reply and error messages.
"""
from __future__ import annotations


def _pma() -> dict:
    from . import pma
    return pma.plan()


def _fixture() -> dict:
    from ..build.building_schema import fixture
    return fixture()


CURATED = {
    "pma": {"name": "Philadelphia Museum of Art - Main Building", "load": _pma,
            "about": "the Main Building: exterior, Rocky Steps, East Terrace and four levels (G, 1, 2, 3) drawn from the 1928 plans; low-confidence rooms are dashed"},
    "test-pavilion": {"name": "Alto Test Pavilion (invented)", "load": _fixture, "about": "a tiny invented building for tests and demos; not real data"},
}
ALIASES = {"philadelphia museum of art": "pma", "philadelphia art museum": "pma", "pma": "pma", "art museum": "pma", "demo": "test-pavilion"}


def resolve(name: str):
    """The curated token for a name or alias (case-insensitive), else None."""
    n = (name or "").strip().lower()
    return n if n in CURATED else ALIASES.get(n)


def load(name: str) -> dict:
    """A fresh copy of the curated plan; KeyError for a name that is not curated."""
    token = resolve(name)
    if token is None:
        raise KeyError(name)
    return CURATED[token]["load"]()


def describe() -> list:
    return [{"building": k, "name": v["name"], "about": v["about"]} for k, v in CURATED.items()]
