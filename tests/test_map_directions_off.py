"""Memory Map: Directions (route planning, its zoom-row button, the phone's Directions buttons and the hint sentences) is off behind one flag
(palace_directions.DIRECTIONS_ON; Luke 2026-11-26: "temporarily take out transit directions/look up navigation features"). The train stations and
the airport scene are untouched. No browser."""
from alto.build import info_help, palace_directions, palace_mobile


def test_directions_is_off_behind_one_flag_and_everything_else_stays():
    assert palace_directions.DIRECTIONS_ON is False
    assert palace_directions.DIR_JS.startswith("var DIRECTIONS_ON=false;")
    assert "window._palDirMount=function(c){ if(!DIRECTIONS_ON ||" in palace_directions.DIR_JS     # (no button in the zoom row)
    mob = palace_mobile.MOBILE_JS
    assert "(DIRECTIONS_ON?'<button type=\"button\" class=\"pm-act pri\" data-a=\"dir\">'" in mob      # (no Directions action on a place card)
    assert "(DIRECTIONS_ON?'<button type=\"button\" class=\"pm-btn\" data-a=\"dir\"" in mob            # (none beside the phone's search)
    assert "Directions" not in info_help._BODY_D["palace"] and "Directions" not in info_help._BODY_M["palace"]
    assert "pmResults" in mob and "DIR.search" in mob                                                    # (the phone's search of the city stays)
    assert "DIR.open" in palace_directions.DIR_JS or "open:function" in palace_directions.DIR_JS          # (the engine is still in the tree)
