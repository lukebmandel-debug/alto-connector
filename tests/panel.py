"""Read the Filter panel's data back out of a built page."""
import json


def sections(html):
    if "var FILTER_SECTIONS=" not in html:
        return []
    raw = html.split("var FILTER_SECTIONS=", 1)[1].split(";\nvar FILTER_NODES=", 1)[0]
    return json.loads(raw)


def nodes(html):
    if "var FILTER_NODES=" not in html:
        return {}
    raw = html.split("var FILTER_NODES=", 1)[1].split(";", 1)[0]
    return json.loads(raw)


def item_ids(html, key):
    for s in sections(html):
        if s["key"] == key:
            return [i["id"] for i in s["items"]]
    return []


def slot_ids(html, slot):
    return item_ids(html, "slot-" + slot)
