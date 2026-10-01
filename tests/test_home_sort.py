"""The order of the projects on the homepage: alphabetical, most recently
added, most recently viewed. The choice is kept on the account (so it follows
the user across devices); added/viewed times ride on each timeline's listing
record. The behaviour itself was exercised in Chromium and WebKit, desktop and
phone widths, against a stand-in account."""
from pathlib import Path

from alto.build import private_shell
from alto.cloud import SOURCE
from alto.engine import template as engine_template

ROOT = Path(__file__).resolve().parent.parent


def _home():
    return (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")


def test_the_homepage_sorts_private_projects_by_the_chosen_order():
    h = _home()
    assert "const SORT_KEY = 'alto-home-sort-v1'" in h
    assert "[['viewed', 'Recently viewed'], ['added', 'Recently added'], ['alpha', 'Alphabetical']]" in h
    assert "sortProjects(byProject(pages" in h
    # one quiet control, only worth showing when there is something to order
    assert "if(projects.length > 1) group.firstChild.appendChild(sortControl())" in h
    # a choice made elsewhere (another device or tab) redraws the list
    assert "window.addEventListener('alto-home-sort', redrawPrivate)" in h
    assert "e.key === SORT_KEY" in h


def test_the_choice_is_synced_on_the_account_newest_wins():
    js = SOURCE.read_text(encoding="utf-8")
    assert "const SORT_KEY = 'alto-home-sort-v1'" in js
    assert "k === SORT_KEY" in js                       # a local change triggers a sync
    assert "homeSort: ls.v, homeSortAt" in js           # pushed to users/{uid}
    assert "rs.t > (Number(ls.t) || 0)" in js           # a newer remote choice wins
    assert "new Event('alto-home-sort')" in js


def test_listing_records_carry_when_added_and_when_viewed():
    js = SOURCE.read_text(encoding="utf-8")
    assert "markViewed: async (key)" in js and "{ viewedAt: serverTimestamp() }" in js
    assert "added: Number(v.added) || 0" in js and "viewedAt: (v.viewedAt && v.viewedAt.seconds) || 0" in js


def test_the_private_shell_records_that_the_owner_opened_it():
    js = private_shell.shell()
    assert "AltoCloud.markViewed(KEY)" in js
