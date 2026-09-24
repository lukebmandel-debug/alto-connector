"""Package one or more built timelines + a generated home snapshot into ONE
offline HTML file — a direct port of Terrarium's build_single_file.py
(srcdoc-iframe shell, __altoSwap router, SHIM link rerouting, cloud tag
stripped), with the Terrarium-specific anchors parameterized by timeline id.

Every timeline in a bundle gets the router key `t_<n>`, served at the synthetic
href `t_<n>.html`. The reports repository is deliberately NOT bundled: an
offline copy carries the timelines and their detail pages, nothing else.
"""
from __future__ import annotations

import html as _html
import json

from .brief import Brief
from .pages import build_home, course_entry_for


class BundleError(ValueError):
    pass


def _rep(html, old, new, n, label):
    c = html.count(old)
    if c != n:
        raise BundleError(f"{label}: found {c} != {n} :: {old[:60]!r}")
    return html.replace(old, new)


SHIM = ("<script>(function(){function go(u){try{var p=window.parent;"
        "if(p&&p!==window&&p.__altoSwap){p.__altoSwap(String(u));return true;}}catch(e){}return false;}"
        "window.__altoGo=function(u){if(!go(u))location.href=u;};"
        "window.__altoSearch=function(){return(window.__altoQuery&&window.__altoQuery.search)||location.search;};"
        "window.__altoHash=function(){return(window.__altoQuery&&window.__altoQuery.hash!==undefined&&window.__altoQuery.hash!=='')"
        "?window.__altoQuery.hash:location.hash;};"
        # Capture phase, so this runs BEFORE any handler on the element itself.
        # That is what makes it a reliable link router — and also why it has to
        # step aside for buttons: the tile's share and reports controls sit inside
        # the course-tile anchor and cancel the click in their own bubble-phase
        # handler, which never got to run. Clicking share silently opened the
        # timeline instead of sharing.
        "document.addEventListener('click',function(e){var t=e.target;"
        "if(t&&t.closest&&t.closest('button'))return;"
        "var a=t&&t.closest&&t.closest('a[href]');"
        # t_<n>.html is a bundled timeline. Without it here the chip anchors in a
        # multi-timeline bundle fall through to a real navigation and 404.
        "if(!a)return;var h=a.getAttribute('href')||'';if(/^(index|terrarium_glass|reports|t_\\d+)\\.html/.test(h))"
        "{e.preventDefault();window.__altoGo(h);}},true);"
        "})();</script>")

CLOUD_TAG = '<script type="module" src="alto-cloud.js"></script>\n'


def _inject_shim(html, label):
    i = html.find("<head>")
    if i < 0:
        raise BundleError(f"{label}: no <head>")
    return html[:i + 6] + SHIM + html[i + 6:]


def _embed(html):
    return json.dumps(html).replace("<", "\\u003c")


def _prepare_timeline(tl: str, tid: str, label: str) -> str:
    """Reroute one timeline document's navigation into the bundle's router."""
    tl = _rep(tl, CLOUD_TAG, "", 1, f"strip cloud tag ({label})")
    tl = _rep(tl, "onclick=\"location.href='index.html'\"",
              "onclick=\"__altoGo('index.html')\"", 2, f"{label} clef+wordmark")
    # The reports repository is not bundled, so its button has nowhere to go —
    # hide it rather than route it at a missing document.
    tl = _rep(tl,
              f"onclick=\"location.href='reports.html?course={tid}&amp;from=project'\"",
              "style=\"display:none\" onclick=\"return false\"",
              1, f"{label} reports btn (hidden: no reports in bundle)")
    tl = _rep(tl, "location.href='index.html'", "__altoGo('index.html')",
              2, f"{label} mobile brand (js)")
    tl = _rep(tl, "location.hash", "__altoHash()", 3, f"{label} hash reads")
    return _inject_shim(tl, label)


