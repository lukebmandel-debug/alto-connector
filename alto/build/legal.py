"""The beta's legal pages: Privacy Policy, Beta Terms and Credits (Luke 2026-10-30, REQUIRED-for-beta R1/R2/R4; the storage notice is a section of the policy).

The words live in alto/legal/*.md and nothing else: Strategy's final text replaces a file and nothing in code changes. alto/legal/VERSION is the one
version of the terms + privacy a person agrees to (the sign-in box and the Firestore record read it; a new version asks everyone again).
The pages are hosted / static (publish_static writes /privacy/, /terms/ and /credits/), so the private page does not grow. Markdown here is the small
subset the drafts use: # title, ## heading, - bullets, **bold**, [links](url), paragraphs, and the first italic line as a note.
"""
import html
import re
from pathlib import Path

LEGAL = Path(__file__).resolve().parent.parent / "legal"
# path on the site -> (file, name in the footer line)
PAGES = {"privacy": ("privacy-policy.md", "Privacy"), "terms": ("beta-terms.md", "Beta Terms"), "credits": ("credits.md", "Credits")}


def version() -> str:
    return (LEGAL / "VERSION").read_text(encoding="utf-8").strip()


def _inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((/[a-z/]*|https?://[^)\s]+|mailto:[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def render_body(md: str) -> tuple[str, str]:
    """(title, body html) of one markdown file."""
    title, out, items = "", [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
    for ln in md.splitlines():
        ln = ln.rstrip()
        if ln.startswith("# "):
            title = ln[2:].strip()
        elif ln.startswith("## "):
            flush()
            out.append(f"<h2>{_inline(ln[3:].strip())}</h2>")
        elif ln.startswith("- "):
            items.append(ln[2:].strip())
        elif ln.strip():
            flush()
            out.append(f'<p class="note">{_inline(ln.strip("*_ "))}</p>' if ln.startswith("*") and ln.endswith("*") else f"<p>{_inline(ln.strip())}</p>")
    flush()
    return title, "\n".join(out)


CSS = """
:root{--bg:#f0efea;--tx:#1a1a2e;--mu:#5a5a70;--ac:#4a3ab0;--ln:rgba(26,26,46,.18)}
html.dark{--bg:#10111a;--tx:#ecebf4;--mu:#a6a6bb;--ac:#a99cff;--ln:rgba(236,235,244,.2)}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.65 Georgia,serif}
main{max-width:720px;margin:0 auto;padding:40px 20px 24px}
h1{font-size:26px;letter-spacing:.02em;margin:0 0 6px} h2{font-size:18px;margin:1.8em 0 .4em}
p,li{margin:.5em 0} ul{padding-left:1.3em} .note{color:var(--mu);font-size:14px}
a{color:var(--ac)} strong{font-weight:700}
nav,footer{max-width:720px;margin:0 auto;padding:0 20px;font:14px/1.6 system-ui,sans-serif}
nav{padding-top:20px} footer{padding-bottom:40px;color:var(--mu);border-top:1px solid var(--ln);margin-top:32px;padding-top:14px}
footer a{margin-right:14px}
"""
# the look follows the person's choice: light/dark is read from what Alto already keeps (alto-theme-v1). The homepage has no Retro style yet; when it does, add its key here
HEAD_JS = ("try{var d=document.documentElement;if(localStorage.getItem('alto-theme-v1')==='dark')d.classList.add('dark');}catch(e){}")


OSM = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">Map data &copy; OpenStreetMap contributors (ODbL)</a>'


def footer_links(current: str = "") -> str:
    cur = ' aria-current="page"'
    return "".join('<a href="/%s/"%s>%s</a>' % (k, cur if k == current else "", html.escape(n)) for k, (_, n) in PAGES.items())


def page(key: str) -> str:
    fname, name = PAGES[key]
    title, body = render_body((LEGAL / fname).read_text(encoding="utf-8"))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><title>{html.escape(title or name)}</title><script>{HEAD_JS}</script><style>{CSS}</style></head><body>'
            f'<nav><a href="/">&larr; Alto</a></nav><main><h1>{html.escape(title or name)}</h1><p class="note">Version {html.escape(version())}</p>{body}</main>'
            f'<footer>{footer_links(key)}<br>{OSM}</footer></body></html>')


def pages() -> dict[str, str]:
    """site path ('privacy', 'terms', 'credits') -> html"""
    return {k: page(k) for k in PAGES}
