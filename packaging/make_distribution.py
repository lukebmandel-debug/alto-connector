#!/usr/bin/env python3
"""Generate everything the public distribution needs, from identity.json.

Emits:
  server.json          the MCP Registry entry (repo root)
  packaging/site/      the download page, ready for `firebase deploy`

Run after building the bundles so file sizes and checksums are real:

    python packaging/build_mcpb.py
    python packaging/make_distribution.py

Refuses to run while identity.json still holds PLACEHOLDER values — a wrong
URL on a download page is worse than no page.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the tick and arrow
# characters this script prints — that is a crash, not a cosmetic problem.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.mcp_server import __version__  # noqa: E402

IDENTITY = ROOT / "packaging" / "identity.json"
DIST = ROOT / "packaging" / "dist"
SITE = ROOT / "packaging" / "site"

PLATFORM_LABELS = {
    "macos-arm64": ("macOS", "Apple Silicon — M1 and later"),
    "macos-x64": ("macOS", "Intel"),
    "windows-x64": ("Windows", "64-bit"),
}


def identity() -> dict:
    ident = json.loads(IDENTITY.read_text(encoding="utf-8"))
    missing = [k for k, v in ident.items()
               if isinstance(v, str) and v.startswith("PLACEHOLDER")]
    if missing:
        raise SystemExit(
            "identity.json still has placeholders: " + ", ".join(missing) +
            "\nFill them in first — publishing a page with a dead download "
            "link is worse than publishing nothing.")
    return ident


def bundles() -> list[dict]:
    out = []
    for key, (os_name, arch) in PLATFORM_LABELS.items():
        f = DIST / f"Alto-{key}.mcpb"
        if not f.exists():
            continue
        data = f.read_bytes()
        out.append({
            "key": key, "os": os_name, "arch": arch, "name": f.name,
            "mb": round(len(data) / 1048576),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    if not out:
        raise SystemExit("no bundles in packaging/dist — run build_mcpb.py first")
    return out


# ── MCP Registry entry ───────────────────────────────────────────────────────

def server_json(ident: dict, files: list[dict]) -> dict:
    """The registry lists where a server lives; it does not host anything.

    The bundles are listed as `mcpb` packages pointing straight at the GitHub
    Release assets, which is the artifact people actually install — no PyPI
    round trip, and the registry verifies each download against fileSha256.

    A `pypi` entry is added only once the package is actually published
    (`pypi_published` in identity.json). Listing one before it exists would
    advertise an install path that fails.
    """
    name = f"io.github.{ident['github_user']}/{ident['github_repo']}"
    repo = f"https://github.com/{ident['github_user']}/{ident['github_repo']}"
    base = f"{repo}/releases/download/v{__version__}"

    packages = [{
        "registryType": "mcpb",
        "identifier": f"{base}/{f['name']}",
        "version": __version__,
        "fileSha256": f["sha256"],
        "transport": {"type": "stdio"},
    } for f in files]

    if ident.get("pypi_published"):
        packages.append(_pypi_package(ident))

    return {**_server_base(ident, name, repo), "packages": packages}


def _pypi_package(ident: dict) -> dict:
    return {
        "registryType": "pypi",
        "identifier": ident["pypi_package"],
        "version": __version__,
        "transport": {"type": "stdio"},
        "runtimeHint": "uvx",
        "environmentVariables": _env_vars(),
    }


def _server_base(ident: dict, name: str, repo: str) -> dict:
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": name,
        "description": ("Build an interactive timeline from your own materials "
                        "— never from invented content."),
        "version": __version__,
        "repository": {
            "url": f"https://github.com/{ident['github_user']}/{ident['github_repo']}",
            "source": "github",
        },
        "websiteUrl": f"https://{ident['firebase_site']}.web.app",
    }


def _env_vars() -> list[dict]:
    return [
        {"name": "ALTO_STORE_DIR",
         "description": "Where timelines are kept on this machine.",
         "isRequired": False,
         "default": "~/Documents/Alto"},
        {"name": "ALTO_FIREBASE_SITE",
         "description": "Your own Firebase Hosting site id, for publishing "
                        "shareable links.",
         "isRequired": False},
        {"name": "ALTO_FIREBASE_PROJECT",
         "description": "The Firebase project that site belongs to.",
         "isRequired": False},
        {"name": "ALTO_FIREBASE_CONFIG",
         "description": "Your Firebase web SDK config JSON, which enables "
                        "cross-device sync of highlights and notes. Alto "
                        "never ships a project of its own.",
         "isRequired": False,
         "isSecret": True},
    ]


# ── download page ────────────────────────────────────────────────────────────

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Alto — build a timeline from your own material</title>
<meta name="description" content="Alto interviews you about material you already have and builds an interactive, filterable timeline from it. It never invents content.">
<meta name="theme-color" content="#f0efea" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#12141f" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon-192.png">
<style>
  *,*::before,*::after{{box-sizing:border-box}}
  :root{{
    --bg:#f0efea; --surface:#fffffff2; --text:#1b1d29; --dim:#5d6172;
    --border:#0f13260f; --line:#c9c6bd; --accent:#7c6ef0;
    --shadow:0 1px 2px #0f132608, 0 12px 32px -12px #0f132626;
  }}
  @media (prefers-color-scheme: dark){{
    :root{{
      --bg:#12141f; --surface:#1c1f2ecc; --text:#eef0f7; --dim:#a2a7bd;
      --border:#ffffff14; --line:#2b3044; --accent:#a394ff;
      --shadow:0 1px 2px #0006, 0 16px 40px -14px #0009;
    }}
  }}
  html{{-webkit-text-size-adjust:100%}}
  body{{
    margin:0; background:var(--bg); color:var(--text);
    font:16px/1.65 ui-sans-serif,-apple-system,"SF Pro Text",Inter,system-ui,sans-serif;
    -webkit-font-smoothing:antialiased;
    padding:max(28px,env(safe-area-inset-top)) 20px
            max(48px,env(safe-area-inset-bottom));
  }}
  .wrap{{max-width:680px;margin:0 auto}}
  header{{display:flex;align-items:center;gap:14px;margin-bottom:34px}}
  header img{{width:52px;height:52px;display:block}}
  h1{{font-size:1.55rem;letter-spacing:-.02em;margin:0;font-weight:650}}
  .tag{{color:var(--dim);font-size:.94rem;margin:2px 0 0}}
  .lede{{font-size:1.08rem;line-height:1.6;margin:0 0 10px}}
  .rule{{color:var(--dim);font-size:.96rem;margin:0 0 34px}}
  h2{{font-size:.78rem;text-transform:uppercase;letter-spacing:.1em;
     color:var(--dim);font-weight:600;margin:38px 0 14px}}
  .dl{{display:flex;flex-direction:column;gap:10px}}
  .notice{{
    background:var(--surface);border:1px solid var(--accent);
    border-left-width:3px;border-radius:10px;padding:13px 16px;
    margin:0 0 8px;font-size:.94rem;
  }}
  a.card{{
    display:flex;align-items:center;gap:14px;text-decoration:none;color:inherit;
    background:var(--surface);border:1px solid var(--border);border-radius:14px;
    padding:15px 17px;box-shadow:var(--shadow);
    transition:transform .16s ease, border-color .16s ease;
  }}
  a.card:hover{{transform:translateY(-1px);border-color:var(--accent)}}
  a.card:focus-visible{{outline:2px solid var(--accent);outline-offset:3px}}
  .os{{font-weight:600}}
  .arch{{color:var(--dim);font-size:.86rem}}
  .size{{margin-left:auto;color:var(--dim);font-size:.84rem;
        font-variant-numeric:tabular-nums;white-space:nowrap}}
  ol{{padding-left:1.15rem;margin:0}}
  ol li{{margin:0 0 9px}}
  code{{
    font:.86em ui-monospace,SFMono-Regular,Menlo,monospace;
    background:var(--surface);border:1px solid var(--border);
    border-radius:6px;padding:.12em .42em;
  }}
  details{{
    background:var(--surface);border:1px solid var(--border);
    border-radius:12px;padding:13px 16px;margin-top:12px;
  }}
  summary{{cursor:pointer;font-weight:560}}
  details p:last-child{{margin-bottom:0}}
  .sums{{
    font:.72rem/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
    color:var(--dim);word-break:break-all;margin:10px 0 0;
  }}
  footer{{
    margin-top:46px;padding-top:22px;border-top:1px solid var(--line);
    color:var(--dim);font-size:.86rem;
  }}
  footer a{{color:inherit}}
  @media (max-width:430px){{
    .arch{{display:block}}
    a.card{{align-items:flex-start}}
  }}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <img src="/icon.svg" alt="" width="52" height="52">
    <div>
      <h1>Alto</h1>
      <p class="tag">A connector for Claude Desktop · v{version}</p>
    </div>
  </header>

  <p class="lede">Alto interviews you about material you already have — a
  course, a novel, a research project — and builds it into an interactive,
  filterable timeline. Cards on colored act bands, entity chips, connection
  lines, detail pages using your own headings, highlights and notes, a mobile
  layout, and a single offline file you can send to anyone.</p>

  <p class="rule">It never invents content. Alto organizes what you give it and
  nothing else — sparse notes make a sparse timeline, on purpose.</p>

{notice}  <h2>Download</h2>
  <div class="dl">
{cards}
  </div>

  <h2>Installing</h2>
  <ol>
    <li>Download the file for your computer.</li>
    <li>Open <strong>Claude Desktop → Settings → Extensions → Advanced
        settings → Install Extension…</strong> and choose the file you
        downloaded. (Double-clicking it works too, if your system opens
        <code>.mcpb</code> files with Claude.)</li>
    <li>Restart Claude Desktop. Alto appears under Extensions.</li>
    <li>Start a chat and say <em>“I want to build a timeline in Alto —
        interview me.”</em></li>
  </ol>

  <details>
    <summary>Do I need to install anything else?</summary>
    <p>No. Each download carries its own copy of Python, so there is nothing to
    set up first. That is why the files are around 50&nbsp;MB.</p>
  </details>

  <details>
    <summary>Where do my timelines go?</summary>
    <p>Onto your own computer, in <code>~/Documents/Alto</code>. Every timeline
    is also produced as a self-contained file you can open or send to someone
    without any server involved.</p>
    <p>Publishing shareable web links is optional and uses <em>your</em> free
    Firebase project, never one of ours. Leave it unconfigured and Alto simply
    stays offline. See the <a href="/privacy/">privacy note</a>.</p>
  </details>

{cli}  <details>
    <summary>Verifying your download</summary>
    <p class="sums">{sums}</p>
  </details>

  <footer>
    <a href="{repo}">Source</a> ·
    <a href="{repo}/releases">Releases</a> ·
    <a href="/privacy/">Privacy</a> ·
    {license} · © 2026 {author}
  </footer>

</div>
</body>
</html>
"""


