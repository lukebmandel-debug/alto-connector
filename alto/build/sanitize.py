"""Make user-supplied brief content safe to interpolate into a timeline page.

Why this exists, and why it has to live here rather than in the engine: the
engine renders detail sections with

    sections.map(s=>`<div class="detail-section"><h3>${s.h}</h3><p>${s.t}</p></div>`)

straight into `innerHTML`, with no escaping — that is inherited Terrarium
behavior and `engine/` is frozen. So a string's journey through `js_str()`
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
    "blockquote", "cite", "q", "a", "h2", "h3", "h4", "h5", "h6", "hr", "table",
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

# A deep link the engine understands: `showDetail('<type>','<id>')`, optionally
# as a `javascript:` href and optionally trailed by `return false`. The four
# types are the engine's own (node / char=entity / env=axis1 / theme=axis2).
# Full-match, and the id is the same slug shape as a node id (brief.ID_RE), so
# the captured value is safe to interpolate back into the emitted markup — it
# can carry no quote or space to break out of the attribute.
_SHOWDETAIL_RE = re.compile(
    r"^\s*(?:javascript:\s*)?showDetail\(\s*['\"](node|char|env|theme)['\"]\s*,"
    r"\s*['\"]([a-z][a-z0-9-]{0,47})['\"]\s*\)\s*;?\s*"
    r"(?:return\s+false\s*;?\s*)?$")

DETAIL_TYPES = ("node", "char", "env", "theme")


def _showdetail_target(attrs) -> "tuple[str, str] | None":
    """The (type, id) an <a>'s onclick/href deep-links to, or None if it isn't a
    showDetail link."""
    for name, value in attrs:
        if (name or "").lower() in ("onclick", "href") and value:
            m = _SHOWDETAIL_RE.match(value.strip())
            if m:
                return m.group(1), m.group(2)
    return None


def esc(s) -> str:
    """HTML-escape text, quotes included. Safe in element and attribute bodies."""
    return html.escape("" if s is None else str(s), quote=True)


# ── links to the material's own documents (the source map) ──────────────────
# `src:<id>` names a source by its manifest id; the build writes the real link.
_SRC_REF = re.compile(r"^\s*src:([a-z][a-z0-9-]{0,47})\s*$")

# Beside every link to a source that has a copy on the author's computer. It
# carries only the source id — the path lives in the page's _ALTO_LOCAL map
# (detail_extras.LOCAL_SOURCES), which a share snapshot drops — and it stays
# hidden unless that script finds the page open from disk.
LOCAL_ICON = ('<a href="#" class="alto-src-local" data-src-local="{id}" '
              'title="Open the copy on this computer"></a>')


def _url_key(u: str) -> str:
    """A document URL cut down to what names the document: no query or
    fragment, no trailing /edit, /view or /preview. A link to a heading
    (…/edit#heading=h.x) and a sharing link (…/edit?usp=sharing) both still
    name the source recorded as …/edit."""
    v = (u or "").strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return re.sub(r"/(?:edit|view|preview)$", "", v)


class SourceMap:
    """The brief's source_docs, for recognising links to them in text."""

    def __init__(self, docs):
        self.by_id, self.by_url = {}, {}
        for d in docs or []:
            if not isinstance(d, dict) or not d.get("id"):
                continue
            url = _safe_url(d.get("url") or "") or ""
            self.by_id[d["id"]] = {"url": url if url.startswith("https://") else "",
                                   "local": bool(d.get("local"))}
            if self.by_id[d["id"]]["url"]:
                self.by_url.setdefault(_url_key(url), d["id"])

    def __bool__(self):
        return bool(self.by_id)

    def resolve(self, href: str) -> "tuple[str | None, str | None]":
        """(source id, None) for a link to a known source; (None, id) for a
        `src:` link to an unknown one; (None, None) for anything else."""
        m = _SRC_REF.match(href or "")
        if m:
            return (m.group(1), None) if m.group(1) in self.by_id else (None, m.group(1))
        if re.match(r"^https://", href or "", re.I):
            return self.by_url.get(_url_key(href)), None
        return None, None


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

    def __init__(self, tags: set, attrs, svg: bool = False, node_ids=None,
                 link_types=None, sources=None):
        super().__init__(convert_charrefs=True)
        # The source map (SourceMap), so a link to one of the material's own
        # documents is recognised and can offer its copy on this computer.
        self.sources = sources
        self.tags, self.attrs, self.svg = tags, attrs, svg
        # None → ordinary markup mode; a set → overview mode, where <a> tags
        # carrying a showDetail() deep link are rewritten to the engine's
        # clickable-chip markup (known id) or demoted to plain text (unknown).
        self.node_ids = node_ids
        # id → detail type, for detail-page text. Present means deep links are
        # resolved by id rather than trusting the authored type.
        self.link_types = link_types
        self.out: list[str] = []
        self._open: list[str] = []
        self._anchor_stack: list[str] = []
        self._suppress = 0
        self.warnings: list[str] = []

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
        if tag == "a" and (self.node_ids is not None
                           or self.link_types is not None):
            self._open_overview_anchor(attrs)
            return
        self.out.append(f"<{tag}{self._emit_attrs(tag, attrs)}>")
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def _open_source_anchor(self, attrs, href) -> bool:
        """A link to a document in the source map: its web link (when it has
        one) tagged with the source id, and — for a source with a copy on this
        computer — the local icon after it (see handle_endtag). A `src:` link
        to an unknown id keeps its text only. False when `href` is neither."""
        sid, unknown = self.sources.resolve(href)
        if unknown:
            where = "overview" if self.node_ids is not None else "detail text"
            self.warnings.append(f"{where}: link to unknown source {unknown!r} "
                                 "shown as plain text")
            self._anchor_stack.append("drop")
            return True
        if not sid:
            return False
        d = self.sources.by_id[sid]
        if not (d["url"] or d["local"]):
            self._anchor_stack.append("drop")
            return True
        title = self._emit_attrs("a", [(k, v) for k, v in attrs
                                       if (k or "").lower() == "title"])
        if d["url"]:
            self.out.append(f'<a href="{esc(d["url"])}"{title} class="note-link" '
                            f'target="_blank" rel="noopener" data-src="{sid}">')
        else:
            # Only on this computer: nothing to open on the web, so the link
            # goes nowhere there (LOCAL_SOURCES stops the '#').
            self.out.append(f'<a href="#"{title} class="note-link" data-src="{sid}">')
        self._anchor_stack.append("a+local:" + sid if d["local"] else "a")
        return True

    def _close_anchor(self, action):
        if action == "span":
            self.out.append("</span>")
        elif action == "a":
            self.out.append("</a>")
        elif action.startswith("a+local:"):
            self.out.append("</a>" + LOCAL_ICON.format(id=action[8:]))
        # "drop" closes nothing — the wrapper emitted nothing to close.

    def _open_overview_anchor(self, attrs):
        """Rewrite an <a> per its showDetail() target. The visible link text
        flows through handle_data unchanged; the matching </a> is closed in
        handle_endtag off _anchor_stack (not _open, since the emitted wrapper is
        a <span>, not an <a>)."""
        target = _showdetail_target(attrs)
        if target is None:
            # Not a deep link — keep it as a normal <a> (any onclick is stripped
            # by _emit_attrs' on* rule, exactly as before this mode existed).
            # A link out of the page (a source doc, a casebook page) opens in a
            # new tab and is styled as one: the page runs inside a frame on
            # every host, where following it in place would replace Alto.
            ext = ""
            href = next((v for k, v in attrs if (k or "").lower() == "href"), "") or ""
            if self.sources is not None and self._open_source_anchor(attrs, href):
                return
            if re.match(r"^https?://", (_safe_url(href) or ""), re.I):
                ext = ' class="note-link" target="_blank" rel="noopener"'
            self.out.append(f"<a{self._emit_attrs('a', attrs)}{ext}>")
            self._anchor_stack.append("a")
            return
        authored, lid = target

        # Resolve by id, not by the authored type. Across a long outline nobody
        # reliably remembers that a concept is 'node' and a case is 'env', and a
        # mistyped link would otherwise ship as a chip that opens nothing.
        kind = None
        if self.link_types is not None:
            kind = self.link_types.get(lid)
        if kind is None and self.node_ids is not None and lid in self.node_ids:
            kind = "node"
        overview = self.node_ids is not None
        where = "overview" if overview else "detail text"

        if kind is None:
            # validate-before-write: a link to something that does not exist
            # never ships as a dead chip — it becomes plain prose, and warns.
            # The overview resolves nodes only, so name that; detail text can
            # reach concepts, entities and axis values alike.
            self.warnings.append(
                f"{where}: deep link to unknown {'node' if overview else 'id'} "
                f"{lid!r} demoted to plain text")
            self._anchor_stack.append("drop")
            return
        if kind != authored:
            self.warnings.append(
                f"{where}: link to {lid!r} was typed {authored!r} but resolves "
                f"as {kind!r} — corrected")

        if self.node_ids is not None and kind == "node":
            # The engine's initOverviewNavLinks reads the node id from the hidden
            # button's onclick and turns the span into a clickable chip.
            self.out.append(
                '<span class="ov-node-link"><button class="ov-node-btn" '
                f"onclick=\"showDetail('node','{lid}')\"></button>")
        else:
            # Everywhere else — detail pages, and non-node overview targets —
            # initOverviewNavLinks cannot reach: it runs once, only when the
            # overview panel opens, and only for 'node'. A data-attribute span
            # driven by one delegated handler works on desktop, mobile and peek.
            self.out.append(
                f'<span class="alto-link" data-sd-type="{kind}" '
                f'data-sd-id="{lid}">')
        self._anchor_stack.append("span")

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
        if self._suppress:
            return
        if (tag == "a" and self._anchor_stack
                and (self.node_ids is not None or self.link_types is not None)):
            self._close_anchor(self._anchor_stack.pop())
            return
        if tag not in self.tags or tag in VOID_TAGS:
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
        # Close any overview anchors the author left unbalanced.
        for action in reversed(self._anchor_stack):
            self._close_anchor(action)
        self._anchor_stack.clear()
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


def clean_linked_markup(value, link_types, sources=None) -> "tuple[str, list[str]]":
    """`clean_markup` plus deep-link rewriting, for detail-page section text.

    An <a> whose onclick/href is `showDetail('<type>','<id>')` becomes an
    `alto-link` span **resolved by id** — the authored type is advisory and a
    mismatch is corrected with a warning. An unknown id demotes to plain text,
    same as the overview does. Returns (html, warnings)."""
    if not value:
        return "", []
    p = _Allowlist(MARKUP_TAGS, MARKUP_ATTRS, link_types=link_types or {},
                   sources=sources)
    p.feed(str(value))
    p.close()
    return p.result(), p.warnings


def clean_overview(value, node_ids, sources=None) -> "tuple[str, list[str]]":
    """Allowlisted inline HTML for the overview panel, plus deep-link rewriting:
    an <a> whose onclick/href is `showDetail('node','<id>')` becomes the engine's
    clickable-chip markup when the id is a live node, or plain text (with a
    warning) when it isn't. Returns (html, warnings)."""
    if not value:
        return "", []
    p = _Allowlist(MARKUP_TAGS, MARKUP_ATTRS, node_ids=node_ids or set(),
                   sources=sources)
    p.feed(str(value))
    p.close()
    return p.result(), p.warnings


def clean_svg(value) -> str:
    """Allowlisted inline SVG — for entity/axis `symbol_svg` glyphs."""
    return _run(value, SVG_TAGS, SVG_ATTRS, svg=True)


# ── the one entry point the build path calls ─────────────────────────────────
_FLAG = "_alto_sanitized"


def sanitize_connections(b, nodes, connections) -> "tuple[list, list[str]]":
    """Make each connection's explanation (its optional fourth element) inert.

    It lands in the engine's innerHTML on a node's "How they connect" section,
    so it gets the same treatment as detail-page text: allowlisted markup, and
    a link to another node that resolves by id. Returns (connections, warnings).
    """
    link_types = {}
    for slot, ax in zip(("env", "theme"), b.axes[:2]):
        link_types.update({v.id: slot for v in ax.values})
    link_types.update({e.id: "char" for e in b.entities})
    link_types.update({n.id: "node" for n in (nodes or [])})
    out, warnings = [], []
    for c in connections or []:
        if len(c) == 4 and c[3]:
            how, w = clean_linked_markup(c[3], link_types, SourceMap(b.source_docs))
            warnings.extend(f"connection {c[0]} → {c[1]}: {m}" for m in w)
            out.append([c[0], c[1], c[2], how])
        else:
            out.append([c[0], c[1], c[2]] if len(c) >= 3 else list(c))
    return out, warnings


def sanitize_brief(b, nodes=None) -> list:
    """Escape plain text and allowlist markup, in place. Idempotent.

    Returns overview deep-link warnings (unknown-node demotions). Call exactly
    once per Brief before blocks.py sees it; the flag makes a second call a no-op
    (rather than double-escaping `&` into `&amp;amp;`) and re-returns the same
    warnings.
    """
    if getattr(b, _FLAG, False):
        return getattr(b, "_alto_sanitize_warnings", [])

    # id → detail type, so a link in section text resolves to the right page
    # whatever type it was authored with. Nodes are written last and win: a
    # concept and a case that share an id is a data problem, not a link problem.
    link_types = {}
    for slot, ax in zip(("env", "theme"), b.axes[:2]):
        link_types.update({v.id: slot for v in ax.values})
    link_types.update({e.id: "char" for e in b.entities})
    link_types.update({n.id: "node" for n in (nodes or [])})

    sec_warnings: list[str] = []
    # Read before the source_docs themselves are cleaned below; SourceMap
    # applies the same https-only rule to each url.
    sources = SourceMap(b.source_docs)

    def sections(items, what):
        for i, s in enumerate(items or []):
            s.h = plain_text(s.h)          # `<h3>${s.h}</h3>`, raw
            # `<p>${s.t}</p>`, raw and markup-bearing — so deep links survive
            # here, unlike node.desc which has to stay plain (see below).
            s.t, w = clean_linked_markup(s.t, link_types, sources)
            sec_warnings.extend(f"{what} section {i + 1}: {m}" for m in w)
            if getattr(s, "tree", None):
                from .subtree import sanitize_tree
                sec_warnings.extend(sanitize_tree(s.tree, link_types, sources,
                                                  f"{what} section {i + 1}"))

    b.title = plain_text(b.title)
    b.subject = plain_text(b.subject)
    b.entity_axis_label = plain_text(b.entity_axis_label)
    b.entity_axis_singular = plain_text(b.entity_axis_singular)
    b.node_noun = plain_text(b.node_noun)
    b.index_label = plain_text(b.index_label) or "Index"
    b.overview_html, ov_warnings = clean_overview(
        b.overview_html, {n.id for n in (nodes or [])}, sources)
    # These two land inside single-quoted JS literals in the sign-in stub, so
    # they additionally must not contain a quote that closes the literal.
    b.owner_name = one_line(b.owner_name).replace("'", "’")
    b.owner_email = one_line(b.owner_email).replace("'", "")

    for a in b.acts:
        a.label, a.short = plain_text(a.label), plain_text(a.short)
        a.summary = plain_text(a.summary)
    # The source map: names are text; a url survives only as https.
    docs = []
    for d in b.source_docs:
        u = _safe_url(d.get("url") or "") or ""
        docs.append({"id": d["id"], "name": plain_text(d.get("name") or d["id"]),
                     "url": u if u.startswith("https://") else "",
                     # A path, never markup: it reaches the page only inside
                     # the JSON of detail_extras.local_sources.
                     "local": d.get("local") or ""})
    b.source_docs = docs

    def cite(c):
        out = {k: plain_text(str(c[k])) for k in ("ch", "note", "short") if c.get(k)}
        p = re.sub(r"[^0-9A-Za-z-]", "", str(c.get("p") or ""))[:12]
        if p:
            out["p"] = p
        return out
    for e in b.entities:
        e.name, e.role = plain_text(e.name), plain_text(e.role)
        e.symbol_svg = clean_svg(e.symbol_svg)
        sections(e.sections, f"entity {e.id}")
        e.aliases = [plain_text(x) for x in e.aliases if (x or "").strip()]
    for ax in b.axes:
        ax.label, ax.singular = plain_text(ax.label), plain_text(ax.singular)
        ax.nav_label = plain_text(ax.nav_label)
        ax.index_blurb = [plain_text(h) for h in ax.index_blurb]
        sections(ax.index_sections, f"{ax.label} index")
        for v in ax.values:
            v.name, v.role = plain_text(v.name), plain_text(v.role)
            v.group = plain_text(v.group)
            v.symbol_svg = clean_svg(v.symbol_svg)
            sections(v.sections, f"{ax.label} value {v.id}")
            v.aliases = [plain_text(x) for x in v.aliases if (x or "").strip()]
            v.cite = cite(v.cite or {})
    for f in b.filters:
        f.label = plain_text(f.label)
        for v in f.values:
            v.name = plain_text(v.name)
    for r in b.relations:
        r.label = plain_text(r.label)
    for fl in b.flags:
        fl['name'] = plain_text(fl.get('name', ''))

    for n in nodes or []:
        n.tag, n.title = plain_text(n.tag), plain_text(n.title)
        # desc renders escaped on the card but raw as the fallback detail
        # section, so markup would look broken on one of the two either way —
        # plain text is the only presentation that is right in both places.
        n.desc = plain_text(n.desc)
        n.color = css_color(n.color, "") if n.color else ""
        sections(n.sections, f"node {n.id}")

    setattr(b, _FLAG, True)
    warnings = ov_warnings + sec_warnings
    setattr(b, "_alto_sanitize_warnings", warnings)
    return warnings
