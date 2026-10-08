"""A private page is shown by a shell that is the same for every timeline, so
alto-cloud.js cannot read the timeline id from its own script tag. Before the
shell named it (setTid), TID was null and highlights + notes never left the
device that made them."""
from alto.build import private_shell
from alto.cloud import SOURCE


def test_shell_names_the_timeline_before_writing_the_page():
    js = private_shell.shell()
    i = js.index("AltoCloud.setTid")
    assert "COURSE_ID" in js[i - 300:i]
    assert i < js.index("document.open();\n      document.write(")


def test_cloud_layer_can_be_told_its_timeline():
    src = SOURCE.read_text(encoding="utf-8")
    assert "let TID" in src and "setTid:" in src
    assert "function subscribeTl" in src
    assert src.count("subscribeTl(") >= 3      # definition + sign-in + setTid
