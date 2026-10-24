"""The avatar module (alto/build/fpv_avatar.py) in the Museum Palace's first-person view: the mayor table, the hop and the T switch are embedded.
The city palace's half of this file (its roam on a synthetic city) went to cold storage with the city's first-person view
(_cold-storage/memory-map-fpv/shared-at-v1.9.163/tests/test_fpv_avatar_view.py); the Museum's browser checks are in test_fpv_avatar_museum.py."""
from alto.build import palace_building_fpv


def test_the_museum_view_carries_the_avatar_and_the_hop():
    js = palace_building_fpv.FPV_ASSET
    assert "var AV=(function(){" in js and "__AV_TABLE__" not in js and "Cherelle Parker" in js and "Zohran Mamdani" in js
    assert "HOP={v0:3.3, g:13.5, coyote:.1, buffer:.13}" in js
    assert "k===' '||c==='Space') n='hop'" in palace_building_fpv.FPV_ASSET and "(k==='t'||k==='T')" in palace_building_fpv.FPV_ASSET
