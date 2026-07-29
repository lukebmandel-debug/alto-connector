"""Emit the homepage and reports pages for a project/timeline set.

Used two ways:
- Offline bundle: a static snapshot listing the bundled timeline(s).
- Hosted (M3): the server renders the same template with the signed-in user's
  projects injected at request time.
"""
from __future__ import annotations

import json
from pathlib import Path

from .brief import Brief
from .emit import emit

from ..engine import template as engine_template


def _js(s):
    return json.dumps(s or "", ensure_ascii=False)


def projects_const(projects: list[dict]) -> str:
    """projects: [{name, courses:[{title, href, sub, courseId, reports, units[]}]}]"""
    slabs = []
    for p in projects:
        courses = ",".join(
            "\n    { title:%s, href:%s, sub:%s,\n"
            "      courseId:%s, reports:%s,\n"
            "      units:%s }" % (
                _js(c["title"]), _js(c["href"]), _js(c.get("sub", "")),
                _js(c["courseId"]), "true" if c.get("reports", True) else "false",
                json.dumps(c.get("units", [])))
            for c in p["courses"])
        slabs.append("\n  { name:%s, courses:[%s,\n  ]}" % (_js(p["name"]), courses))
    return "const PROJECTS = [%s,\n];" % ",".join(slabs)


# Generalized search: fetch every live course href and index its NODES_SRC.
SEARCH_COURSE_FN = """function extractCourse(html, courseTitle, courseHref){
    const out = [];
    const s = html.indexOf('const NODES_SRC=[');
    if(s < 0) return out;
    let e = html.indexOf('\\n];', s);
    const block = html.slice(s, e < 0 ? s + 400000 : e);
    const re = /\\{id:'((?:[^'\\\\]|\\\\.)*)'[\\s\\S]*?title:'((?:[^'\\\\]|\\\\.)*)'\\s*,\\s*desc:'((?:[^'\\\\]|\\\\.)*)'/g;
    let m;
    while((m = re.exec(block))){
      out.push({kind:courseTitle, title:unesc(m[2]), text:unesc(m[3]),
                go:(id => () => { location.href = courseHref + '#find=' + id; })(m[1])});
    }
    return out;
  }"""

SEARCH_FETCH = """if(!courseLoading){
      courseLoading = true;
      PROJECTS.forEach(p => p.courses.forEach(c => {
        if(c.comingSoon || !c.href) return;
        fetch(c.href)
          .then(r => r.ok ? r.text() : '')
          .then(html => { if(html) INDEX = INDEX.concat(extractCourse(html, c.title, c.href)); render(input.value); })
          .catch(() => {});
      }));
    }"""


def build_home(projects: list[dict]) -> str:
    template = engine_template("home_template.html")
    regions = {
        "projects": projects_const(projects),
        "search_course_fn": SEARCH_COURSE_FN,
        "search_fetch": SEARCH_FETCH,
    }
    return emit(template, regions, {})


def course_meta_const(courses: list[dict]) -> str:
    entries = ",".join(
        "\n  %s: {\n    title: %s, project: %s, app: %s,\n    units: %s\n  }" % (
            json.dumps(c["courseId"]), _js(c["title"]), _js(c.get("project", "")),
            _js(c["href"]), json.dumps(c.get("units", [])))
        for c in courses)
    return "const COURSE_META = {%s\n};" % entries


def build_reports(courses: list[dict], default_course: str) -> str:
    template = engine_template("reports_template.html")
    regions = {"course_meta": course_meta_const(courses)}
    tokens = {"default_course":
              f"params.get('course') || {json.dumps(default_course)}"}
    return emit(template, regions, tokens)


def course_entry_for(brief: Brief, project_name: str = "",
                     href: str = "terrarium_glass.html") -> dict:
    n_acts = len(brief.acts)
    return {
        "title": brief.title,
        "href": href,
        "sub": f"{n_acts} {'act' if n_acts == 1 else 'acts'}",
        "courseId": brief.timeline_id,
        "reports": True,
        "project": project_name,
        "units": [a.color for a in brief.acts],
    }
