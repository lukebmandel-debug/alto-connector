"""Frames for a Holographic background clip (alto/build/holo_video.py), deterministic: every CSS animation of the background's layer is paused and set to the frame's time
(Web Animations currentTime), then the page is screenshotted. The page is the background alone at the clip's proportions (16:10, 1920 x 1200 CSS px, the scene box), the picture
with the page-bg layer's own filter (saturate 1.15) and the animation layer over it as holo_anim.py draws it.

  python render_frames.py <kind> <out dir> [fps=30] [scale=1.3333] [only the first N frames]    kind: neon (more come with their loop lengths)
Frame i is time i/fps; the clip has LOOP*fps frames and frame LOOP*fps would equal frame 0 (checked: written as frame_end.png).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright   # noqa: E402
from alto.build import holo_anim as ha, holo_backgrounds as hb   # noqa: E402

BG = {"neon": "h-neon-rain", "rain": "h-signal-rain", "sweep": "h-grid-horizon", "drift": "h-lightspeed", "haze": "h-amber-haze", "target": "h-targeting"}
LOOP = {k: ha.LOOP for k in BG}
# Loop overrides (Art stage-2 notes): every period divides 12 s and no motion is faster than the CSS the sheet approved (same px/s, same degrees/s; the swing/fade ranges shrink to fit).
def _loop_css(kind: str) -> str:
    if kind == "rain":      # tile height = speed x 12 s  (25.6, 22.7, 21.7 px/s)
        import random
        R = random.Random(21)
        out = []
        for i, (h, n, w, a) in enumerate(((307, 44, 1, .55), (272, 32, 1, .42), (260, 24, 2, .30))):
            lay = ",".join(f"var(--g{i + 1}) {R.randrange(ha.W)}px {R.randrange(h)}px/{w}px {h}px repeat-y" for _ in range(n))
            out.append(f".ha-rain i:nth-of-type({i + 1}){{top:-{h}px;height:calc(100% + {h}px);background:{lay};animation:ha-fall{i + 1} 12s linear infinite}}"
                       f"@keyframes ha-fall{i + 1}{{to{{transform:translateY({h}px)}}}}")
        return "".join(out)
    if kind == "sweep":     # the band's travel (72% of 16 s = 11.5 s) becomes 96% of 12 s: same speed
        return (".ha-sweep i{animation:ha-sweep 12s cubic-bezier(.45,.05,.55,.95) infinite}"
                "@keyframes ha-sweep{0%{transform:translateY(0)}96%,100%{transform:translateY(calc(1200px + 280px))}}")
    if kind == "drift":     # 14 s -> 12 s with the swell's range cut to 1.56 so the rate of growth is unchanged
        return (".ha-drift div{animation:ha-drift 12s ease-in infinite}.ha-drift div+div{animation-delay:-6s}"
                "@keyframes ha-drift{0%{transform:scale(.7);opacity:0}15%{opacity:.5}100%{transform:scale(1.56);opacity:0}}")
    if kind == "haze":      # dust sways (to and fro, 12 s) by half of what the old one-way pass covered in 6 s; the sun breathes 6 s up, 6 s down over the same rate
        return (".ha-haze .df{animation:ha-sway1 12s ease-in-out infinite;left:-400px}.ha-haze .dn{animation:ha-sway2 12s ease-in-out infinite;left:-500px}"
                "@keyframes ha-sway1{0%,100%{transform:translateX(0)}50%{transform:translateX(46px)}}@keyframes ha-sway2{0%,100%{transform:translateX(0)}50%{transform:translateX(100px)}}"
                ".ha-haze .sun{animation:ha-breathe 12s ease-in-out infinite}@keyframes ha-breathe{0%,100%{opacity:.35}50%{opacity:.675}}")
    return ""
def _rings() -> str:    # one dotted ring and one dashed ring, each an exact number of dashes round, so a whole number of dashes of turning is a perfect loop (72 and -48 degrees a loop)
    import math
    def ring(r, n, dash, op):
        c = 2 * math.pi * r / n
        return (f'<svg viewBox="{-r - 2} {-r - 2} {2 * r + 4} {2 * r + 4}"><circle r="{r}" fill="none" stroke="#{ha.INK_HEX}" stroke-opacity="{op}" '
                f'stroke-dasharray="{dash} {c - dash:.3f}" stroke-width="1.4"/></svg>')
    return ('<div class="ha-scene"><div class="pa"><i class="ping"></i></div><div class="ring r1">' + ring(170, 90, 2, .35) + '</div><div class="ring r2">' + ring(380, 45, 40, .2) + "</div></div>")
LOOPKEYS = {"target": ".ha-target .r1{animation:ha-turn1 12s linear infinite}@keyframes ha-turn1{to{transform:rotate(72deg)}}.ha-target .r2{animation:ha-turn2 12s linear infinite}@keyframes ha-turn2{to{transform:rotate(-48deg)}}"}
W, H = 1920, 1200


def page(kind: str) -> str:
    pic = {i: f for i, _, f in hb.HOLO_BGS}[BG[kind]]()[1]["b"]          # the dark version: Holographic is dark on a computer
    if kind == "target":
        pic = ha._DA                                                       # Art FIX 2: no still dashed rings under the turning ones
    return ("<!doctype html><html class='alto-holo'><head><meta charset='utf-8'><style>html,body{margin:0;height:100%;background:#000;overflow:hidden}"
            "#pic{position:fixed;inset:0;filter:brightness(1) blur(0px) saturate(1.15);background:" + pic + "}</style><style>" + ha.CSS + _loop_css(kind) + (LOOPKEYS.get(kind, "")) + "</style></head><body>"
            "<div id='pic'></div><div id='alto-ha' class='ha ha-" + kind + "'><b class='zp'></b>" + (_rings() if kind == "target" else ha.HTML[kind]) + "</div></body></html>")


def main():
    kind, out = sys.argv[1], Path(sys.argv[2])
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    scale = float(sys.argv[4]) if len(sys.argv) > 4 else 4 / 3
    out.mkdir(parents=True, exist_ok=True)
    n = LOOP[kind] * fps
    lim = int(sys.argv[5]) if len(sys.argv) > 5 else n          # a short try-out: only the first lim frames
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=scale)
        pg = ctx.new_page()
        pg.set_content(page(kind))
        # the scene box = the whole frame (what hafit does in the page, at this size)
        pg.evaluate("""(()=>{const s=document.querySelector('.ha-scene'); if(s){ s.style.cssText='left:0;bottom:0;width:100%;transform:none'; }
          document.querySelectorAll('.rn,.rf').forEach(e=>e.style.inset='-'+Math.ceil(.13*innerWidth)+'px')})()""")
        pg.wait_for_timeout(500)
        for i in list(range(lim)) + (["end"] if lim == n else []):
            t = (n if i == "end" else i) / fps * 1000
            pg.evaluate("""t=>new Promise(r=>{ document.getAnimations().forEach(a=>{a.pause(); a.currentTime=t}); requestAnimationFrame(()=>requestAnimationFrame(r)) })""", t)
            pg.screenshot(path=str(out / (f"frame_{i:04d}.png" if i != "end" else "frame_end.png")))
        print("animations:", pg.evaluate("document.getAnimations().length"))
        b.close()


if __name__ == "__main__":
    main()
