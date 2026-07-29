"""Splice content into an Alto template.

The template (produced by tools/extract_templates.py) contains
    /*ALTO:BEGIN name*/<default>/*ALTO:END name*/       (js/css context)
    <!--ALTO:BEGIN name--><default><!--ALTO:END name--> (html context)
region markers and __ALTO_TOK_name__ tokens. emit() replaces every marked span
(markers included) and every token with caller-supplied content, then asserts
no ALTO marker survives. Splices are position-based single replacements — the
same assert-before-write discipline as build_terrarium_glass.py.
"""
import re


class EmitError(Exception):
    pass


_BEGIN = {
    "js": "/*ALTO:BEGIN {n}*/",
    "html": "<!--ALTO:BEGIN {n}-->",
}
_END = {
    "js": "/*ALTO:END {n}*/",
    "html": "<!--ALTO:END {n}-->",
}


def _find_region(text, name):
    for ctx in ("js", "html"):
        b = _BEGIN[ctx].format(n=name)
        e = _END[ctx].format(n=name)
        nb, ne = text.count(b), text.count(e)
        if nb == 0 and ne == 0:
            continue
        if nb != 1 or ne != 1:
            raise EmitError(f"region {name!r}: begin×{nb} end×{ne} (need 1/1)")
        a = text.index(b)
        z = text.index(e)
        if z < a:
            raise EmitError(f"region {name!r}: END before BEGIN")
        return a, z + len(e)
    raise EmitError(f"region {name!r}: markers not found")


def emit(template: str, regions: dict, tokens: dict, *, strict: bool = True) -> str:
    """regions: name -> replacement text (replaces the whole marked span).
    tokens: name -> replacement text (replaces every __ALTO_TOK_name__).
    strict: assert that no ALTO marker/token remains afterward."""
    out = template
    for name, content in regions.items():
        a, z = _find_region(out, name)
        out = out[:a] + content + out[z:]
    for name, content in tokens.items():
        ph = f"__ALTO_TOK_{name}__"
        if ph not in out:
            raise EmitError(f"token {name!r}: placeholder not found")
        out = out.replace(ph, content)
    if strict:
        leftover = re.search(r"ALTO:(BEGIN|END) [\w-]+|__ALTO_TOK_\w+__", out)
        if leftover:
            raise EmitError(f"unconsumed template slot: {leftover.group(0)!r}")
    return out
