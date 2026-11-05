"""Makes alto/assets/flags/flags.json.gz (the Memory Atlas's country flags) from the flag-icons package (MIT; github.com/lipis/flag-icons).

    python docs/world-palace/build_world_flags.py <dir of the unpacked flag-icons npm package>   (flag-icons-7.2.3: its flags/4x3/*.svg)

One minified SVG per country the gazetteer places, keyed by its ISO3; the countries in world_flags.NEUTRAL (Antarctica, disputed or sovereign-less
areas, territories whose ISO code is another state's) get no flag at all: the page draws its neutral pennant for them.
"""
import gzip, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from alto.build import world_flags                     # noqa: E402
from alto.build.world_geo import gazetteer             # noqa: E402


def minify(svg: str) -> str:
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"\s+id=\"flag-icons-[a-z-]+\"", "", svg, count=1)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r">\s+<", "><", svg).strip()
    return re.sub(r"\s{2,}", " ", svg)


def main(src: str) -> None:
    d = os.path.join(src, "flags", "4x3")
    out = {}
    for iso3, c in sorted(gazetteer()["countries"].items()):
        if iso3 in world_flags.NEUTRAL or not c.get("iso2"):
            continue
        with open(os.path.join(d, c["iso2"].lower() + ".svg"), encoding="utf-8") as f:
            out[iso3] = minify(f.read())
    path = os.path.join(world_flags.DIR, "flags.json.gz")
    with gzip.GzipFile(path, "wb", mtime=0) as f:
        f.write(json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    print(len(out), "flags,", sum(len(v) for v in out.values()), "bytes of SVG,", os.path.getsize(path), "bytes packed")


if __name__ == "__main__":
    main(sys.argv[1])
