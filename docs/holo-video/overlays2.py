"""The 12 s motion of Holographic backgrounds 7-11 (Art's round-2 notes), drawn as an SVG layer over the scene (1600 x 1000, the picture's own coordinates, `slice` like the picture) and animated with CSS
transform/opacity only. Every period divides 12 s. Used by render_frames.py only: the clips carry the motion, the page ships no CSS layer for these."""
import random

KINDS = ("aurora", "bay", "jade", "dune", "tether")
W, H = 1600, 1000


def _kf(name, body):
    return f"@keyframes {name}{{{body}}}"


def overlay(kind):
    R = random.Random(7)
    d = ('<defs><filter id="ob" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>'
         '<filter id="ob2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>'
         '<filter id="ob3" x="-30%" y="-80%" width="160%" height="260%"><feGaussianBlur stdDeviation="16"/></filter>'
         '<radialGradient id="rr"><stop offset="0" stop-color="#ff5a4a" stop-opacity=".95"/><stop offset="1" stop-color="#ff5a4a" stop-opacity="0"/></radialGradient>'
         '<radialGradient id="ra"><stop offset="0" stop-color="#ffb347" stop-opacity=".95"/><stop offset="1" stop-color="#ffb347" stop-opacity="0"/></radialGradient>'
         '<radialGradient id="rw"><stop offset="0" stop-color="#dffcff" stop-opacity=".95"/><stop offset=".5" stop-color="#7fe8f0" stop-opacity=".35"/><stop offset="1" stop-color="#7fe8f0" stop-opacity="0"/></radialGradient>'
         '<radialGradient id="rl"><stop offset="0" stop-color="#ffd070" stop-opacity=".9"/><stop offset="1" stop-color="#ffd070" stop-opacity="0"/></radialGradient>'
         '<radialGradient id="rs"><stop offset="0" stop-color="#ffc08a" stop-opacity=".9"/><stop offset="1" stop-color="#ff8f60" stop-opacity="0"/></radialGradient></defs>')
    css, o = "", []
    if kind == "aurora":
        for i in range(10):
            x0 = 80 + i * 150 + R.randint(-20, 20)
            o.append(f'<path class="ry r{i % 2}" d="M{x0} 110l{R.randint(26, 44)} 0l{R.randint(30, 60)} 430l-{R.randint(30, 44)} 0Z" fill="#8dffcf" fill-opacity="{R.uniform(.07, .13):.2f}" filter="url(#ob)"/>')
        o.append('<ellipse class="ed" cx="800" cy="470" rx="900" ry="70" fill="#b8ffd8" filter="url(#ob3)"/>')
        o.append('<g class="lamp"><circle cx="1394" cy="606" r="44" fill="url(#rr)"/><circle cx="1394" cy="606" r="4" fill="#fff0e8"/></g>')
        css = (".ry{animation:ay 12s ease-in-out infinite}.ry.r1{animation-delay:-6s}" + _kf("ay", "0%,100%{transform:translateX(-45px)}50%{transform:translateX(45px)}") +
               ".ed{opacity:0;animation:ae 12s ease-in-out infinite}" + _kf("ae", "0%,100%{opacity:0}50%{opacity:.34}") +
               ".lamp{opacity:.05;animation:al 4s linear infinite}" + _kf("al", "0%,55%{opacity:.05}62%,78%{opacity:1}86%,100%{opacity:.05}"))
    elif kind == "bay":
        cx, cy = 800, 655
        S = [1.55 * .74 ** k for k in range(8)]
        lights = []
        for k in range(7):
            for f in (0, .5):
                s = S[k] + (S[k + 1] - S[k]) * f
                if cy + 330 * s > H + 40:
                    continue
                lights.append(s)
        N = len(lights)
        for j, s in enumerate(lights):                         # nearest first, so the run goes down the deck toward the door
            for sg in (-1, 1):
                x, y = cx + sg * 430 * s, cy + 330 * s - 6 * s
                o.append(f'<g class="gl" style="animation-delay:{j * 4 / N - 4:.3f}s"><ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{60 * s:.0f}" ry="{22 * s:.0f}" fill="url(#ra)"/>'
                         f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{9 * s:.1f}" ry="{3.6 * s:.1f}" fill="#fff6d8"/></g>')
        o.append(f'<ellipse class="dr" cx="{cx}" cy="{cy}" rx="380" ry="270" fill="url(#rw)"/>')
        css = (".gl{opacity:0;animation:ag 4s linear infinite}" + _kf("ag", "0%{opacity:0}8%{opacity:1}30%{opacity:0}100%{opacity:0}") +
               ".dr{opacity:0;animation:ad 12s ease-in-out infinite}" + _kf("ad", "0%,100%{opacity:0}50%{opacity:.5}"))
    elif kind == "jade":
        def tile(n, a, b, op, w):
            s = "".join(f"M{R.randint(0, W + 200)} {R.randint(0, 800)}l-{(b) // 9} {R.randint(a, b)}" for _ in range(n))
            return "".join(f'<path d="{s}" transform="translate(0 {dy})" stroke="#c8ffe8" stroke-opacity="{op}" stroke-width="{w}"/>' for dy in (-800, 0, 800))
        o.append(f'<g class="rf">{tile(80, 16, 30, .16, 1.1)}</g><g class="rn">{tile(26, 60, 110, .13, 1.6)}</g>')
        mist = "".join(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="translate({dx} 0)"/>' for dx in (0, 800, 1600) for cx, cy, rx, ry in ((120, 800, 170, 22), (470, 880, 230, 28), (700, 940, 160, 20), (320, 960, 200, 24)))
        o.append(f'<g class="mi" fill="#bfffe0" fill-opacity=".13" filter="url(#ob)">{mist}</g>')
        o.append('<rect class="fl" x="1010" y="328" width="38" height="242" fill="#03120d"/>')
        for x, y in ((700, 372), (930, 384), (1010, 302), (640, 262)):
            o.append(f'<g class="sw"><circle cx="{x}" cy="{y}" r="40" fill="url(#rl)" fill-opacity=".55"/></g>')
        css = (".rf{animation:jf 12s linear infinite}.rn{animation:jn 6s linear infinite}" + _kf("jf", "to{transform:translateY(800px)}") + _kf("jn", "to{transform:translateY(800px)}") +
               ".mi{animation:jm 12s linear infinite}" + _kf("jm", "to{transform:translateX(-800px)}") +
               ".fl{opacity:0;animation:jx 6s linear infinite}" + _kf("jx", "0%,60%{opacity:0}64%{opacity:.85}70%{opacity:.2}76%{opacity:.8}82%,100%{opacity:0}") +
               ".sw{animation:js 4s ease-in-out infinite}" + _kf("js", "0%,100%{transform:translateX(-8px)}50%{transform:translateX(8px)}"))
    elif kind == "dune":
        o.append('<g class="bm"><rect x="693" y="0" width="14" height="612" fill="#ffb090" filter="url(#ob2)"/><rect x="699" y="0" width="2" height="612" fill="#ffd8c0"/><circle cx="700" cy="612" r="80" fill="url(#rs)"/></g>')
        o.append('<g class="cd" filter="url(#ob3)"><ellipse cx="0" cy="256" rx="300" ry="26" fill="#8da0e0" fill-opacity=".42"/><ellipse cx="-120" cy="244" rx="170" ry="18" fill="#a6b6f0" fill-opacity=".34"/><ellipse cx="150" cy="270" rx="200" ry="16" fill="#8da0e0" fill-opacity=".3"/></g>')
        st = "".join(f'<circle class="tw" style="animation-delay:{-R.uniform(0, 6):.2f}s" cx="{R.randint(20, 1580)}" cy="{int(560 * R.random() ** 1.3)}" r="{R.choice((1.4, 1.8, 2.2))}" fill="#eaf2ff"/>' for _ in range(40))
        o.append(st)
        css = (".bm{opacity:.1;animation:db 4s ease-in-out infinite}" + _kf("db", "0%,100%{opacity:.1}35%{opacity:1}") +
               ".cd{animation:dc 12s linear infinite}" + _kf("dc", "0%{transform:translateX(-400px)}100%{transform:translateX(2000px)}") +
               ".tw{opacity:.25;animation:dt 6s ease-in-out infinite}" + _kf("dt", "0%,100%{opacity:.25}50%{opacity:1}"))
    elif kind == "tether":
        o.append('<g class="car"><circle cx="930" cy="0" r="18" fill="url(#rw)"/><rect x="927.5" y="-6" width="5" height="12" fill="#fffaf0"/></g>')
        cl = "".join(f'<ellipse cx="{cx + dx}" cy="{cy}" rx="{rx}" ry="{ry}"/>' for dx in (0, 800, 1600) for cx, cy, rx, ry in ((120, 470, 270, 34), (520, 540, 320, 40), (300, 610, 210, 28), (680, 600, 150, 22)))
        o.append(f'<g class="cl" fill="#ffd8cc" fill-opacity=".2" filter="url(#ob3)">{cl}</g>')
        o.append('<ellipse class="wm" cx="970" cy="846" rx="560" ry="150" fill="url(#rs)"/>')
        css = (".car{opacity:0;animation:tc 12s linear infinite}" + _kf("tc", "0%{transform:translateY(805px);opacity:0}6%{opacity:1}55%{opacity:1}100%{transform:translateY(150px);opacity:0}") +
               ".cl{animation:tl 12s linear infinite}" + _kf("tl", "to{transform:translateX(-800px)}") +
               ".wm{opacity:0;animation:tw2 12s ease-in-out infinite}" + _kf("tw2", "0%,100%{opacity:0}50%{opacity:.35}"))
    return f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%" aria-hidden="true">{d}{"".join(o)}</svg>', css
