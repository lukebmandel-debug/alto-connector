"""Hub & spoke ⇄ Star chart (convert_timeline).

Hub & spoke is an outline laid out 'solar' (still circles on spokes); a Star
chart is a Mind Palace in its stars view (the same systems, moving). They hold
the same thing — every unit's (district's) roots as suns, their children as
planets, moons, satellites — so a conversion changes only the brief: the mode,
the layout / palace_view, and the settings one kind has and the other cannot
hold. Those are parked in brief.stash for the way back, so a round trip loses
nothing. The nodes, connections, notes, sources and consent are never touched
(convert_brief does not see them, beyond reading the nodes to check that the
result is valid).
"""
from __future__ import annotations

import copy

from .brief import BriefError, solar_style

TARGETS = ("star_chart", "hub_and_spoke")
# what each kind keeps for itself (parked in brief.stash while the timeline is the other kind)
OUTLINE_OWN = ("layout", "tree_lines", "outcomes", "placement")
PALACE_OWN = ("palace", "palace_view", "placement")
_DEFAULTS = {"layout": "auto", "tree_lines": "fan", "outcomes": "stack", "placement": {},
             "palace": {}, "palace_view": "city"}


class ConvertError(ValueError):
    """Why this timeline cannot be converted that way (said to the user)."""


def kind_of(brief: dict) -> str:
    """'hub_and_spoke', 'star_chart', 'city_palace', 'building_palace', or the mode / layout."""
    mode = brief.get("mode") or "linear"
    if mode == "outline" and brief.get("layout") == "solar":
        return "hub_and_spoke"
    if mode == "palace":
        return {"stars": "star_chart", "building": "building_palace"}.get(brief.get("palace_view"), "city_palace")
    if mode == "outline":
        return f"outline ({brief.get('layout') or 'auto'} layout)"
    return mode


def _refuse(brief: dict, to: str) -> None:
    have = kind_of(brief)
    if to not in TARGETS:
        raise ConvertError(f"to {to!r}: must be 'star_chart' (Hub & spoke → Star chart) or "
                           "'hub_and_spoke' (Star chart → Hub & spoke)")
    want_from = "hub_and_spoke" if to == "star_chart" else "star_chart"
    if have == to:
        raise ConvertError(f"this timeline is already a {_name(to)}")
    if have == want_from:
        return
    if have == "building_palace":
        raise ConvertError(
            "this Mind Palace is a Building Palace: its cards stand in the rooms of one real building's plan, which a Hub & spoke cannot show. "
            "Only a Star chart converts — rebuild it with palace_view 'stars' first (the building's plan is kept, so it can go back), then convert")
    if have == "city_palace":
        raise ConvertError(
            "this Mind Palace is shown as a city: its buildings stand on a real map's lots and "
            "its floors stack to any height, which a Hub & spoke cannot show. Only its Star "
            "chart view converts — rebuild it with palace_view 'stars' first (the city is kept, "
            "so it can go back), then convert")
    raise ConvertError(
        f"this timeline is a {have}; convert_timeline only turns a Hub & spoke (an outline with "
        "layout 'solar') into a Star chart and back. "
        + ("Build it with layout 'solar' first to make it a Hub & spoke." if have.startswith("outline")
           else "It has no hub-and-spoke structure to carry over."))


def _name(k: str) -> str:
    return {"star_chart": "Star chart", "hub_and_spoke": "Hub & spoke"}.get(k, k)


def _turns(placement) -> dict:
    """Only the `order` hints of a placement ({id: {"order": n}}): the turn a card was given among
    its siblings, which both kinds honour (a ring in a Hub & spoke, a floor in a Star chart)."""
    return {i: {"order": h["order"]} for i, h in (placement or {}).items()
            if isinstance(h, dict) and isinstance(h.get("order"), int) and not isinstance(h.get("order"), bool)}


