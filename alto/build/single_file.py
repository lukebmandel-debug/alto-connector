"""Package a built timeline + generated home/reports snapshot into ONE offline
HTML file — a direct port of Terrarium's build_single_file.py (srcdoc-iframe
shell, __altoSwap router, SHIM link rerouting, cloud tag stripped), with the
Terrarium-specific anchors parameterized by timeline id.
"""
from __future__ import annotations

import json

from .brief import Brief
from .pages import build_home, build_reports, course_entry_for


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
        "document.addEventListener('click',function(e){var t=e.target;var a=t&&t.closest&&t.closest('a[href]');"
        "if(!a)return;var h=a.getAttribute('href')||'';if(/^(index|terrarium_glass|reports)\\.html/.test(h))"
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


def bundle(brief: Brief, timeline_html: str, project_name: str = "") -> str:
    """Return the single offline HTML file for one built timeline."""
    tid = brief.timeline_id
    course = course_entry_for(brief, project_name or brief.subject or "Alto")
    home = build_home([{"name": project_name or "Alto",
                        "courses": [course]}])
    reports = build_reports([course], tid)
    tl = timeline_html

    # strip the hosted-only cloud loader everywhere
    home = _rep(home, CLOUD_TAG, "", 1, "strip cloud tag (home)")
    tl = _rep(tl, CLOUD_TAG, "", 1, "strip cloud tag (timeline)")
    reports = _rep(reports, CLOUD_TAG, "", 1, "strip cloud tag (reports)")

    # home edits
    home = _rep(home,
                "location.href = 'reports.html?course=' + encodeURIComponent(c.courseId) + '&from=home';",
                "__altoGo('reports.html?course=' + encodeURIComponent(c.courseId) + '&from=home');",
                1, "home reports link")
    home = _rep(home,
                "go:(id => () => { location.href = courseHref + '#find=' + id; })(m[1])",
                "go:(id => () => { __altoGo(courseHref + '#find=' + id); })(m[1])",
                1, "home search deep-link")
    home = _rep(home,
                "fetch(c.href)\n          .then(r => r.ok ? r.text() : '')",
                "Promise.resolve((function(){try{var p=window.parent;"
                "return (p&&p.__altoDoc&&p.__altoDoc('timeline'))||'';}catch(e){return '';}})())",
                1, "home search source")
    home = _rep(home,
                "  if(isMobile){ location.href = web; return; }   // Claude mobile app intercepts the universal link\n",
                "  { window.open(web, '_blank'); return; }\n", 1, "openClaude mobile")
    home = _rep(home, "  location.href = 'claude://claude.ai/new?q=' + q;\n",
                "  window.open(web, '_blank');\n", 1, "openClaude desktop")
    home = _inject_shim(home, "home")

    # timeline edits (anchors parameterized by tid)
    tl = _rep(tl, "onclick=\"location.href='index.html'\"",
              "onclick=\"__altoGo('index.html')\"", 2, "tl clef+wordmark")
    tl = _rep(tl,
              f"onclick=\"location.href='reports.html?course={tid}&amp;from=project'\"",
              f"onclick=\"__altoGo('reports.html?course={tid}&amp;from=project')\"",
              1, "tl reports btn")
    tl = _rep(tl, "location.href='index.html'", "__altoGo('index.html')",
              2, "tl mobile brand (js)")
    tl = _rep(tl, "location.hash", "__altoHash()", 3, "tl hash reads")
    tl = _inject_shim(tl, "timeline")

    # reports edits
    reports = _rep(reports, "onclick=\"location.href='index.html'\"",
                   "onclick=\"__altoGo('index.html')\"", 2, "reports brand")
    reports = _rep(reports, "const params = new URLSearchParams(location.search);",
                   "const params = new URLSearchParams(window.__altoSearch?window.__altoSearch():location.search);",
                   1, "reports query read")
    reports = _inject_shim(reports, "reports")

    for name, h in [("home", home), ("timeline", tl), ("reports", reports)]:
        for bad in ["location.href='index.html'", "location.href = 'reports.html",
                    "location.href = 'terrarium_glass.html",
                    "onclick=\"location.href='index.html'\""]:
            if bad in h:
                raise BundleError(f"{name}: residual un-routed nav :: {bad!r}")

    title = f"{brief.title} — Alto"
    shell = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<title>{title}</title>\n'
        '<style>html,body{margin:0;padding:0;height:100%;background:#0b0d15}\n'
        '#stage{position:fixed;inset:0;width:100%;height:100%;border:0;display:block}</style>\n'
        '</head><body>\n'
        f'<iframe id="stage" title="{title}" allow="clipboard-write; clipboard-read"></iframe>\n'
        '<script>\n'
        'var __DOCS={home:' + _embed(home) + ',\ntimeline:' + _embed(tl) +
        ',\nreports:' + _embed(reports) + '};\n'
        'window.__altoDoc=function(k){return __DOCS[k]||"";};\n'
        'var __KEY={"index.html":"home","terrarium_glass.html":"timeline","reports.html":"reports"};\n'
        'window.__altoSwap=function(url){\n'
        '  url=String(url||"index.html");\n'
        '  var m=/^\\.?\\/?([a-z_]+\\.html)(\\?[^#]*)?(#.*)?$/.exec(url);\n'
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