def build_page(ident: dict, files: list[dict]) -> str:
    repo = f"https://github.com/{ident['github_user']}/{ident['github_repo']}"
    base = f"{repo}/releases/download/v{__version__}"
    cards = "\n".join(
        f'    <a class="card" href="{base}/{f["name"]}" download>\n'
        f'      <span><span class="os">{f["os"]}</span> '
        f'<span class="arch">{f["arch"]}</span></span>\n'
        f'      <span class="size">{f["mb"]} MB</span>\n'
        f'    </a>'
        for f in files)
    sums = "<br>".join(f'{f["sha256"]}&nbsp;&nbsp;{f["name"]}' for f in files)
    # Only advertise the PyPI route once the package actually exists.
    cli = ("""  <details>
    <summary>Prefer the command line?</summary>
    <p><code>uvx %s</code> runs the same server from PyPI, for use with any
    MCP client.</p>
  </details>

""" % ident["pypi_package"]) if ident.get("pypi_published") else ""
    notice = (f'  <p class="notice">{ident["notice"]}</p>\n\n'
              if ident.get("notice") else "")
    return PAGE.format(version=__version__, cards=cards, sums=sums, repo=repo,
                       cli=cli, notice=notice, license=ident["license"],
                       author=ident["author_name"])


def build_site(ident: dict, files: list[dict]) -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(build_page(ident, files), encoding="utf-8")

    # The glyph, as a favicon and as the page mark.
    shutil.copy2(ROOT / "alto" / "assets" / "alto-mark.svg", SITE / "icon.svg")
    shutil.copy2(ROOT / "alto" / "assets" / "png" / "alto-light-256.png",
                 SITE / "icon-192.png")

    privacy = SITE / "privacy"
    privacy.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "alto" / "privacy.html", privacy / "index.html")

    (SITE / "firebase.json").write_text(json.dumps({
        "hosting": {
            "site": ident["firebase_site"],
            "public": ".",
            "ignore": ["firebase.json", ".firebaserc", "**/.*"],
            "headers": [{
                "source": "**",
                "headers": [
                    {"key": "Content-Security-Policy",
                     "value": ("default-src 'self'; style-src 'self' "
                               "'unsafe-inline'; img-src 'self' data:; "
                               "object-src 'none'; base-uri 'self'; "
                               "form-action 'none'; frame-ancestors 'none'")},
                    {"key": "X-Content-Type-Options", "value": "nosniff"},
                    {"key": "Referrer-Policy",
                     "value": "strict-origin-when-cross-origin"},
                ],
            }],
        },
    }, indent=2) + "\n", encoding="utf-8")

    (SITE / ".firebaserc").write_text(json.dumps({
        "projects": {"default": ident["firebase_project"]}}, indent=2) + "\n",
        encoding="utf-8")


