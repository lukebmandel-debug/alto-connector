"""Locate the engine templates the build path renders into.

Two layouts have to work:

* **Dev checkout** — templates live in `<repo>/engine/`, a sibling of this
  package, alongside `FROZEN/` and `TEMPLATE_MANIFEST.json` which the
  extraction tooling and the golden round-trip test need.
* **Installed** — a `pip install` or an .mcpb bundle has no repo, so the three
  runtime templates are copied in beside this file at packaging time (see
  `packaging/build_mcpb.sh`). They are generated, hence gitignored.

The packaged copy wins when present, so an installed Alto never silently reads
a stale checkout that happens to be lying around.

Only these three files are runtime dependencies. `TEMPLATE_MANIFEST.json`
(255KB) and `FROZEN/` (~1MB) are build-time proofs and are deliberately left
out of every shipped artifact.
"""
from __future__ import annotations

from pathlib import Path

RUNTIME_TEMPLATES = (
    "timeline_template.html",
    "home_template.html",
    "reports_template.html",
)

PACKAGED = Path(__file__).resolve().parent
REPO = PACKAGED.parent.parent / "engine"


class EngineMissing(RuntimeError):
    pass


def engine_dir() -> Path:
    """The directory holding the runtime templates."""
    if (PACKAGED / "timeline_template.html").exists():
        return PACKAGED
    if (REPO / "timeline_template.html").exists():
        return REPO
    raise EngineMissing(
        "engine templates not found — looked in "
        f"{PACKAGED} and {REPO}. An installed Alto should carry them inside "
        "the package; a checkout should have engine/ next to alto/.")


def template(name: str) -> str:
    if name not in RUNTIME_TEMPLATES:
        raise EngineMissing(f"{name!r} is not a runtime template")
    return (engine_dir() / name).read_text(encoding="utf-8")
