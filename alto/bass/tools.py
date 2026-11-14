"""The Bass tool belt: the SAME tool functions as the connector (alto.mcp_server), offered to the model through
Anthropic's `tools` parameter and executed IN-PROCESS for the caller's uid. Same storage, same gates (the consent
gate included), so switching front doors loses nothing.

Only a subset is offered: no sign-in/site/account tools, nothing that deletes a timeline or project, nothing that
reaches the network (the Memory Map/Blueprint/Atlas builders fetch OpenStreetMap), nothing that publishes.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

import jsonschema

BASS_TOOLS = (
    "list_projects", "create_project", "create_timeline", "record_materials_consent", "set_entities",
    "set_axis_values", "add_nodes", "add_connections", "set_flags", "set_lines", "set_overview",
    "run_layout_preview", "place_nodes", "build_timeline", "preview_timeline", "get_timeline", "delete_nodes",
    "set_up_world", "set_up_building",
    "get_nodes",          # read only, the caller's own timeline: with get_timeline(compact=true) an edit reads what it needs, not the whole draft
)
WRITE_TOOLS = frozenset({
    "create_project", "create_timeline", "record_materials_consent", "set_entities", "set_axis_values", "add_nodes",
    "add_connections", "set_flags", "set_lines", "set_overview", "place_nodes", "build_timeline", "delete_nodes",
    "set_up_world", "set_up_building"})
NEVER_OFFERED = ("set_up_site", "sign_in", "list_accounts", "connect_account", "delete_timeline", "delete_project",
                 "publish_timeline", "import_timeline", "set_up_palace", "get_interview_guide")

# Bass offers set_up_building for the ONE curated building only (the Philadelphia Museum of Art, building='pma'): no plan the model
# drafts, no demo plan. Another building, a new city and a pre-built city are not offered: Bass says so in plain words (shapes.py).
BUILDING_CURATED = ("pma",)
RESTRICTED_DESCRIPTIONS = {
    "set_up_building": ("The Memory Blueprint of the Philadelphia Museum of Art (Main Building), which Alto already holds: pass building='pma'. "
                        "Hands the timeline's cards to its rooms (mode 'room': each top-level card to a room; 'anchor': to an art slot or fixture) and stores the "
                        "curated plan with the timeline. Run it once the timeline exists (mode 'palace', palace_view 'building'); run it again to "
                        "change how cards are handed out. assignments: {card id: room or slot id}. No other building is available."),
}


def _strip(schema: Any) -> Any:
    """Drop the `title` noise Pydantic adds (it costs tokens every call)."""
    if isinstance(schema, dict):
        return {k: _strip(v) for k, v in schema.items() if k != "title" or not isinstance(v, str)}
    if isinstance(schema, list):
        return [_strip(v) for v in schema]
    return schema


def _close(schema: Any) -> bool:
    """Set additionalProperties:false on every object that does not state it. -> True when no object stayed open."""
    ok = True
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False
            elif schema["additionalProperties"] is not False:
                ok = False
        for v in list(schema.values()):
            ok = _close(v) and ok
    elif isinstance(schema, list):
        for v in schema:
            ok = _close(v) and ok
    return ok


@dataclass
class ToolOutcome:
    content: str
    is_error: bool = False
    wrote: bool = False
    name: str = ""
    final: bool = False       # ends the action once its results are in (no further model turn)


class ToolBox:
    def __init__(self, store=None, names: tuple = BASS_TOOLS, *, max_result_chars: int = 20000,
                 use_strict: bool = True):
        from alto import mcp_server as srv           # imported late: it needs the connector's dependencies
        self.srv = srv
        self.store = store
        self.names = tuple(names)
        bad = [n for n in self.names if n in NEVER_OFFERED]
        if bad:
            raise ValueError(f"not allowed in Bass: {bad}")
        self.max_result_chars = max_result_chars
        self.use_strict = use_strict
        tm = srv.mcp._tool_manager
        self._tools = {}
        for n in self.names:
            t = tm.get_tool(n)
            if t is None:
                raise KeyError(f"alto.mcp_server has no tool {n!r}")
            self._tools[n] = t
        self.strict_names: set[str] = set()
        if store is None:                             # incident 11 Nov: never fall through to Alto's default (cloud) store
            from alto.cloud.offline import CloudStoreRefused
            raise CloudStoreRefused("refused: a Bass tool belt needs an explicit store (ToolBox(store)); "
                                    "it never falls back to Alto's default store or the account this computer is signed in to.")

    # -- the function objects the connector itself registers (identity is what the tests pin) -------------------
    def function(self, name: str):
        return self._tools[name].fn

    def input_schema(self, name: str) -> dict:
        t = self._tools[name]
        s = copy.deepcopy(t.parameters)
        s["properties"].pop("account", None)          # the engine decides the account; the model never does
        if "required" in s:
            s["required"] = [r for r in s["required"] if r != "account"]
        if name == "set_up_building":                 # the curated building only: no plan, no demo, no free-text name
            keep = ("timeline_id", "mode", "assignments", "building")
            s["properties"] = {k: v for k, v in s["properties"].items() if k in keep}
            s["properties"]["building"] = {"type": "string", "enum": list(BUILDING_CURATED)}
            s["required"] = ["timeline_id", "building"]
        return _strip(s)

    def specs(self) -> list[dict]:
        out = []
        self.strict_names = set()
        for n in self.names:
            t = self._tools[n]
            schema = self.input_schema(n)
            closed = _close(copy.deepcopy(schema))
            spec = {"name": n, "description": RESTRICTED_DESCRIPTIONS.get(n) or " ".join((t.description or n).split()),
                    "input_schema": schema}
            if self.use_strict and closed:
                _close(schema)
                spec["strict"] = True
                self.strict_names.add(n)
            out.append(spec)
        return out

    # -- execution ----------------------------------------------------------------------------------------------
    def execute(self, uid: str, name: str, tool_input: Any) -> ToolOutcome:
        if name not in self._tools:
            return ToolOutcome(json.dumps({"error": "unknown_tool", "message": f"no tool named {name}"}), True,
                               name=name)
        if not isinstance(tool_input, dict):
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": "input must be an object"}), True,
                               name=name)
        schema = self.input_schema(name)
        extra = sorted(set(tool_input) - set(schema.get("properties", {})))
        if extra:
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": f"unknown argument(s): {extra}"}),
                               True, name=name)
        try:
            jsonschema.validate(tool_input, schema)
        except jsonschema.ValidationError as e:
            where = "/".join(map(str, e.absolute_path)) or "input"
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": f"{where}: {e.message[:300]}"}),
                               True, name=name)
        srv = self.srv
        if self.store is not None and srv._store is not self.store:
            srv.set_store(self.store)
        tok = srv.current_uid.set(uid)
        try:
            result = self._tools[name].fn(**tool_input)
        except Exception as e:      # a tool must never take the loop down: the model gets to see what went wrong
            return ToolOutcome(json.dumps({"error": "tool_failed", "message": f"{type(e).__name__}: {e}"[:500]}),
                               True, name=name)
        finally:
            srv.current_uid.reset(tok)
        is_error = isinstance(result, dict) and bool(result.get("error"))
        text = json.dumps(result, default=str, ensure_ascii=False)
        if len(text) > self.max_result_chars:
            text = text[:self.max_result_chars] + ' ... [result truncated: ask for a narrower view]'
        return ToolOutcome(text, is_error, wrote=(name in WRITE_TOOLS and not is_error), name=name)
