"""The FPV graphics pass (alto/build/fpv_gfx.py): the hosted CC0 assets, the shared FXG module in both first-person renderers, the quality ladder,
the site's headers and CSP. Source and file checks only (no browser); the WebKit frames are in tests/test_fpv_gfx_render.py."""
import json
import re
import struct

from alto import publish_static
from alto.build import fpv_gfx, palace_building_fpv, palace_ride, palace_ride_gfx, palace_ride_gl_shaders

M = fpv_gfx._manifest()
FILES = dict(fpv_gfx.files())


def test_every_hosted_file_is_content_hash_named_and_small():
    assert FILES, "alto/assets/gfx is empty"
    for name in FILES:
        assert fpv_gfx.NAME_RE.match(name), name
    assert sum(len(b) for b in FILES.values()) < 10e6                    # the whole set; a visit fetches only its tier's part


def test_the_manifest_names_files_that_are_published():
    paths = [M["basis"]["js"], M["basis"]["wasm"], M["meshopt"]] + list(M["env"]["px"].values())
    for t in M["tex"].values():
        paths += [t["a1024"], t["a512"], t["b512"]]
    paths += [d["glb"] for d in M["mdl"].values()]
    for p in paths:
        assert p.startswith("/gfx/") and p[5:] in FILES, p
    assert set(M["tex"]) >= {"kasota", "marble", "parquet", "boards", "terrazzo", "brick", "asphalt", "sidewalk"}
    assert set(M["mdl"]) == {"hydrant", "bin", "bench"}


def test_textures_are_ktx2_and_props_are_meshopt_glb():
    for name, b in FILES.items():
        if name.endswith(".ktx2"):
            assert b[:12] == b"\xabKTX 20\xbb\r\n\x1a\n", name
            assert struct.unpack("<I", b[40:44])[0] > 1, name + ": no mip levels"            # levelCount
        if name.endswith(".glb"):
            assert b[:4] == b"glTF"
            g = json.loads(b[20:20 + struct.unpack("<I", b[12:16])[0]])
            assert g["extensionsUsed"] == ["EXT_meshopt_compression"] and len(g["meshes"]) == 1


def test_the_sky_carries_its_sh_and_sun():
    e = M["env"]
    assert len(e["sh"]) == 9 and all(len(c) == 3 for c in e["sh"]) and set(e["px"]) == {"2048", "1024"}
    up = [e["sh"][0][c] * .282095 + e["sh"][2][c] * .488603 + e["sh"][6][c] * .315392 * 2 for c in range(3)]
    assert abs(up[0] * .2126 + up[1] * .7152 + up[2] * .0722 - 1) < .02                                    # normalised: the zenith's E/pi = 1


def test_both_renderers_embed_the_shared_module_and_nothing_reaches_a_page():
    ride = palace_ride.ride_asset()[1]
    for js in (palace_building_fpv.FPV_ASSET, ride):
        assert "var FXG=(function(){" in js and "X.post=function(gl)" in js and "__FXG_ASSETS__" not in js
    assert "FXG" not in palace_ride.RIDE_LOADER if hasattr(palace_ride, "RIDE_LOADER") else True
    assert "#ifdef IBL" in palace_building_fpv._GLSL_WORLD_FS and "#ifdef SOFTSH" in palace_building_fpv._GLSL_WORLD_FS
    assert "#ifdef GFX_IBL" in palace_ride_gl_shaders.SH_COMMON and "#ifdef GFX_REAL" in palace_ride_gl_shaders.FS_WORLD and "textureLod" not in palace_ride_gl_shaders.SH_COMMON


def test_the_quality_ladder():
    js = palace_building_fpv.FPV_ASSET
    m = re.search(r"var FX=\{high:\{([^}]*)\}, medium:\{([^}]*)\}, low:\{([^}]*)\}, off:\{([^}]*)\}\};", js)
    hi, med, low, off = (dict(kv.split(":") for kv in g.replace("'", "").split(", ")) for g in m.groups())
    assert hi["soft"] == "2" and hi["ao"] == "12" and hi["env"] == "2048" and hi["real"] == "a1024"
    assert med["soft"] == "1" and med["env"] == "1024" and med["real"] == "a512"
    assert low["ao"] == "0" and low["env"] == "" and low["real"] == "" and low["bloom"] == "0"            # the low tier fetches nothing
    assert all(v in ("0", "") for v in off.values())
    assert "if(name==='medium'&&o&&(o.mobile||o.ios)) f.ao=0;" in js and "else if(r==='floor') fxDown();" in js
    g = palace_ride_gfx.JS_GFX
    assert "if(t==='legacy'||gfxQ().palfx==='0'||typeof FXG==='undefined'||!FXG.env) return {ao:0, bloom:0, ibl:0, env:'', real:''};" in g
    assert "ao:ph?0:10" in g and "gfxFxSetup(gl)" in g


def test_headers_keep_gfx_files_a_year_and_the_csp_allows_wasm_only():
    csp = publish_static._csp("'none'")
    src = next(d for d in csp.split("; ") if d.startswith("script-src"))
    assert "'wasm-unsafe-eval'" in src and " 'unsafe-eval'" not in src
    names = sorted(FILES)
    rules = publish_static._gfx_rules(names)
    assert len(rules) == len(names) and all("immutable" in r["headers"][0]["value"] for r in rules)
    assert publish_static._gfx_rules(["../evil.js", "x.ktx2"]) == []
