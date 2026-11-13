"""The Bass copy of the interview guide's shape sections (System, Memory Atlas, Memory Blueprint) and the plain lines for what Bass cannot
build yet. Text only: the tools (set_up_world, set_up_building for 'pma') live in tools.py. Honed by Strategy against ORG/notes-interview/
BASS-SHAPES-DRAFT.md, which this file must equal word for word (tests/test_bass_shapes.py pins the lengths and the key phrases)."""
from __future__ import annotations

SHAPES = ("system", "atlas", "blueprint")

MENU = (
    "Shapes. Besides the usual timeline or outline, Bass can draw an outline as a System (each unit's main concept a sun, its concepts "
    "planets, theirs moons and satellites), place it on the world map as a Memory Atlas, or walk it through the Philadelphia Museum of Art "
    "as a Memory Blueprint. Offer one only as one of your at-most-three offers, as a question with its reason in the same sentence, when "
    "the student's notes or words fit it: a System needs an outline with one main concept per unit; an Atlas needs "
    "places their notes name; the Blueprint is only the Philadelphia Museum of Art. Set `shape` in the plan to what they said yes to "
    "(\"system\", \"atlas\" or \"blueprint\"); otherwise leave it out. When the student likes diagrams or pictures and their notes have a "
    "main concept per unit, the System is your first offer, before a quiz or a plan. Never show a finished outline built from their notes: "
    "ask for their units or main concepts and echo back only what they named.\n"
    "What Bass cannot do yet: a Memory Palace of a city (a new city or a pre-built one), a Memory Blueprint of any other building, a "
    "first-person walk. If the student asks for one, say so in one or two plain sentences and say it needs their own Claude account. The "
    "first time, add as a plain statement, not a question, that you can build the ordinary outline or timeline here; ask no question in that answer (not even the opening question, which waits until they are back on their notes), and do "
    "not repeat that statement if they ask for another of these."
)

SYSTEM = (
    "System. Draw this outline as a System: the timeline's mode is 'outline' and its layout is 'solar'. A unit's top concept (no parent) is a "
    "sun, its children planets, theirs moons, one level deeper satellites; nothing goes deeper. If a concept would sit at a fifth level, do "
    "not flatten or move it yourself: name it and ask whether to move it up or cut it. A unit has several top concepts only when the student's "
    "notes treat them as equals; never make one up or merge two. The planets' order is the outline's order, so do not place cards by "
    "position. The structure is the student's own headings in their order; if the notes show no units or main concepts, ask one short "
    "question for them, and never name a concept the student did not say."
)

ATLAS = (
    "Memory Atlas. Create the timeline with mode 'palace' and palace_view 'world': one unit per region, each main concept a country. When "
    "the cards exist, call set_up_world once. Pass `places` only for a card whose place the student's notes name (a case decided in "
    "Oregon) or that the student asked for; never guess a place from the subject. Every other card follows the built-in route. The map is "
    "Alto's own, nothing is fetched, nothing is drawn for the student. Say plainly which cards you placed and which follow the route."
)

BLUEPRINT = (
    "Memory Blueprint. Only the Philadelphia Museum of Art (Main Building) is available. Create the timeline with mode 'palace' and "
    "palace_view 'building', add the cards, then call set_up_building once with building 'pma'; the cards go into its rooms. Never draw, "
    "accept or offer a plan for any other building. If the student wants another building, say plainly that Bass cannot yet and that it "
    "needs their own Claude account; mention the ordinary outline here only once in the conversation, as a statement."
)

SECTIONS = {"system": SYSTEM, "atlas": ATLAS, "blueprint": BLUEPRINT}

# Always in force (engine SYSTEM_PROMPT): a request Bass cannot meet gets a plain answer, never silence or a blank page.
PLAIN_LINE = (
    "- Bass cannot yet build a Memory Palace of a city (new or pre-built), a Memory Blueprint of any building but the Philadelphia Museum of "
    "Art, or a first-person walk. If asked, say so in one or two plain sentences and say it needs their own Claude account. Mention the "
    "ordinary outline or timeline here once in the conversation, as a statement, never as a question, and never repeat it. Ask no question in that answer; the opening question waits until the student is back on their notes."
)


def section(shape) -> str:
    return SECTIONS.get(shape if isinstance(shape, str) else "", "")


def edit_text() -> str:
    """The edit chat carries the menu and all three sections (Haiku; about 900 tokens, cached with the conversation)."""
    return MENU + "\n\n" + "\n\n".join(SECTIONS[k] for k in SHAPES)
