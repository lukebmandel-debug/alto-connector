"""Portals: gateways at stations to places off the map (palace.check_portals)."""
import pytest
from alto.build import palace
from alto.build.brief import BriefError


def test_a_portal_keeps_its_name_stations_and_line():
    out = palace.check_portals([{"name": " Airport ", "stations": ["Jefferson Station", " "], "line": "Regional Rail"}])
    assert out == [{"id": "portal1", "name": "Airport", "via": "", "line": "Regional Rail", "stations": ["Jefferson Station"]}]


@pytest.mark.parametrize("bad", [[{"stations": ["A"]}], [{"name": "X"}], ["nope"]])
def test_a_portal_needs_a_name_and_stations(bad):
    with pytest.raises(BriefError):
        palace.check_portals(bad)
