"""CLI: python -m alto.build <brief.json> [out.html]"""
import json
import sys
from pathlib import Path

from .builder import build_from_file
from .verify import VerifyError


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: python -m alto.build <brief.json> [out.html] [--bundle]")
    src = args[0]
    out = Path(args[1]) if len(args) > 1 else Path(src).with_suffix(".built.html")
    try:
        html, report = build_from_file(src)
    except VerifyError as e:
        print("BUILD FAILED:")
        for f in e.failures:
            print(f"  - {f}")
        sys.exit(1)
    out.write_text(html, encoding="utf-8")
    print(json.dumps(report, indent=1))
    print(f"wrote {out} ({report['bytes']:,} bytes)")

    if "--bundle" in sys.argv:
        from .builder import load_brief
        from .single_file import bundle
        d = json.loads(Path(src).read_text(encoding="utf-8"))
        brief, _, _ = load_brief(d)
        offline = bundle(brief, html)
        bout = Path(src).with_suffix(".offline.html")
        bout.write_text(offline, encoding="utf-8")
        print(f"wrote {bout} ({len(offline.encode('utf-8')):,} bytes)")


if __name__ == "__main__":
    main()
