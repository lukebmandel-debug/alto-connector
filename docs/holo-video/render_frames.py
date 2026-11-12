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

BG = {"neon": "h-neon-rain"}
LOOP = {"neon": ha.LOOP}
W, H = 1920, 1200


def page(kind: str) -> str:
    pic = {i: f for i, _, f in hb.HOLO_BGS}[BG[kind]]()[1]["b"]          # the dark version: Holographic is dark on a computer
    return ("<!doctype html><html class='alto-holo'><head><meta charset='utf-8'><style>html,body{margin:0;height:100%;background:#000;overflow:hidden}"
            "#pic{position:fixed;inset:0;filter:brightness(1) blur(0px) saturate(1.15);background:" + pic + "}</style><style>" + ha.CSS + "</style></head><body>"
            "<div id='pic'></div><div id='alto-ha' class='ha ha-" + kind + "'><b class='zp'></b>" + ha.HTML[kind] + "</div></body></html>")


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
