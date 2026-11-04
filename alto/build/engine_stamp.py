"""Which Alto release built a page, and the rule that an older Alto never
overwrites a page a newer one built.

`alto-build` (fingerprint.py) is a content digest: it says two pages came from
the same code, but not which is newer. A downgrade guard needs an ORDER, so
the private page also carries `alto-engine`, the release number of the Alto
that built it.

The failure this exists for (Luke, L-1103-004328): a Mac still running an old
Alto extension rebuilt and published a page that a newer Alto had made, and the
page lost everything the newer one added. Nothing warned anyone.

There is deliberately no switch, argument or environment variable that turns
the refusal off. The only way past it is the one that fixes the cause: update
the extension.
"""
from __future__ import annotations

import html as _html
import re

META_ENGINE = "alto-engine"

_TAG = re.compile(r'<meta name="%s" content="(\d+(?:\.\d+){0,3})"' % META_ENGINE)

UPDATE_HOW = ("download the newest Alto from https://alto-get.web.app, open the "
              "downloaded file to install it over this one, then restart Claude")


class StaleEngineError(Exception):
    """Publishing would put an older engine's page over a newer one's."""

    def __init__(self, existing: str, mine: str):
        self.existing, self.mine = existing, mine
        super().__init__(
            f"This page was last built by Alto {existing}, which is newer than "
            f"this extension ({mine}). Publishing would replace it with an older "
            f"page and lose what the newer Alto added. Nothing was changed. "
            f"Update the Alto extension first ({UPDATE_HOW}), then publish again.")


def parse_version(s) -> tuple[int, ...] | None:
    """'1.9.211' -> (1, 9, 211); None for anything that is not a plain release number."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})", str(s or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def is_older(a, b) -> bool:
    """True when release `a` is older than release `b`; False if either is unreadable."""
    pa, pb = parse_version(a), parse_version(b)
    return bool(pa and pb and _cmp(pa, pb) < 0)


def running_version() -> str:
    import sys
    mod = sys.modules.get("alto.mcp_server")
    if mod is None:
        from .. import mcp_server as mod          # noqa: PLC0415 — lazy: mcp_server imports the build package
    return mod.__version__


def engine_meta_tag(version: str = "") -> str:
    return f'<meta name="{META_ENGINE}" content="{_html.escape(version or running_version(), quote=True)}">'


def page_engine(html) -> str:
    """The release stamped into a page, or '' when it has none (it predates stamps)."""
    m = _TAG.search(str(html or "")[:60000])
    return m.group(1) if m else ""


def check_no_downgrade(existing_html, new_html: str = "") -> None:
    """Raise StaleEngineError when the page already stored was built by a NEWER
    Alto than the page about to replace it. An unstamped existing page passes."""
    have = page_engine(existing_html)
    if not have:
        return
    mine = page_engine(new_html) or running_version()
    if is_older(mine, have):
        raise StaleEngineError(have, mine)
