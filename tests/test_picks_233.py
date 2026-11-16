"""v1.9.233 picks (Luke, Board B-1115-190321): the New dialog as tabs (B), Holo toggles as glass (S1), the terms text, the kept luke-alto hook,
the pubstamp retry. Static checks, no browser (the browser ones are tests/test_picks_233_browser.py)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _plain_pages():
    from alto.build import pages
    from alto.build.drive_picker_page import picker_js, picker_page
    return {"home": pages.build_home([]), "reports": pages.build_reports([], ""), "picker_js": picker_js(), "picker_page": picker_page()}


def test_plain_home_page_has_no_bass_word_at_all():
    for name, html in _plain_pages().items():
        assert not re.search(r"bass", html, re.I), (name, re.search(r".{40}bass.{40}", html, re.I | re.S))
    for f in ("alto/engine/home_template.html", "engine/home_template.html", "alto/cloud/alto-cloud.js"):
        assert not re.search(r"bass", (ROOT / f).read_text("utf-8"), re.I), f


def test_the_two_template_copies_are_identical():
    assert (ROOT / "alto/engine/home_template.html").read_bytes() == (ROOT / "engine/home_template.html").read_bytes()


def test_plain_new_dialog_is_two_tabs_claude_default_and_no_intro_line():
    h = _plain_pages()["home"]
    tabs = re.findall(r'<button type="button" class="nt-tab[^"]*" role="tab" data-tab="(\w+)"', h)
    assert tabs == ["claude", "self"]
    d = h[h.index('id="nt-modal"'):h.index('id="nt-cancel"')]
    assert "suggested route" not in d.lower() and "Suggested. Then make small" not in d and "Or start from a blank page" not in d
    assert 'id="nt-claude">Open Claude</button>' in h
    assert "document.querySelector('#nt-tabs .nt-tab[data-tab=\"' + (window._altoNtFirst || 'claude')" in h      # Claude unless an add-on names another first tab
    assert "@media (max-width:640px){ #nt-modal{ width:calc(100vw - 40px); max-width:none; } }" in h          # the phone dialog gutter is 20px


def test_bass_enters_the_dialog_only_through_the_bass_ui_anchors(monkeypatch):
    monkeypatch.setenv("ALTO_BASS_UI", "1")
    from alto.build import bass_ui, pages
    assert bass_ui.enabled()
    h = pages.build_home([])
    assert re.findall(r'class="nt-tab[^"]*" role="tab" data-tab="(\w+)"', h) == ["bass", "claude", "self"]
    assert 'id="nt-bass"' in h and "_altoNtFirst" in h


def test_hosted_hook_adds_the_bass_tab_in_front_and_the_pin_is_current():
    from alto.build import bass_hosted_ext as h
    b = h.bundle()
    assert "nt-tabs" in b and "_altoNtFirst='bass'" in b
    assert "Upload notes" in b and "Build it with Bass from my notes" not in b                    # the old "Build it with Bass from my notes" button is gone
    assert h.pin() == (ROOT / "alto/cloud/ext_pin.txt").read_text("utf-8").strip()


def test_terms_denied_text_has_no_bass_word():
    js = (ROOT / "alto/cloud/alto-cloud.js").read_text("utf-8")
    assert "This feature is invite-only during the beta, and this account isn't on the list." in js
    assert not re.search(r"bass", js, re.I)


def test_holo_s1_glass_plate_is_deep_and_covers_every_boxed_button():
    from alto.build import holo
    c = holo.css().replace("\n", "")
    for i in ("#search-btn", "#info-btn", "#account-btn", "#bin-btn", "#bg-toggle", "#download-all", "#tab-rail>button", ".alto-edit-pill", "#timeline-return-pill"):
        assert f"html.alto-holo {i}:not(#_):not(#__):not(#___):not(#____):not(#_____)" in c, i
    assert "radial-gradient(circle at 32% 24%,rgba(255,255,255,.14),transparent 55%),rgba(var(--ho-bgrgb),.86)" in c
    assert "right:20px" in c and "body > #bg-toggle" in c


def test_s1_is_holo_only():
    from alto.build import retro
    assert "rgba(var(--ho-bgrgb),.86)" not in retro.CHROME_CSS + retro.HOME_CSS


def _tree_pin():
    return (ROOT / "alto/cloud/ext_pin.txt").read_text("utf-8").strip()


def _env(**kw):
    base = {"ALTO_EXT_URL": "https://us-central1-demo-project.cloudfunctions.net/altoext"}
    base.update(kw)
    return base


def test_keep_hook_needs_the_explicit_flag_and_a_good_url_and_an_unchanged_bundle(tmp_path):
    from alto.cloud import ext_hook
    assert ext_hook.keep_url(_env()) == ""                                    # no flag: nothing
    assert ext_hook.keep_url(_env(ALTO_KEEP_HOOK="0")) == ""
    assert ext_hook.keep_url({"ALTO_KEEP_HOOK": "1"}) == ""                   # no URL
    assert ext_hook.keep_url(_env(ALTO_KEEP_HOOK="1", ALTO_EXT_URL="https://example.com/x")) == ""
    assert ext_hook.keep_url(_env(ALTO_KEEP_HOOK="1", ALTO_EXT_URL="https://us-central1-p.cloudfunctions.net/bassext")) == ""
    assert ext_hook.keep_url(_env(ALTO_KEEP_HOOK="1", ALTO_EXT_DEPLOYED_PIN_FILE=_rec(tmp_path, _tree_pin()))) == _env()["ALTO_EXT_URL"]


def _rec(tmp_path, text, name="rec.txt"):
    f = tmp_path / name
    f.write_text(text)
    return str(f)


OLD_PIN = "sha384-cL9lXV3Y8S/x7tVZuIhAgusYHior6FezgEwSH+Y6rcEwEipNLcJ+VglGsVjnvzmL 106301"          # what altoext served before 233


def test_keep_hook_record_must_list_the_tree_pin(tmp_path):
    from alto.cloud import ext_hook
    url = _env()["ALTO_EXT_URL"]
    k = lambda rec: ext_hook.keep_url({"ALTO_KEEP_HOOK": "1", "ALTO_EXT_URL": url, "ALTO_EXT_DEPLOYED_PIN_FILE": rec})
    assert k(_rec(tmp_path, OLD_PIN + "\n")) == ""                                      # (1) the tree pin is not in the record: the function still serves the old bundle
    assert k(_rec(tmp_path, OLD_PIN + "\n" + _tree_pin() + "\n")) == url               # (2) it is in the record: attached
    assert k(str(tmp_path / "nope.txt")) == ""                                         # (3) no record file
    assert k(str(ROOT / "alto/cloud/ext_pin.txt")) == ""                               # (4) a record inside the repo is refused, even one that names the tree pin
    inside = ROOT / "tests" / "_rec_inside_233.txt"
    try:
        inside.write_text(_tree_pin() + "\n")
        assert k(str(inside)) == ""
        assert k(str(ROOT / "tests" / ".." / "tests" / "_rec_inside_233.txt")) == ""                  # (a path that only resolves inside)
    finally:
        inside.unlink()


def test_keep_hook_tool_exit_codes(tmp_path, monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("keep_hook", ROOT / "tools/keep_hook.py")
    kh = importlib.util.module_from_spec(spec); spec.loader.exec_module(kh)
    url = _env()["ALTO_EXT_URL"]
    for rec, want in ((_rec(tmp_path, OLD_PIN, "old.txt"), 2), (str(tmp_path / "none"), 2), (str(ROOT / "alto/cloud/ext_pin.txt"), 2), (_rec(tmp_path, _tree_pin(), "new.txt"), 0)):
        monkeypatch.setenv("ALTO_KEEP_HOOK", "1"); monkeypatch.setenv("ALTO_EXT_URL", url); monkeypatch.setenv("ALTO_EXT_DEPLOYED_PIN_FILE", rec)
        assert kh.main() == want
    assert "export ALTO_EXT_URL=" + url in capsys.readouterr().out


def test_the_default_record_path_is_outside_the_repo():
    from alto.cloud import ext_hook
    from pathlib import Path as P
    d = P(ext_hook.DEFAULT_DEPLOYED_PIN_FILE).expanduser().resolve()
    assert ROOT not in d.parents and d.name == "altoext-deployed-pin.txt"


def test_keep_hook_refuses_when_the_served_bundle_no_longer_has_the_pin(monkeypatch, tmp_path):
    from alto.build import bass_hosted_ext
    from alto.cloud import ext_hook
    monkeypatch.setattr(bass_hosted_ext, "bundle", lambda: "changed")
    assert ext_hook.keep_url(_env(ALTO_KEEP_HOOK="1", ALTO_EXT_DEPLOYED_PIN_FILE=_rec(tmp_path, _tree_pin()))) == ""


def test_keep_hook_reads_no_network_and_no_firestore():
    for f in ("alto/cloud/ext_hook.py", "tools/keep_hook.py"):
        imports = "\n".join(l for l in (ROOT / f).read_text("utf-8").splitlines() if re.match(r"\s*(import|from) ", l))
        assert not re.search(r"firestore|firebase|urllib|requests|socket|http|google|store", imports, re.I), (f, imports)


def test_the_default_build_and_the_connector_carry_no_hook_and_no_bass(monkeypatch):
    for k in ("ALTO_EXT_URL", "ALTO_KEEP_HOOK", "ALTO_BASS_UI", "ALTO_BASS_BASE"):
        monkeypatch.delenv(k, raising=False)
    from alto.cloud import ext_hook
    src = "var x=1;"
    assert ext_hook.append(src) == src                                        # ALTO_KEEP_HOOK alone, or nothing, adds nothing
    monkeypatch.setenv("ALTO_KEEP_HOOK", "1")
    assert ext_hook.append(src) == src and ext_hook.origin() == ""
    js = (ROOT / "alto/cloud/alto-cloud.js").read_text("utf-8")
    assert "alto-ext" not in js and not re.search(r"bass", js, re.I)


def test_publish_retry_after_live_mismatch_deploys_again(tmp_path, monkeypatch):
    from alto import publish_static as ps
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>a</p>")
    monkeypatch.setattr(ps, "firebase_configured", lambda: ("fb", "s", "p"))
    monkeypatch.setattr(ps, "rules_path", lambda: ROOT / "alto/firestore.rules")
    calls = []

    def fake_deploy(d):
        calls.append(1)
        ps._marker(d).unlink() if ps._marker(d).exists() else None          # (what the real deploy_site does first)
        return "https://s.web.app"
    monkeypatch.setattr(ps, "deploy_site", fake_deploy)
    live, deployed = ps.deploy_if_changed(site)
    assert deployed and not ps._marker(site).exists()                         # a deploy alone records nothing
    # the live check found a mismatch: the publish returns an error WITHOUT mark_deployed; the re-run must deploy again
    live, deployed = ps.deploy_if_changed(site)
    assert deployed and len(calls) == 2
    ps.mark_deployed(site)                                                    # the check passed
    live, deployed = ps.deploy_if_changed(site)
    assert not deployed and len(calls) == 2                                   # now it can skip


def test_every_direct_deploy_clears_the_marker(tmp_path, monkeypatch):
    from alto import publish_static as ps
    src = (ROOT / "alto/publish_static.py").read_text("utf-8")
    body = src[src.index("def deploy_site"):src.index("rules_src = rules_path()")]
    assert "_marker(site_dir).unlink()" in body
    mc = (ROOT / "alto/mcp_server.py").read_text("utf-8")
    assert mc.index("mark_deployed(site)") > mc.index('"error": "live_mismatch"')       # written only after the mismatch return
