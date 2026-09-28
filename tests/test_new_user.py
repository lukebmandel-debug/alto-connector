"""What a brand-new user hit in the 1.8.37 end-to-end run (2026-09-27), each
pinned so it cannot come back:

- a project named "1L Fall" got the id `1l-fall`, which create_timeline then
  refused, stranding the project;
- the guide's `persona` was rejected by the brief;
- `sources` on nodes warned "not in source_docs — it will not be shown"
  although the build showed every one;
- per-character lines took palette colours unrelated to the character's chip;
- the .mcpb carried no firestore.rules, so its deploys shipped hosting only.
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

BRIEF = {"title": "Low Tide", "acts": [{"label": "Harbor"}, {"label": "Storm"}],
         "relations": [{"key": "spine", "label": "Ensemble"},
                       {"key": "nell", "label": "Nell"},
                       {"key": "ash-line", "label": "Ash", "entity": "ash"},
                       {"key": "weather", "label": "Weather"}]}
ENTS = [{"id": "nell", "name": "Nell"}, {"id": "ash", "name": "Ash"}]


@pytest.fixture(autouse=True)
def store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield
    srv.set_store(None)


def _timeline(kind="writing", brief=BRIEF):
    pid = srv.create_project("Low Tide", "map", kind)["project_id"]
    tid = srv.create_timeline(pid, brief)["timeline_id"]
    srv.record_materials_consent(
        tid, [{"id": "notes", "name": "Chapter notes.docx"}], True)
    return tid


# ── ids ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["1L Fall", "2026 Research", "7", "---"])
def test_any_project_name_can_hold_a_timeline(name):
    pid = srv.create_project(name, "", "studying")["project_id"]
    assert srv.ID_RE.match(pid), pid
    r = srv.create_timeline(pid, {"title": "Contracts",
                                  "acts": [{"label": "A"}, {"label": "B"}]})
    assert "timeline_id" in r, r


def test_a_legacy_digit_project_still_works(tmp_path):
    st = srv.get_store()
    st.put_project(srv.uid(), "1l-fall", {"project_id": "1l-fall",
                                          "name": "1L Fall", "kind": "studying"})
    r = srv.create_timeline("1l-fall", {"title": "Contracts",
                                        "acts": [{"label": "A"}, {"label": "B"}]})
    assert "timeline_id" in r, r
    # …and only an existing one: an unknown bad id is still refused as bad.
    assert srv.create_timeline("9nope", {"title": "x"})["error"] == "bad_id"


# ── persona ─────────────────────────────────────────────────────────────────

def test_persona_is_accepted_and_handed_back():
    p = {"name": "THE IN-LAW",
         "prompt": "Answers only from Priya's own outline; never adds outside law."}
    pid = srv.create_project("Contracts", "", "studying")["project_id"]
    r = srv.create_timeline(pid, {"title": "C", "acts": [{"label": "A"}, {"label": "B"}],
                                  "persona": p})
    assert "timeline_id" in r, r
    assert not any("persona" in w for w in r["warnings"])
    assert srv.get_timeline(r["timeline_id"])["brief"]["persona"] == p


def test_a_persona_that_forgets_the_closed_system_rule_warns():
    pid = srv.create_project("Contracts", "", "studying")["project_id"]
    r = srv.create_timeline(pid, {"title": "C", "acts": [{"label": "A"}, {"label": "B"}],
                                  "persona": {"name": "Pal", "prompt": "Be friendly."}})
    assert any("closed-system" in w for w in r["warnings"])
    bad = srv.create_timeline(pid, {"title": "D", "acts": [{"label": "A"}, {"label": "B"}],
                                    "persona": {"name": "Pal", "vibe": "x"}})
    assert bad["error"] == "invalid_brief"


# ── source map ──────────────────────────────────────────────────────────────

def test_sources_from_the_consent_manifest_do_not_warn():
    tid = _timeline()
    ents = [{**e, "sources": ["notes"]} for e in ENTS]
    assert not any("source_docs" in w
                   for w in srv.set_entities(tid, ents)["warnings"])
    r = srv.add_nodes(tid, [{"id": "c1", "act": 0, "tag": "Chapter",
                             "title": "Quay", "desc": "d", "sources": ["notes"]}])
    assert not any("source_docs" in w for w in r["warnings"]), r
    # A source that really is unknown still warns.
    r = srv.add_nodes(tid, [{"id": "c2", "act": 1, "tag": "Chapter",
                             "title": "Storm", "desc": "d", "sources": ["nope"]}])
    assert any("'nope'" in w for w in r["warnings"])


# ── organisation: lines follow their character ─────────────────────────────

def test_a_relation_that_follows_an_entity_takes_its_colour():
    from alto.build.builder import load_brief
    from alto.build.brief import validate_brief
    b, _, _ = load_brief({"brief": {**BRIEF, "entities": ENTS}})
    validate_brief(b)
    col = {e.id: e.color for e in b.entities}
    rel = {r.key: r.color for r in b.relations}
    assert rel["nell"] == col["nell"]            # key == entity id
    assert rel["ash-line"] == col["ash"]         # explicit `entity`
    assert rel["weather"] not in col.values()    # an ordinary relation


def test_an_explicit_relation_colour_wins():
    from alto.build.builder import load_brief
    from alto.build.brief import validate_brief
    rels = [{"key": "nell", "color": "#123456"}]
    b, _, _ = load_brief({"brief": {**BRIEF, "relations": rels, "entities": ENTS}})
    validate_brief(b)
    assert b.relations[0].color == "#123456"


def test_a_writing_project_autolinks_its_characters():
    tid = _timeline("writing")
    assert srv.get_timeline(tid)["brief"]["autolink"] == ["char", "env", "theme"]
    tid2 = _timeline("studying")
    assert "autolink" not in srv.get_timeline(tid2)["brief"]


# ── the rules travel with every install ─────────────────────────────────────

def test_the_package_carries_the_rules():
    assert (ROOT / "alto" / "firestore.rules").read_bytes() == \
        (ROOT / "firestore.rules").read_bytes()
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"firestore.rules"' in py
    mcpb = (ROOT / "packaging" / "build_mcpb.py").read_text(encoding="utf-8")
    assert '"firestore.rules")' in mcpb


def test_a_deploy_from_an_install_without_a_checkout_ships_the_rules(
        tmp_path, monkeypatch):
    """The bundle case: no repo root next to the package."""
    from alto import publish_static as ps
    monkeypatch.setattr(ps, "REPO", tmp_path / "no-checkout")
    log = tmp_path / "calls.json"
    fb = tmp_path / "firebase"
    fb.write_text(f"#!/bin/sh\n{sys.executable} -c 'import json,os,sys;"
                  f"json.dump({{\"argv\":sys.argv[1:],\"files\":os.listdir()}},"
                  f"open(\"{log}\",\"w\"))' \"$@\"\n")
    fb.chmod(fb.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ALTO_FIREBASE_BIN", str(fb))
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "my-alto")
    site = tmp_path / "store" / "_site"
    site.mkdir(parents=True)
    ps.deploy_site(site)
    calls = json.loads(log.read_text())
    assert "hosting:my-alto,firestore:rules" in calls["argv"]
    assert "firestore.rules" in calls["files"]
    cfg = json.loads((site.parent / "firebase.json").read_text())
    assert cfg["firestore"] == {"rules": "firestore.rules"}


def test_no_rules_at_all_refuses_to_deploy(tmp_path, monkeypatch):
    from alto import publish_static as ps
    monkeypatch.setattr(ps, "REPO", tmp_path)
    monkeypatch.setattr(ps, "__file__", str(tmp_path / "pkg" / "publish_static.py"))
    with pytest.raises(ps.PublishError, match="firestore.rules is missing"):
        ps.rules_path()