MCP_NAME_MARK = "mcp-name:"


def stamp_readme(ident: dict) -> None:
    """The registry proves PyPI ownership by finding this exact line in the
    published package README, so it has to match server.json's name."""
    name = f"io.github.{ident['github_user']}/{ident['github_repo']}"
    line = f"{MCP_NAME_MARK} {name}"
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    lines = text.split("\n")
    for i, existing in enumerate(lines):
        if existing.startswith(MCP_NAME_MARK):
            lines[i] = line
            readme.write_text("\n".join(lines), encoding="utf-8")
            return
    # Not present yet — insert directly under the H1 so it survives any
    # rewrite of the prose below it.
    for i, existing in enumerate(lines):
        if existing.startswith("# "):
            lines.insert(i + 1, "\n" + line)
            break
    else:
        lines.insert(0, line)
    readme.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ident = identity()
    files = bundles()

    (ROOT / "server.json").write_text(
        json.dumps(server_json(ident, files), indent=2) + "\n", encoding="utf-8")
    print("✓ server.json")

    stamp_readme(ident)
    print("✓ README mcp-name line")

    build_site(ident, files)
    print(f"✓ packaging/site/  ({len(files)} downloads listed)")
    for f in files:
        print(f"    {f['os']:8} {f['arch']:26} {f['mb']:>3} MB")

    print("\nNext:")
    print(f"  cd packaging/site && firebase deploy "
          f"--only hosting:{ident['firebase_site']}")


if __name__ == "__main__":
    main()
