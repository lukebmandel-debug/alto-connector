"""CPU reading, headed WebKit (the method of ORG/resume/alto-testing.md, pm/cpuprobe3.py): Neon rain as VIDEO vs as CSS animation vs STILL (Reduce Motion), each page
8 s to settle then 30 s measured; ps process time of the ms-playwright processes and of WindowServer, as % of one core. (The ms-playwright sum also counts other agents' browsers on this shared Mac and goes negative when one exits: WindowServer is the figure to read.)
  python cpu_probe.py <repo> [reps=2]   (needs alto/assets/holo_video/neon-rain.mp4)"""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
tree = sys.argv[1]; reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
sys.path.insert(0, tree); sys.path.insert(0, tree + "/tests"); os.chdir(tree)
from playwright.sync_api import sync_playwright
from tests import test_holo_anim as T
from tests.range_server import serve
from alto.build import holo, retro, backgrounds_import as bi, holo_video as hv
from alto.build.blocks import ID_PATTERNS
page, tid = T._outline()
key = ID_PATTERNS["hl_key"].format(tid=tid)
d = Path(tempfile.mkdtemp()); (d / "t.html").write_text(page, encoding="utf-8")
(d / "holo").mkdir(); (d / "retro").mkdir(); (d / hv.FOLDER).mkdir()
n, t = holo.holo_asset()
# the CSS variant: a second site with the same script minus the clip's name (so it draws the CSS layer) and no /hvid/ folder
dc = Path(tempfile.mkdtemp()); (dc / "t.html").write_text(page, encoding="utf-8"); (dc / "holo").mkdir(); (dc / "retro").mkdir()
for dd, txt in ((d, t), (dc, re.sub(r'"vid":\{[^}]*\}', '"vid":{}', t))): (dd / "holo" / n).write_text(txt, encoding="utf-8")
n2, t2 = retro.retro_asset()
lib, js = bi.site_file()
for dd in (d, dc): (dd / "retro" / n2).write_text(t2, encoding="utf-8"); (dd / lib).write_text(js, encoding="utf-8")
for name, b in hv.files(): (d / hv.FOLDER / name).write_bytes(b)
srv, url = serve(d)
srv2, url_css = serve(dc)
def cpu():
    out = subprocess.run(["ps", "-A", "-o", "pid=,time=,command="], capture_output=True, text=True).stdout
    tot = 0.0; ws = 0.0
    for ln in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+):(\d+\.\d+)\s+(.*)", ln)
        if not m: continue
        tt = int(m.group(2)) * 60 + float(m.group(3)); cmd = m.group(4)
        if "ms-playwright" in cmd: tot += tt
        elif "/WindowServer" in cmd: ws = tt
    return tot, ws
res = {}
with sync_playwright() as p:
    for rep in range(reps):
        for name in ("VIDEO", "CSS", "STILL"):
            b = p.webkit.launch(headless=False)
            ctx = b.new_context(viewport={"width": 1400, "height": 860}, reduced_motion="reduce" if name == "STILL" else "no-preference")
            pg = ctx.new_page(); pg.goto((url_css if name == "CSS" else url) + "/t.html"); pg.wait_for_timeout(300)
            pg.evaluate("localStorage.clear()")
            pg.evaluate("([k,b,s])=>{ localStorage.setItem(k+'-style', s); localStorage.setItem(k+'-bg', JSON.stringify({v:b,t:Date.now()})); }", [key, "h-neon-rain", "holo"])
            pg.reload(); pg.bring_to_front(); pg.wait_for_timeout(8000)
            info = pg.evaluate("(()=>{const v=document.querySelector('#alto-ha video'); return {vis: document.visibilityState, hid: document.documentElement.classList.contains('hp-hid'), video: !!v, t: v&&v.currentTime, paused: v&&v.paused, anims: document.getAnimations().filter(a=>a.playState==='running').length}})()")
            (c0, w0) = cpu(); t0 = time.time(); pg.wait_for_timeout(30000); (c1, w1) = cpu(); t1 = time.time()
            info2 = pg.evaluate("(()=>{const v=document.querySelector('#alto-ha video'); return v&&v.currentTime})()")
            res.setdefault(name, []).append({"webkit_procs_pct_of_one_core": round(100 * (c1 - c0) / (t1 - t0), 2), "windowserver_pct": round(100 * (w1 - w0) / (t1 - t0), 2),
                                             "wall_s": round(t1 - t0, 1), "load1": os.getloadavg()[0], "at_settle": info, "video_time_after": info2})
            b.close()
            print(name, rep, res[name][-1], flush=True)
print(json.dumps(res, indent=1))