def convert_brief(brief: dict, nodes: list, to: str) -> tuple[dict, list]:
    """(the converted brief, notes for the user). Raises ConvertError when this
    timeline cannot be converted that way — with the reason, for the user.
    `nodes` are the stored node dicts; they are read, never changed."""
    _refuse(brief, to)
    old = copy.deepcopy(brief)
    new = copy.deepcopy(brief)
    stash = dict(new.get("stash") or {})
    notes = []
    if to == "star_chart":
        # (layout 'solar' is what a Hub & spoke is: it comes back with the mode)
        stash["outline"] = {k: copy.deepcopy(old[k]) for k in OUTLINE_OWN
                            if k in old and not (k == "layout" and old[k] == "solar")}
        back = stash.pop("palace", {}) or {}
        for k in OUTLINE_OWN:
            new.pop(k, None)
        for k in PALACE_OWN:
            if k in back:
                new[k] = copy.deepcopy(back[k])
        new["mode"] = "palace"
        new["palace_view"] = "stars"
        turns = _turns(old.get("placement"))             # the order the planets were put in goes along
        if turns:
            new["placement"] = {**(new.get("placement") or {}), **{i: {**(new.get("placement") or {}).get(i, {}), **h}
                                                                  for i, h in turns.items()}}
        if (old.get("placement") or {}):
            notes.append("the outline's card placement is kept aside (a Star chart places by its "
                         "orbits); converting back restores it")
    else:
        roots: dict = {}
        for n in nodes:
            if not n.get("parent"):
                roots.setdefault(n.get("act", 0), []).append(n["id"])
        acts = old.get("acts") or []
        crowded = {a: ids for a, ids in sorted(roots.items()) if len(ids) > 1}
        if crowded:
            a, ids = next(iter(crowded.items()))
            label = (acts[a].get("short") or acts[a].get("label")) if a < len(acts) and isinstance(acts[a], dict) else f"{a + 1}"
            raise ConvertError(
                f"district {a + 1} ({label!r}) has {len(ids)} buildings ({', '.join(ids[:4])}"
                f"{' …' if len(ids) > 4 else ''}), and a Hub & spoke has one sun per unit"
                + (f" ({len(crowded)} districts are like that)" if len(crowded) > 1 else "")
                + ". Make the others floors of one building, or give each building a unit of "
                "its own, then convert — nothing was changed")
        stash["palace"] = {k: copy.deepcopy(old[k]) for k in PALACE_OWN
                           if k in old and not (k == "palace_view" and old[k] == "stars")}
        pp = {i: {k: v for k, v in h.items() if k != "order"} for i, h in (stash["palace"].get("placement") or {}).items()}
        pp = {i: h for i, h in pp.items() if h}                 # a turn goes along (below); it is not parked as well
        if pp:
            stash["palace"]["placement"] = pp
        else:
            stash["palace"].pop("placement", None)
        back = stash.pop("outline", {}) or {}
        for k in PALACE_OWN:
            new.pop(k, None)
        for k in OUTLINE_OWN:
            if k in back:
                new[k] = copy.deepcopy(back[k])
        new["mode"] = "outline"
        new["layout"] = "solar"
        turns = _turns(old.get("placement"))             # the order the floors were put in goes along
        if turns:
            new["placement"] = {**(new.get("placement") or {}), **{i: {**(new.get("placement") or {}).get(i, {}), **h}
                                                                  for i, h in turns.items()}}
        if (old.get("palace") or {}).get("data_z"):
            notes.append("the palace's city is kept aside; converting back (or building it as a "
                         "city) needs no new map")
    stash = {k: v for k, v in stash.items() if v}
    if stash:
        new["stash"] = stash
    else:
        new.pop("stash", None)
    return new, notes


def check_converted(brief_dict: dict, node_dicts: list, connections: list) -> list:
    """Validate the converted timeline as the build will; BriefError → ConvertError."""
    from .builder import load_brief
    from .brief import validate_brief, validate_nodes
    try:
        b, nodes, _ = load_brief({"brief": brief_dict, "nodes": [
            {k: v for k, v in n.items() if not k.startswith("_")} for n in node_dicts],
            "connections": connections})
        warnings = validate_brief(b) + validate_nodes(b, nodes)
    except (BriefError, TypeError) as e:
        raise ConvertError(f"the converted timeline would not build: {e} — nothing was changed")
    assert solar_style(b), "a converted timeline is Hub & spoke or a Star chart"
    return warnings
