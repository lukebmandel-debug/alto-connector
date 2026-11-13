"""alto-bass-parity: the shape texts (System, Atlas, Blueprint), the plain 'cannot yet' lines, and where each rides (mock only)."""
import sys
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bass_apidoc as D
from alto import mcp_server as srv
from alto.bass import actions as A
from alto.bass import engine as E
from alto.bass import mock_anthropic as M
from alto.bass import shapes as S


@pytest.fixture
def env(tmp_path):
    e = D.make_env(tmp_path / "store")
    yield e
    srv.set_store(None)


def _text(env, i=0):
    c = env.mock.message_requests[i]["body"]["messages"][0]["content"]
    return c if isinstance(c, str) else "\n".join(b.get("text", "") for b in c if isinstance(b, dict))


def test_the_sections_say_what_the_guide_says_and_stay_short():
    assert "'outline'" in S.SYSTEM and "'solar'" in S.SYSTEM and "fifth level" in S.SYSTEM and "never name a concept the student did not say" in S.SYSTEM
    assert "palace_view 'world'" in S.ATLAS and "set_up_world" in S.ATLAS and "never guess a place" in S.ATLAS and "nothing is fetched" in S.ATLAS
    assert "Philadelphia Museum of Art" in S.BLUEPRINT and "building 'pma'" in S.BLUEPRINT and "Never draw" in S.BLUEPRINT
    assert all(len(t) < 1300 for t in S.SECTIONS.values()) and len(S.MENU) < 1800 and len(S.edit_text()) < 3500


def test_every_cannot_yet_line_points_to_their_own_claude_account_and_offers_the_ordinary_build():
    for t in (S.MENU, S.PLAIN_LINE, S.BLUEPRINT):
        assert "Claude account" in t and ("ordinary outline" in t)
    assert "not a question" in S.MENU and "never as a question" in S.PLAIN_LINE and "only once" in S.BLUEPRINT
    assert "new city" in S.MENU and "pre-built" in S.MENU and "any other building" in S.MENU
    assert "city (new or pre-built)" in S.PLAIN_LINE and "Philadelphia Museum of Art" in S.PLAIN_LINE
    assert S.PLAIN_LINE in E.SYSTEM_PROMPT


def test_the_propose_schema_carries_the_optional_shape_and_the_menu_rides_on_propose_only(env):
    props = A.PROPOSE_SCHEMA["properties"]
    assert props["shape"]["enum"] == ["system", "atlas", "blueprint"] and "shape" not in A.PROPOSE_SCHEMA["required"]
    env.mock.use(M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]))
    env.acts.dispatch("student", {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert S.MENU in _text(env)


@pytest.mark.parametrize("shape", S.SHAPES)
def test_a_confirmed_shape_loads_only_its_own_section_into_the_build(env, shape):
    chips = dict(D.CHIPS, shape=shape)
    env.mock.use(M.propose_chips())
    env.acts.dispatch("student", {"action": "build", "args": {"chips": chips, "materials": D.MATERIALS, "consent": True, "accepted": True}})
    t = _text(env)
    assert S.SECTIONS[shape] in t and all(S.SECTIONS[o] not in t for o in S.SHAPES if o != shape)


def test_no_shape_or_an_unknown_one_adds_nothing(env):
    for chips in (D.CHIPS, dict(D.CHIPS, shape="palace")):
        env.mock.use(M.propose_chips())
        n = len(env.mock.message_requests)
        env.acts.dispatch("student", {"action": "build", "args": {"chips": chips, "materials": D.MATERIALS, "consent": True, "accepted": True}})
        t = _text(env, n)
        assert not any(S.SECTIONS[k] in t for k in S.SHAPES)


def test_the_edit_chat_carries_the_menu_and_all_three_sections_on_its_first_turn_only(env):
    env.mock.use(M.Scenario("e", [M.Step(M.Reply([M.text("Done.")]))]))
    env.acts.dispatch("student", {"action": "edit", "args": {"timeline_id": "t1", "text": "show it as a System"}})
    t = _text(env)
    assert S.MENU in t and all(S.SECTIONS[k] in t for k in S.SHAPES)
