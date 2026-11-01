"""The interview guide's section S (offer what fits the student's goal) and the plain-word Flow 1 lines (single source for the Claude interview)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")


def _section() -> str:
    start = GUIDE.index("### S. Offer what fits their goal")
    end = GUIDE.index("### §D-Palace.", start)
    return GUIDE[start:end]


def _flat(s: str) -> str:
    return " ".join(s.replace("> ", " ").split())


def test_section_s_sits_after_the_shape_question_and_before_the_format_sections():
    assert GUIDE.index("### B0. Which shape?") < GUIDE.index("### S. Offer what fits their goal") < GUIDE.index("### §D-Palace.")
    assert GUIDE.count("### S. Offer what fits their goal") == 1


def test_the_opening_question_is_skipped_only_when_the_notes_give_both_goal_and_study_style():
    s = _section()
    assert "What is this for, and how do you like to study?" in s
    assert "Skip it ONLY when" in s and "BOTH what the work is for AND how they like to study" in s
    assert "still ask how they like to study" in s
    assert "with no menu of study methods" in s


def test_it_offers_the_four_kinds_tailored_capped_and_only_where_the_notes_support_it():
    s = _section()
    assert "at most three things per round" in s
    for kind in ("a quiz", "flash cards", "a decision tree", "a mini timeline"):
        assert kind in s
    assert "Do you have practice questions I should base it on?" in s
    assert "A no is final for that kind" in s
    assert "Do not announce a later offer in advance" in s
    assert "ends in a question mark" in s and 'Never write "I\'ll write/add/make ..." about an extra before they say yes' in s
    assert "ask the missing half first and do not offer yet" in s
    assert "Never reclassify, regroup or relabel anything the student named" in s
    assert "A direct invitation" in s and "Never answer it with a refusal" in s
    assert "40 words or fewer" in s
    assert "A stated habit IS the study style" in s
    assert "if you have none, I'll write them only from your notes" in s
    assert "ask ONE question per message, never two" in s
    assert "indentation or numbering" in s and "Where would you break this up, if anywhere?" in s
    assert "at least two parts" in s


def test_everyday_words_and_the_closed_system_still_stand():
    s = _section()
    assert "Everyday words only" in s and '"hub"' in s and '"chips"' in s
    assert "Section 0 stands" in s and "only from their materials" in s
    assert "never add a concept that is not in their materials" in s and "THEIR call" in s


def test_the_flow_one_lines_the_student_reads_use_plain_words():
    f = _flat(GUIDE)
    assert "Speak to the student in everyday words" in f and "about 60 words" in f
    assert "One thing about how Alto works: I build **only** from what you give me." in f
    assert "Which do you want, either or both?" in f
    assert "Two ways to lay this out." in f and "radiating out" not in f and "Cases attach to concepts as chips" not in f
    assert "Which do you want?" in f and "tiny satellites" not in f
    assert "Under '<their main concept>', what are its sub-concepts?" in f and "Under '<their hub>'" not in f


def test_the_section_stays_compact():
    assert len(_section()) < 7500
