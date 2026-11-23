"""A local, test-only fixture shaped like Luke's Torts outline top bar (round 3 of v1.9.273): an Element group of nine kind-glyph chips with counts, an Authorities group (the Cases
index chip) and the outline title tab. Built from samples/outline_brief.json only; never a real account's data."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ["Intent", "Contact / Invasion", "Causation", "Consent", "Duty", "Breach", "Damages", "Foreseeability", "Standard of Care"]
_SHAPES = ['<circle cx="12" cy="12" r="4"/>', '<path d="M6 6l12 12M18 6L6 18"/>', '<path d="M5 12h14M13 6l6 6-6 6"/>', '<path d="M5 13l4 4 10-10"/>', '<path d="M12 3l8 5v8l-8 5-8-5V8z"/>',
           '<path d="M6 4l5 8-4 8"/>', '<path d="M12 3v18M16 7H10a3 3 0 000 6h4a3 3 0 010 6H8"/>', '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="2"/>',
           '<rect x="3" y="9" width="18" height="6" rx="2"/>']


LONG = "The extraordinarily long name of a doctrine that no phone could ever show in one line"


def brief(title="Torts", long_names=False):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b = d["brief"]
    b["title"] = title
    b["entity_axis_singular"] = "Element"
    b["entity_axis_label"] = "Elements"
    b["index_label"] = "Authorities"
    ents = []
    for i, k in enumerate(KINDS):
        ents.append({"id": "k%d" % i, "name": k, "role": k, "color": "#4de8d8",
                     "symbol_svg": '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">%s</svg>' % _SHAPES[i]})
    b["entities"] = ents
    for j, n in enumerate(d["nodes"]):
        n["entity_ids"] = ["k%d" % (j % 9), "k%d" % ((j * 3 + 1) % 9)]
    if long_names:
        d["nodes"][1]["title"] = LONG
        d["nodes"][-1]["title"] = LONG + " too"
    return copy.deepcopy(d)


def page(title="Torts", long_names=False, data=None):
    from alto.build.builder import build_timeline, load_brief
    from alto.build import palace_assets
    import phone_matrix as pm
    html = build_timeline(*load_brief(data or brief(title, long_names)))[0]
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    i = html.rfind("</body>")
    html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
    j = html.find('<script id="alto-shell-js">')
    return html[:j] + pm.SEED + html[j:] if j >= 0 else html


# ---- a Negligence unit (round "row subtrees"): six branches in one row band, each with sub-cards ----
# Neutral invented names; a copy shaped like the Torts negligence unit, never a real account's data.
_BRANCHES = {   # branch -> {sub-card: [leaf outcomes]}, Defenses the deepest
    "duty": {"General rule": ["Duty owed", "No duty"], "Special relationships": ["Duty owed", "No duty"],
             "Rescuers": ["Duty owed", "No duty"]},
    "breach": {"Reasonable person": ["Breach", "No breach"], "Custom": ["Breach", "No breach"],
               "Negligence per se": ["Breach", "No breach"]},
    "fact": {"But-for test": ["Cause", "No cause"], "Substantial factor": ["Cause", "No cause"],
             "Alternative liability": ["Cause", "No cause"]},
    "proximate": {"Foreseeable harm": ["Proximate", "Not proximate"],
                  "Intervening acts": ["Proximate", "Not proximate"]},
    "damages": {"Compensatory": [], "Punitive": []},
    "defenses": {"Contributory fault": ["Barred", "Not barred"], "Comparative fault": ["Reduced", "Not reduced"],
                 "Assumption of risk": ["Barred", "Not barred"], "Immunities": ["Immune", "Not immune"],
                 "Statutes of limitation": ["Barred", "Not barred"]},
}
_BRANCH_TITLES = {"duty": "Duty", "breach": "Breach", "fact": "Cause in Fact", "proximate": "Proximate Cause",
                  "damages": "Damages", "defenses": "Defenses"}


def negligence_brief(child_w=190, nested=("breach", "defenses")):
    """One unit, Negligence: a hub with six branches in a row band (child_w wide), each branch with
    sub-cards; the ones named in `nested` are rows of their own (the case that used to stack)."""
    d = brief("Torts")
    b = d["brief"]
    b["acts"] = [{"label": "UNIT ONE - NEGLIGENCE", "short": "Unit 1 - Negligence"},
                 {"label": "UNIT TWO - STRICT LIABILITY", "short": "Unit 2 - Strict liability"}]
    b["axes"], b["relations"], b["filters"], d["connections"] = [], [], [], []
    b["overview_html"] = "<p>Negligence, a test copy.</p>"
    place = {"negligence": {"arrange": "row", "child_w": child_w}}
    nodes = [{"id": "negligence", "act": 0, "tag": "Negligence", "title": "Negligence", "desc": "The hub.",
              "entity_ids": ["k0"], "axis1_values": [], "sections": []}]

    def add(i, parent, title, tag):
        nodes.append({"id": i, "act": 0, "tag": tag, "title": title, "desc": "A short note on " + title.lower() + ".",
                      "entity_ids": ["k%d" % (len(nodes) % 9)], "axis1_values": [], "sections": [], "parent": parent})
    for br, subs in _BRANCHES.items():
        add(br, "negligence", _BRANCH_TITLES[br], "Negligence")
        if br in nested:
            place[br] = {"arrange": "row"}
        for s, outs in subs.items():
            sid = br + "-" + s.lower().replace(" ", "-")
            add(sid, br, s, "Negligence")
            for o in outs:
                add(sid + "-" + o.lower().replace(" ", "-"), sid, o, "Outcome")
    nodes.append({"id": "strict", "act": 1, "tag": "Strict", "title": "Strict liability", "desc": "A second unit.",
                  "entity_ids": ["k2"], "axis1_values": [], "sections": []})
    for i in ("Animals", "Abnormally dangerous activities", "Products"):
        add("strict-" + i.split()[0].lower(), "strict", i, "Strict")
        nodes[-1]["act"] = 1
    d["nodes"] = nodes
    b["placement"] = place
    return d
