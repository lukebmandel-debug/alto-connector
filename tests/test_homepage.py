"""Homepage course tiles: full rainbow strips + domain-appropriate period label."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import Brief, Act, period_words  # noqa: E402
from alto.build.pages import course_entry_for  # noqa: E402


def test_missing_act_colors_fill_rainbow():
    # acts authored without colors (the common case — colors are assigned at
    # build, not stored) must still yield a full, non-empty rainbow.
    b = Brief(title="Civ Pro", acts=[Act(label="PJ"), Act(label="Erie"),
                                     Act(label="Pleading")])
    entry = course_entry_for(b, kind="studying", href="/t/x/")
    assert len(entry["units"]) == 3
    assert all(u and u.startswith("#") for u in entry["units"])


def test_explicit_act_colors_preserved():
    b = Brief(title="X", acts=[Act(label="A", color="#123456"), Act(label="B")])
    units = course_entry_for(b, href="/t/x/")["units"]
    assert units[0] == "#123456"
    assert units[1] and units[1] != "#123456"


def test_period_words_by_kind_and_override():
    assert period_words("studying", "") == ("Unit", "Units")
    assert period_words("writing", "") == ("Act", "Acts")
    assert period_words("research", "") == ("Phase", "Phases")
    assert period_words("", "") == ("Unit", "Units")          # default
    assert period_words("studying", "Era") == ("Era", "Eras")  # override wins


def test_course_sub_uses_period_noun():
    course = Brief(title="Civ Pro", acts=[Act(label="a"), Act(label="b")])
    assert course_entry_for(course, kind="studying", href="/t/x/")["sub"] == "2 units"
    novel = Brief(title="Novel", acts=[Act(label="one")])
    assert course_entry_for(novel, kind="writing", href="/t/y/")["sub"] == "1 act"
    hist = Brief(title="Rome", acts=[Act(label="a"), Act(label="b"), Act(label="c")],
                 period_noun="Era")
    assert course_entry_for(hist, href="/t/z/")["sub"] == "3 eras"