# The framed page's own account panel is built in JS, so there is no markup to
# rewrite — hide it with a style instead. In an offline bundle the simulated
# account is honest enough (there is no server to be signed in to), but in the
# private view the session is REAL and belongs to the shell: the framed panel
# would offer a "Sign out" that clears a localStorage key, changes nothing about
# Firebase, and leaves the timeline on screen. A sign-out control that lies
# about signing you out is worse than none.
_HIDE_FRAMED_ACCOUNT = "<style>#account-btn{display:none !important}</style>"

# Read by the private shell when it backfills a title, and never present in
# anything world-readable: this meta lives inside the page, which is in
# Firestore under the owner's uid, not in the shell that serves it.
PRIVATE_LABEL = "alto-label"


def private_page(brief: Brief, timeline_html: str, label: str = "") -> str:
    """The timeline prepared for srcdoc delivery by the private shell.

    Identical preparation to a bundled timeline — the cloud tag stripped (it
    cannot run at about:srcdoc anyway), navigation routed through __altoGo, the
    reports button hidden — but delivered as one document rather than embedded
    in a router, and with the framed account panel suppressed. The shell
    supplies __altoSwap; see alto/build/private_shell.py.
    """
    page = _prepare_timeline(timeline_html, brief.timeline_id, "private")
    i = page.find("<head>")
    if i < 0:
        raise BundleError("private: no <head>")
    # The name the owner's homepage shows. The page's own <title> is built from
    # the brief, and five outlines of one course all have the same brief title
    # — listing five tiles that all read "Civil Procedure" is no more use than
    # listing five that read "Untitled". The project name is what tells them
    # apart, and only the publisher knows it, so it is recorded here.
    meta = (f'<meta name="{PRIVATE_LABEL}" content="'
            f'{_html.escape(label or brief.title, quote=True)}">')
    return page[:i + 6] + meta + _HIDE_FRAMED_ACCOUNT + page[i + 6:]


def bundle(brief: Brief, timeline_html: str, project_name: str = "") -> str:
    """Return the single offline HTML file for one built timeline."""
    name = project_name or brief.subject or "Alto"
    return bundle_many([{"name": name, "items": [(brief, timeline_html)]}],
                       title=f"{brief.title} — Alto")


