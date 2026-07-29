"""Make user-supplied brief content safe to interpolate into a timeline page.

Why this exists, and why it has to live here rather than in the engine: the
engine renders detail sections with

    sections.map(s=>`<div class="detail-section"><h3>${s.h}</h3><p>${s.t}</p></div>`)

straight into `innerHTML`, with no escaping — that is inherited Terrarium
behaviour and `engine/` is frozen. So a string's journey through `js_str()`
protects only the *JS literal*; once assigned it decodes and is parsed as HTML.
The single point where user content can be made inert is therefore right here,
before it reaches blocks.py.

Escaping here would be wrong, and that is the subtle part. The engine is
*inconsistent* about who escapes: a node's title is rendered `esc(n.title)` on
the card but `'+nd.title+'` raw on its detail page — the same stored value,
two sinks. Pre-escaping would make the card read `Smith &amp; Jones`.

So the rule is **strip, don't escape**:

  * **Plain-text fields are reduced to tag-free text** (`plain_text`): entities
    decoded, elements removed. With no `<` or `>` left, the raw sinks cannot be
    made to open a tag — and every raw sink in the engine was verified to be
    element content, never an attribute value, so stray quotes and ampersands
    are inert. The value also survives the engine's own `esc()` unchanged, so
    ordinary titles render correctly on both paths.
  * **Markup-bearing fields** (`overview_html`, `Section.t`) keep working inline
    HTML but are rebuilt through a tag/attribute allowlist.
  * **`symbol_svg`** is rebuilt through a separate SVG allowlist.
  * **Colors** that reach a CSS or JS literal are pattern-checked (`css_color`).
  * `esc()` remains for blocks.py's own HTML *attribute* contexts, which are the
    one place stripping is not enough.

Everything is stdlib — no bleach — because these paths ship inside the .mcpb
bundle and every dependency is weight there.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# ── allowlists ───────────────────────────────────────────────────────────────
# Inline/structural formatting an author plausibly wants in verbatim material.
# Deliberately excludes anything that can load or run: script, style, iframe,
# object, embed, form, input, link, meta, base, svg (handled separately).
MARKUP_TAGS = {
    "b", "strong", "i", "em", "u", "s", "mark", "small", "code", "kbd", "abbr",
    "sup", "sub", "br", "span", "p", "div", "ul", "ol", "li", "dl", "dt", "dd",
    "blockquote", "cite", "q", "a", "h3", "h4", "h5", "h6", "hr", "table",
    "thead", "tbody", "tr", "th", "td", "figure", "figcaption",
}
MARKUP_ATTRS = {
    "a": {"href", "title"},
    "abbr": {"title"},
    "span": {"class"},
    "div": {"class"},
    "p": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
VOID_TAGS = {"br", "hr"}

SVG_TAGS = {
    "svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline",
    "polygon", "defs", "lineargradient", "radialgradient", "stop", "title",
    "desc", "clippath", "mask", "use", "symbol", "text", "tspan", "filter",
    "fedropshadow", "fegaussianblur", "femerge", "femergenode", "feoffset",
    "feflood", "fecomposite", "feblend", "fecolormatrix",
}
SVG_ATTRS = {
    "viewbox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
    "r", "rx", "ry", "d", "points", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-opacity",
    "fill-opacity", "fill-rule", "clip-rule", "opacity", "transform",
    "gradientunits", "gradienttransform", "offset", "stop-color",
    "stop-opacity", "id", "class", "style", "xmlns", "xmlns:xlink",
    "preserveaspectratio", "vector-effect", "dx", "dy", "stddeviation",
    "flood-color", "flood-opacity", "in", "in2", "result", "type", "values",
    "font-size", "font-family", "font-weight", "text-anchor", "dominant-baseline",
}

# `url(...)`, `expression(...)` and `@import` are the CSS escape hatches that
# can fetch or execute; a style attribute keeping only safe declarations is
# still useful for SVG glyphs, so filter rather than drop.
_CSS_BAD = re.compile(r"(?:url\s*\(|expression\s*\(|@import|javascript:)", re.I)
_SAFE_URL = re.compile(r"^(?:https?:|mailto:|#|/(?!/)|[^:/?#]*(?:[/?#]|$))", re.I)

# A color that is safe to drop into `'…'` in JS or a CSS declaration.
_CSS_COLOR = re.compile(
    r"^(?:#[0-9a-fA-F]{3,8}"
    r"|var\(--[a-z][a-z0-9-]{0,47}\)"
    r"|rgba?\([\d\s.,%]{1,40}\)"
    r"|hsla?\([\d\s.,%deg]{1,40}\)"
    r"|[a-zA-Z]{3,20})$")


def esc(s) -> str:
    """HTML-escape text, quotes included. Safe in element and attribute bodies."""
    return html.escape("" if s is None else str(s), quote=True)


def unescape_text(s) -> str:
    """Undo `esc()` for the few sinks that are neither HTML nor innerHTML."""
    return html.unescape("" if s is None else str(s))


def plain_text(s) -> str:
    """Tag-free, entity-decoded text — the default for plain-text fields.

    Repeated until stable so that nested or split constructs (`<scr<b>ipt>`,
    `<<a>script>`) cannot reassemble into a tag once an inner match is removed.
    """
    out = unescape_text(s)
    for _ in range(6):
        nxt = re.sub(r"<[^>]*>|<[^>]*$", "", out)
        # A lone '<' with no '>' is still a tag opener to a parser; drop it too.
        nxt = nxt.replace("<", "")
        if nxt == out:
            break
        out = nxt
    return out


def one_line(s) -> str:
    """`plain_text` collapsed to a single line — for a share sheet or a mailto
    subject, which display a string rather than parse it."""
    return re.sub(r"\s+", " ", plain_text(s)).strip()


def css_color(value, fallback: str) -> str:
    """A color literal safe for a CSS declaration or a quoted JS string."""
    v = ("" if value is None else str(value)).strip()
    return v if _CSS_COLOR.match(v) else fallback


def _safe_url(value: str) -> str | None:
    v = (value or "").strip().replace("\x00", "")
    # Control characters are how `java\tscript:` slips past a naive scheme check.
    v = re.sub(r"[\x00-\x20]", "", v)
    return v if _SAFE_URL.match(v) else None


def _safe_style(value: str) -> str | None:
    return None if _CSS_BAD.search(value or "") else (value or "").strip() or None


class _Allowlist(HTMLParser):
    """Rebuild a fragment keeping only allowlisted tags and attributes.

    Text inside a dropped tag is kept (so stripping `<script>` wrappers doesn't
    silently delete an author's prose), except for tags whose *content* is code
    rather than prose — script/style — which are dropped whole.
    """

    DROP_CONTENT = {"script", "style"}

    def __init__(self, tags: set, attrs, svg: bool = False):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs, self.svg = tags, attrs, svg
        self.out: list[str] = []
        self._open: list[str] = []
        self._suppress = 0

    def _allowed_attrs(self, tag: str):
        return self.attrs if self.svg else self.attrs.get(tag, set())

    def _emit_attrs(self, tag, attrs) -> str:
        allowed, parts = self._allowed_attrs(tag), []
        for name, value in attrs:
            name = (name or "").lower()
            # Blocks every event handler in one rule, including ones that don't
            # exist yet — an allowlist of attrs plus this is belt and braces.
            if name.startswith("on") or name not in allowed:
                continue
            value = "" if value is None else value
            if name in ("href", "src", "xlink:href"):
                value = _safe_url(value)
            elif name == "style":
                value = _safe_style(value)
            if value is None:
                continue
            parts.append(f' {name}="{html.escape(str(value), quote=True)}"')
        return "".join(parts)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.DROP_CONTENT:
            self._suppress += 1
            return
        if self._suppress or tag not in self.tags:
            return
        self.out.append(f"<{tag}{self._emit_attrs(tag, attrs)}>")
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self._suppress or tag not in self.tags:
            return
        self.out.append(f"<{tag}{self._emit_attrs(tag, attrs)}/>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.DROP_CONTENT:
            self._suppress = max(0, self._suppress - 1)
            return
        if self._suppress or tag not in self.tags or tag in VOID_TAGS:
            return
        if tag in self._open:
            # Close anything left dangling so a stray </div> can't unbalance the
            # surrounding page structure.
            while self._open:
                open_tag = self._open.pop()
                self.out.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data):
        if not self._suppress:
            self.out.append(html.escape(data, quote=False))

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def unknown_decl(self, data):
        pass

    def handle_pi(self, data):
        pass

    def result(self) -> str:
        while self._open:
            self.out.append(f"</{self._open.pop()}>")
        return "".join(self.out)


def _run(value, tags, attrs, svg=False) -> str:
    if not value:
        return ""
    p = _Allowlist(tags, attrs, svg)
    p.feed(str(value))
    p.close()
    return p.result()


def clean_markup(value) -> str:
    """Allowlisted inline HTML — for fields documented as carrying markup."""
    return _run(value, MARKUP_TAGS, MARKUP_ATTRS)


def clean_svg(value) -> str:
    """Allowlisted inline SVG — for entity/axis `symbol_svg` glyphs."""
    return _run(value, SVG_TAGS, SVG_ATTRS, svg=True)


# ── the one entry point the build path calls ─────────────────────────────────
_FLAG = "_alto_sanitized"


def sanitize_brief(b, nodes=None) -> None:
    """Escape plain text and allowlist markup, in place. Idempotent.

    Call exactly once per Brief before blocks.py sees it. The flag makes a
    second call a no-op rather than double-escaping `&` into `&amp;amp;`.
    """
    if getattr(b, _FLAG, False):
        return

    def sections(items):
        for s in items or []:
            s.h = plain_text(s.h)          # `<h3>${s.h}</h3>`, raw
            s.t = clean_markup(s.t)        # `<p>${s.t}</p>`, raw and markup-bearing

    b.title = plain_text(b.title)
    b.subject = plain_text(b.subject)
    b.entity_axis_label = plain_text(b.entity_axis_label)
    b.entity_axis_singular = plain_text(b.entity_axis_singular)
    b.node_noun = plain_text(b.node_noun)
    b.overview_html = clean_markup(b.overview_html)
    # These two land inside single-quoted JS literals in the sign-in stub, so
    # they additionally must not contain a quote that closes the literal.
    b.owner_name = one_line(b.owner_name).replace("'", "’")
    b.owner_email = one_line(b.owner_email).replace("'", "")

    for a in b.acts:
        a.label, a.short = plain_text(a.label), plain_text(a.short)
    for e in b.entities:
        e.name, e.role = plain_text(e.name), plain_text(e.role)
        e.symbol_svg = clean_svg(e.symbol_svg)
        sections(e.sections)
    for ax in b.axes:
        ax.label, ax.singular = plain_text(ax.label), plain_text(ax.singular)
        for v in ax.values:
            v.name, v.role = plain_text(v.name), plain_text(v.role)
            v.symbol_svg = clean_svg(v.symbol_svg)
            sections(v.sections)
    for r in b.relations:
        r.label = plain_text(r.label)

    for n in nodes or []:
        n.tag, n.title = plain_text(n.tag), plain_text(n.title)
        # desc renders escaped on the card but raw as the fallback detail
        # section, so markup would look broken on one of the two either way —
        # plain text is the only presentation that is right in both places.
        n.desc = plain_text(n.desc)
        n.color = css_color(n.color, "") if n.color else ""
        sections(n.sections)

    setattr(b, _FLAG, True)
