"""Board L-1123 chip backdrop: cards scroll under the clear top bars (clear_top.py), so every filter chip and group label carries its own plate,
opaque (alpha >= .85) or blurred (>= 8px), in Classic, Retro and Holo, desktop and phone; the plates move no box. Headless WebKit, offline, silent."""
import pytest

from test_holo_glass_273_torts import _page

JS = """async () => {
  const vis = (e) => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return r.width > 2 && r.height > 2 && c.display !== 'none' && c.visibility !== 'hidden'; };
  const els = () => [...document.querySelectorAll('#nav .nav-btn, #nav .nav-group-label')].filter(vis);
  const cv = document.querySelector('#canvas'); if (cv) cv.scrollTop += 250; window.scrollBy(0, 250);
  await new Promise(r => setTimeout(r, 600));
  const alpha = (s) => { const m = s.match(/rgba?\\(([^)]*)\\)/); if (m) { const p = m[1].split(/[ ,\\/]+/).filter(Boolean); return p.length > 3 ? parseFloat(p[3]) : 1; }
    const k = s.match(/color\\([^)]*\\/\\s*([\\d.]+)\\)/); if (k) return parseFloat(k[1]); return /^color\\(/.test(s) ? 1 : 0; };
  const blur = (s) => { const m = (s || '').match(/blur\\(([\\d.]+)px\\)/); return m ? parseFloat(m[1]) : 0; };
  const rect = (e) => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(v => Math.round(v * 10) / 10).join(','); };
  const now = els().map(e => { const c = getComputedStyle(e); return {t: (e.textContent || '').trim().slice(0, 16), a: alpha(c.backgroundColor), b: blur(c.webkitBackdropFilter || c.backdropFilter), r: rect(e)}; });
  const st = document.createElement('style'); st.textContent = '#nav .nav-btn,#nav .nav-group-label{background:none!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}';
  document.head.appendChild(st); await new Promise(r => setTimeout(r, 100));
  const bare = els().map(rect);
  return {now, bare}; }"""


@pytest.mark.parametrize("vw,vh,mob", [(1440, 900, False), (390, 844, True), (844, 390, True)], ids=["d1440", "p390", "l844"])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_chip_and_label_plates_hide_cards_under_them(style, vw, vh, mob):
    r = _page(style, vw, vh, mob, js=JS)
    if not mob:
        assert len(r["now"]) >= 10, r["now"]
    for c in r["now"]:
        assert c["a"] >= 0.85 or c["b"] >= 8, (style, vw, c, "chip text can sit on card text")
    assert [c["r"] for c in r["now"]] == r["bare"], (style, vw, "the plate moved a chip")