def bundle_many(groups: list[dict], title: str = "Alto") -> str:
    """Return ONE offline HTML file holding every timeline in `groups`.

    groups: [{"name": <project name>, "items": [(Brief, timeline_html), ...]}]

    One group with one item is the single-timeline bundle; several groups is a
    whole-site bundle. Router keys are assigned across the whole bundle, so a
    timeline's key is stable regardless of which project it sits in.
    """
    if not groups or not any(g["items"] for g in groups):
        raise BundleError("bundle_many: nothing to bundle")

    projects, docs, keys = [], {}, {}
    n = 0
    for g in groups:
        courses = []
        for brief, timeline_html in g["items"]:
            key = f"t_{n}"
            entry = course_entry_for(brief, g["name"], href=f"{key}.html")
            # No reports page in the bundle → no report bubble on the chip.
            entry["reports"] = False
            courses.append(entry)
            docs[key] = _prepare_timeline(timeline_html, brief.timeline_id, key)
            keys[f"{key}.html"] = key
            n += 1
        if courses:
            projects.append({"name": g["name"], "courses": courses})

    home = build_home(projects)

    # strip the hosted-only cloud loader
    home = _rep(home, CLOUD_TAG, "", 1, "strip cloud tag (home)")

    # home edits
    home = _rep(home,
                "location.href = 'reports.html?course=' + encodeURIComponent(c.courseId) + '&from=home';",
                "__altoGo('reports.html?course=' + encodeURIComponent(c.courseId) + '&from=home');",
                1, "home reports link")
    home = _rep(home,
                "go:(id => () => { location.href = courseHref + '#find=' + id; })(m[1])",
                "go:(id => () => { __altoGo(courseHref + '#find=' + id); })(m[1])",
                1, "home search deep-link")
    # Search indexes every bundled timeline, so the source has to resolve the
    # course's own href to its router key rather than assume a single doc.
    home = _rep(home,
                "fetch(c.href)\n          .then(r => r.ok ? r.text() : '')",
                "Promise.resolve((function(){try{var p=window.parent;"
                "var k=String(c.href||'').replace(/^\\.?\\//,'').replace(/\\.html$/,'');"
                "return (p&&p.__altoDoc&&p.__altoDoc(k))||'';}catch(e){return '';}})())",
                1, "home search source")
    # Share: the bundle runs every page in a srcdoc iframe, where location.href
    # is "about:srcdoc" — an invalid base, so `new URL(path, location.href)`
    # THREW. altoShareLink is async, so the throw became an unhandled rejection:
    # no toast, no copy, nothing at all happened on click. The relative path is
    # meaningless here anyway (the bundle is one file and always opens at
    # index.html — it has no deep links), so share the document that CONTAINS
    # the bundle when that is a real web address, and say so plainly when it is
    # a local file. Never throw: a share that cannot resolve still tells the user.
    home = _rep(home,
                "  const url = new URL(path, location.href).href;",
                "  var url = '';\n"
                "  try {\n"
                "    var top = (window.parent && window.parent !== window)\n"
                "      ? window.parent.location.href : location.href;\n"
                "    if(/^https?:/i.test(top||'')) url = top;\n"
                "  } catch(e){}\n"
                "  if(!url){ showToast('Offline copy \\u2014 send the file itself'); return; }",
                1, "home share base (srcdoc has no usable location.href)")
    home = _rep(home,
                "  if(isMobile){ location.href = web; return; }   // Claude mobile app intercepts the universal link\n",
                "  { window.open(web, '_blank'); return; }\n", 1, "openClaude mobile")
    home = _rep(home, "  location.href = 'claude://claude.ai/new?q=' + q;\n",
                "  window.open(web, '_blank');\n", 1, "openClaude desktop")
    home = _inject_shim(home, "home")
    docs["home"] = home

    for name, h in docs.items():
        for bad in ["location.href='index.html'", "location.href = 'reports.html",
                    "location.href = 'terrarium_glass.html",
                    "onclick=\"location.href='index.html'\""]:
            if bad in h:
                raise BundleError(f"{name}: residual un-routed nav :: {bad!r}")

    keys["index.html"] = "home"
    docs_js = ",\n".join(f"{k}:{_embed(v)}" for k, v in docs.items())
    title = _html.escape(title, quote=True)
    shell = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<title>{title}</title>\n'
        '<style>html,body{margin:0;padding:0;height:100%;background:#0b0d15}\n'
        '#stage{position:fixed;inset:0;width:100%;height:100%;border:0;display:block}</style>\n'
        '</head><body>\n'
        f'<iframe id="stage" title="{title}" allow="clipboard-write; clipboard-read"></iframe>\n'
        '<script>\n'
        'var __DOCS={' + docs_js + '};\n'
        'window.__altoDoc=function(k){return __DOCS[k]||"";};\n'
        'var __KEY=' + json.dumps(keys) + ';\n'
        'window.__altoSwap=function(url){\n'
        '  url=String(url||"index.html");\n'
        # [a-z0-9_] — bundled timelines are keyed t_0, t_1, ...
        '  var m=/^\\.?\\/?([a-z0-9_]+\\.html)(\\?[^#]*)?(#.*)?$/.exec(url);\n'
        '  var file=(m&&m[1])||"index.html", search=(m&&m[2])||"", hash=(m&&m[3])||"";\n'
        '  var key=__KEY[file]||"home";\n'
        '  var html=__DOCS[key]||"";\n'
        '  var q=JSON.stringify({search:search,hash:hash}).replace(/</g,"\\u003c");\n'
        '  html=html.replace("<head>","<head><script>window.__altoQuery="+q+";<\\/script>");\n'
        '  document.getElementById("stage").srcdoc=html;\n'
        '};\n'
        'window.__altoSwap("index.html");\n'
        '</script>\n'
        '</body></html>\n'
    )
    return shell
