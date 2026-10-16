"""Portals: gateways at stations to places off the map (palace.check_portals)."""
import pytest
from alto.build import palace
from alto.build.brief import BriefError


def test_a_portal_keeps_its_name_stations_and_line():
    out = palace.check_portals([{"name": " Airport ", "stations": ["Jefferson Station", " "], "line": "Regional Rail"}])
    assert out == [{"id": "portal1", "name": "Airport", "via": "", "line": "Regional Rail", "stations": ["Jefferson Station"],
                    "kind": "airport", "destinations": []}]


def test_an_airport_keeps_its_code_and_destinations():
    out = palace.check_portals([{"name": "Philadelphia International Airport", "code": "phl", "stations": ["30th Street Station"],
                                 "destinations": [{"city": "Boston", "code": "bos", "url": "../abc/"}, {"city": " "}, {"city": "Paris"}]}])
    assert out[0]["code"] == "PHL" and out[0]["kind"] == "airport"
    assert out[0]["destinations"] == [{"city": "Boston", "code": "BOS", "url": "../abc/"}, {"city": "Paris", "code": "CDG"}]


def test_default_destinations_skip_this_city_and_list_the_users_palaces_first():
    from alto.build.palace_airport import default_destinations
    d = default_destinations("Boston", [{"city": "Chicago", "code": "ORD", "url": "../k/"}])
    assert d[0]["city"] == "Chicago" and "url" in d[0]
    assert all(x["city"] != "Boston" for x in d) and sum(1 for x in d if x["city"] == "Chicago") == 1


@pytest.mark.parametrize("bad", [[{"stations": ["A"]}], [{"name": "X"}], ["nope"]])
def test_a_portal_needs_a_name_and_stations(bad):
    with pytest.raises(BriefError):
        palace.check_portals(bad)
