"""A civ-pro-litigation-sized horizontal timeline (275 cards, made up): 7 units, 20 events, every other card nested under an event, up to 3 deep."""
import json, random
def brief(extend=True):
    r = random.Random(7)
    stages = ["Before suit", "Pleading", "Joinder", "Discovery", "Pretrial", "Trial", "After judgment"]
    words = "court party claim motion rule notice service answer default amend join discover depose produce compel summary jury verdict appeal preclude".split()
    def txt(n): return " ".join(r.choice(words) for _ in range(n)).capitalize() + "."
    acts = [{"label": f"Part {i+1} — {s}", "short": s} for i, s in enumerate(stages)]
    nodes, per = [], [3, 3, 3, 3, 3, 3, 2]
    ev = 0
    kids_left = 275 - 20
    for a, k in enumerate(per):
        for j in range(k):
            eid = f"ev{ev}"
            nodes.append({"id": eid, "act": a, "tag": "Event", "title": f"Event {ev+1}: {txt(3)[:-1]}", "desc": txt(r.randint(8, 22))})
            n = kids_left // (20 - ev) if ev < 19 else kids_left
            kids_left -= n
            pool = [eid]
            for c in range(n):
                p = r.choice(pool[:1] * 3 + pool) if len(pool) > 1 else eid
                cid = f"{eid}-c{c}"
                nodes.append({"id": cid, "act": a, "nest": p, "tag": r.choice(["Rule", "Doctrine", "Case", "Test"]),
                              "title": f"{ev+1}.{c+1} {txt(r.randint(2, 6))[:-1]}", "desc": txt(r.randint(6, 30))})
                depth = 1; q = p
                while q != eid: q = next(x["nest"] for x in nodes if x["id"] == q); depth += 1
                if depth < 3: pool.append(cid)
            ev += 1
    b = {"title": "The Lawsuit (print test)", "subject": "Made-up sample", "mode": "lanes", "columns": 3, "node_noun": "Event",
         "period_noun": "Part", "entity_axis_label": "People", "entity_axis_singular": "Person", "main_line": "The lawsuit",
         "lines": [], "flashbacks": [], "acts": acts, "timeline_id": "lanes-print-275"}
    if extend: b["extend"] = True
    return {"brief": b, "nodes": nodes, "connections": []}
if __name__ == "__main__":
    d = brief(); print(len(d["nodes"]))
