#!/usr/bin/env python3
"""Builds the animated SVG cards for github.com/NirmanPatel036.

Run:  python scripts/build_cards.py
Needs: pip install fonttools brotli

With GITHUB_TOKEN set, the heatmap and activity cards use your real
contribution calendar. Without it they fall back to sample data.
Fonts are subset per card and embedded as base64, because GitHub's
image proxy blocks external font requests.
"""
import base64
import datetime as dt
import io
import json
import math
import os
import urllib.request
from collections import Counter, defaultdict
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "scripts", "fonts")
OUT = os.path.join(ROOT, "cards")
LOGIN = "NirmanPatel036"

# ---------- palette ----------
INK = "#3B2A36"
INK2 = "#4E3D49"
MUTED = "#6B5663"
CREAM = "#EEE2D2"
CREAM2 = "#E5D6C3"
VIOLET = "#4B4BF0"
CORAL = "#F0643F"
ORANGE = "#E8920F"
PLUM = "#3F2F3A"
LINK = "#3B3BD6"
HEAT = ["#E0D3C1", "#C3C5F8", "#9093F4", "#6366F1", "#3434C9"]

# ---------- fonts ----------
FONTS = {
    "serif": ("NPSerif", "normal", "instrument-serif-latin-400-normal.woff2"),
    "serif-i": ("NPSerif", "italic", "instrument-serif-latin-400-italic.woff2"),
    "sans": ("NPSans", "normal", "instrument-sans-latin-400-normal.woff2"),
    "mono": ("NPMono", "normal", "jetbrains-mono-latin-400-normal.woff2"),
}
_tt = {}


def tt(key):
    if key not in _tt:
        _tt[key] = TTFont(os.path.join(FONT_DIR, FONTS[key][2]))
    return _tt[key]


def metrics(key):
    f = tt(key)
    upm = f["head"].unitsPerEm
    return f["hhea"].ascent / upm, -f["hhea"].descent / upm


def width(text, key, size, spacing=0.0):
    f = tt(key)
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    upm = f["head"].unitsPerEm
    w = 0
    for ch in text:
        g = cmap.get(ord(ch)) or cmap.get(ord("?"))
        w += hmtx[g][0] / upm * size + spacing
    return w - (spacing if text else 0)


def baseline(top, line_h, key, size):
    a, d = metrics(key)
    return top + (line_h - size * (a + d)) / 2 + size * a


def wrap(text, key, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if width(trial, key, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Card:
    """Collects SVG body markup and the characters used per font."""

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.body, self.chars = [], defaultdict(set)

    def add(self, s):
        self.body.append(s)

    def text(self, x, y, s, key, size, fill, anchor="start", spacing=0, extra=""):
        self.chars[key].update(s)
        fam, style, _ = FONTS[key]
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        st = ' font-style="italic"' if style == "italic" else ""
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}"{st} font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}"{ls}{extra}>{escape(s)}</text>'
        )

    def runs(self, x, y, parts, size, extra=""):
        """parts: [(text, fontkey, fill)] laid out as tspans on one line."""
        spans = []
        for s, key, fill in parts:
            self.chars[key].update(s)
            fam, style, _ = FONTS[key]
            st = ' font-style="italic"' if style == "italic" else ""
            spans.append(f'<tspan font-family="{fam}"{st} fill="{fill}">{escape(s)}</tspan>')
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve"{extra}>{"".join(spans)}</text>')

    def font_css(self):
        css = []
        for key, chars in self.chars.items():
            if not chars:
                continue
            fam, style, file = FONTS[key]
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["*"]
            font = TTFont(os.path.join(FONT_DIR, file))
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            css.append(
                f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:400;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
            )
        return "".join(css)

    def render(self, css=""):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title>"
            f"<style>{self.font_css()}{BASE_CSS}{css}</style>"
            + "".join(self.body)
            + "</svg>"
        )


BASE_CSS = """
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes breathe{0%,100%{transform:scaleX(1)}50%{transform:scaleX(.82)}}
@keyframes pop{from{transform:scale(0)}to{transform:scale(1)}}
@keyframes rise{from{transform:translateY(40px);opacity:0}to{transform:none;opacity:1}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@keyframes spin{to{transform:rotate(360deg)}}
.ray{transform-box:fill-box;transform-origin:0% 50%;animation:grow 1.4s cubic-bezier(.2,.7,.2,1) both,breathe 5s ease-in-out infinite}
.dot{transform-box:fill-box;transform-origin:50% 50%;animation:pop .5s cubic-bezier(.3,1.6,.5,1) both}
.layer{animation:rise 1.6s cubic-bezier(.2,.7,.2,1) both}
.bob{animation:bob 6s ease-in-out infinite}
.ring{transform-box:fill-box;transform-origin:50% 50%;animation:spin 40s linear infinite}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""

RAY_GRAD = (
    '<linearGradient id="ray" x1="0" y1="0" x2="1" y2="0">'
    f'<stop offset="0" stop-color="{VIOLET}"/><stop offset=".35" stop-color="#B44FA6"/>'
    f'<stop offset=".7" stop-color="{CORAL}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>'
)
WAVE_GRADS = (
    f'<linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PLUM}"/></linearGradient>'
    f'<linearGradient id="gm" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CORAL}"/><stop offset=".7" stop-color="#8E4C8C"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
    f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CORAL}"/><stop offset=".35" stop-color="#EE7A2C"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>'
)


def frame(card, fill, radius):
    card.add(
        f'<defs><clipPath id="clip"><rect width="{card.w}" height="{card.h}" rx="{radius}"/></clipPath>'
        f"{RAY_GRAD}{WAVE_GRADS}</defs>"
    )
    card.add(f'<g clip-path="url(#clip)"><rect width="{card.w}" height="{card.h}" fill="{fill}"/>')


def close(card):
    card.add("</g>")


def link_arrow(x, y, color, size=9):
    """A small ↗ drawn as a path (the mono subset has no arrow glyph)."""
    s = size
    return (
        f'<path d="M{x:.1f},{y + s:.1f} L{x + s:.1f},{y:.1f} M{x + s * .35:.1f},{y:.1f} '
        f'L{x + s:.1f},{y:.1f} L{x + s:.1f},{y + s * .65:.1f}" fill="none" stroke="{color}" '
        f'stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


# ---------- the same seeded shapes as the design ----------
def rand(a, b):
    s = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return s - math.floor(s)


def rays(n, frm, to, r0, min_len, max_len, seed):
    out = []
    for i in range(n):
        t = i / (n - 1)
        wave = 0.5 + 0.5 * math.sin(t * 9 + seed)
        ln = min_len + (max_len - min_len) * (0.35 * wave + 0.65 * rand(i, seed))
        out.append(
            dict(angle=frm + (to - frm) * t, r0=round(r0 + rand(seed, i) * 6), len=round(ln),
                 d1=0.03 * i, d2=1.6 + 0.08 * i)
        )
    return out


def draw_rays(card, cx, cy, items, thick):
    for r in items:
        card.add(
            f'<g transform="rotate({r["angle"]:.2f} {cx} {cy})"><rect class="ray" x="{cx + r["r0"]}" '
            f'y="{cy - thick / 2}" width="{r["len"]}" height="{thick}" rx="{thick / 2}" fill="url(#ray)" '
            f'style="animation-delay:{r["d1"]:.2f}s,{r["d2"]:.2f}s"/></g>'
        )


def wave_path(w, h, base, amp, rise_, seed, step, shape=None):
    pts, x = [], 0
    while x <= w + step:
        t = x / w
        if shape:  # real monthly data, 0..1
            y = base - rise_ * shape(t) - amp * 0.35 * math.sin(t * 23 + seed * 2.3) * rand(round(x), seed)
        else:
            y = (base - rise_ * t - amp * (0.5 + 0.5 * math.sin(t * 7 + seed))
                 - amp * 0.55 * math.sin(t * 23 + seed * 2.3) * rand(round(x), seed))
        pts.append((min(x, w), max(6, y)))
        x += step
    d = f"M0,{h} L0,{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        mx = (pts[i][0] + pts[i + 1][0]) / 2
        my = (pts[i][1] + pts[i + 1][1]) / 2
        d += f" Q{pts[i][0]:.1f},{pts[i][1]:.1f} {mx:.1f},{my:.1f}"
    lx, ly = pts[-1]
    return d + f" L{lx:.1f},{ly:.1f} L{w},{h} Z"


# ---------- contribution data ----------
def fetch_calendar():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return None
    q = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
         "totalContributions weeks{contributionDays{date contributionCount}}}}}}")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cal = json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception as e:  # fall back to sample data
        print("contribution fetch failed:", e)
        return None
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return cal["totalContributions"], cal["weeks"], days


def calendar_model():
    data = fetch_calendar()
    today = dt.date.today()
    months = []
    m = today.replace(day=1)
    for _ in range(12):
        months.insert(0, m)
        m = (m - dt.timedelta(days=1)).replace(day=1)
    labels = [m.strftime("%b") for m in months]

    if not data:
        cells = []
        for c in range(53):
            for r in range(7):
                v = rand(c + 3, r) * 0.78 + (c / 53) * 0.3
                cells.append((c, r, 0 if v < .34 else 1 if v < .52 else 2 if v < .68 else 3 if v < .84 else 4))
        return dict(real=False, cells=cells, labels=labels, monthly=None,
                    stat1="sample data · refreshed daily", stat2="streak and busiest day refresh daily")

    total, weeks, days = data
    counts = sorted(d["contributionCount"] for d in days if d["contributionCount"] > 0)

    def level(n):
        if n == 0 or not counts:
            return 0
        q = [counts[int(len(counts) * p)] for p in (.25, .5, .75)]
        return 1 if n <= q[0] else 2 if n <= q[1] else 3 if n <= q[2] else 4

    cells = []
    weeks = weeks[-53:]
    for c, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday = 0
            cells.append((c, wd, level(d["contributionCount"])))

    best = cur = 0
    for d in days:
        cur = cur + 1 if d["contributionCount"] else 0
        best = max(best, cur)
    by_wd = Counter()
    for d in days:
        by_wd[dt.date.fromisoformat(d["date"]).strftime("%A")] += d["contributionCount"]
    busiest = by_wd.most_common(1)[0][0] if total else "—"

    per_month = Counter()
    for d in days:
        per_month[d["date"][:7]] += d["contributionCount"]
    monthly = [per_month.get(m.strftime("%Y-%m"), 0) for m in months]
    return dict(real=True, cells=cells, labels=labels, monthly=monthly,
                stat1=f"{total:,} contributions · refreshed daily",
                stat2=f"longest streak {best} days · busiest day {busiest}")


# ---------- cards ----------
def hero():
    c = Card(840, 340, "Nirman Patel. Intern at Quest Diagnostics, Hyderabad. I build agents, RAG systems and quantum classifiers.")
    frame(c, CREAM, 12)
    # burst on the right edge
    c.add(f'<circle class="ring" cx="840" cy="170" r="71.25" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="5 4" opacity=".55"/>')
    draw_rays(c, 840, 170, rays(44, 104, 256, 78, 110, 270, 1.3), 5)
    # annotations
    c.add(f'<circle cx="588.5" cy="68.5" r="4" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    c.add(f'<line x1="556" y1="46" x2="585.6" y2="71" stroke="{INK}" stroke-width="1"/>')
    c.text(528, 41, "dl", "mono", 11, INK)
    c.add(f'<circle cx="588.5" cy="266.5" r="4" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    c.add(f'<line x1="552" y1="296" x2="585" y2="269" stroke="{INK}" stroke-width="1"/>')
    c.text(514, 301, "qml", "mono", 11, INK)

    para = wrap("I build agents, RAG systems and quantum classifiers, and ship every one as a live demo.", "sans", 16, 440)
    block = 15 + 16 + 64 + 16 + 4 + 24 * len(para) + 16 + 16
    top = (340 - block) / 2
    c.text(44, baseline(top, 15, "mono", 11), "INTERN AT QUEST DIAGNOSTICS · HYDERABAD, IN", "mono", 11, MUTED, spacing=1.76)
    y = top + 15 + 16
    c.runs(44, baseline(y, 64, "serif", 64), [("Nirman ", "serif", INK), ("Patel", "serif-i", VIOLET)], 64, ' letter-spacing="-0.64"')
    y += 64 + 16 + 4
    for line in para:
        c.text(44, baseline(y, 24, "sans", 16), line, "sans", 16, INK2)
        y += 24
    y += 16
    url = "nirmanhere.vercel.app"
    by = baseline(y, 16, "mono", 12)
    c.text(44, by, url, "mono", 12, INK)
    c.add(link_arrow(44 + width(url, "mono", 12) + 6, by - 8.5, INK, 8))
    close(c)
    return c.render()


def heatmap(model):
    c = Card(840, 236, "Contribution graph in blue, refreshed daily")
    frame(c, CREAM, 12)
    c.runs(22, baseline(24, 31, "serif", 26), [("Contributions ", "serif", INK), ("this year", "serif-i", VIOLET)], 26)
    c.text(818, baseline(28, 15, "mono", 11), model["stat1"], "mono", 11, INK2, anchor="end")
    colw = 795 / 12
    for i, lab in enumerate(model["labels"]):
        x = 22 + i * colw
        c.add(f'<line x1="{x + .5:.1f}" y1="63" x2="{x + .5:.1f}" y2="191" stroke="{INK}" stroke-opacity=".18"/>')
        c.text(x + 5, 73, lab, "mono", 10, INK2)
    sizes = [11, 11, 12, 12, 13]
    for col, row, lvl in model["cells"]:
        cx, cy = 22 + col * 15 + 6.5, 87 + row * 15 + 6.5
        c.add(f'<circle class="dot" cx="{cx}" cy="{cy}" r="{sizes[lvl] / 2}" fill="{HEAT[lvl]}" style="animation-delay:{col * .025 + row * .01:.2f}s"/>')
    # legend, right-aligned
    ly = 236 - 14 - 7
    x = 818 - width("more", "mono", 10)
    c.text(x, ly + 3.5, "more", "mono", 10, INK)
    x -= 6
    for col in reversed(HEAT):
        x -= 10
        c.add(f'<circle cx="{x + 5}" cy="{ly}" r="5" fill="{col}"/>')
        x -= 6
    c.text(x - width("less", "mono", 10), ly + 3.5, "less", "mono", 10, INK)
    close(c)
    return c.render()


def activity(model):
    c = Card(840, 260, "Contributions over the last 12 months, month by month, with streak and busiest day")
    frame(c, CREAM, 12)
    shape = None
    if model["monthly"] and max(model["monthly"]) > 0:
        mx = max(model["monthly"])
        vals = [v / mx for v in model["monthly"]]

        def shape(t, vals=vals):
            p = t * (len(vals) - 1)
            i = min(int(p), len(vals) - 2)
            f = p - i
            f = f * f * (3 - 2 * f)
            return vals[i] * (1 - f) + vals[i + 1] * f
    layers = [
        ("gb", wave_path(840, 260, 200, 60, 120 if not shape else 170, .4, 28, shape), 0, 7, ""),
        ("gm", wave_path(840, 260, 228, 52, 90 if not shape else 130, 2.2, 24, shape), .25, 5.5, ' opacity=".95"'),
        (CORAL, wave_path(840, 260, 246, 30, 70 if not shape else 95, 4.1, 30, shape), .5, 6.5, ' opacity=".9"'),
        ("gf", wave_path(840, 260, 262, 22, 74 if not shape else 70, 5.6, 36, shape), .75, 0, ""),
    ]
    for fill, d, delay, bob, op in layers:
        f = f"url(#{fill})" if not fill.startswith("#") else fill
        path = f'<path d="{d}" fill="{f}" stroke="{INK}" stroke-width=".6"{op}/>'
        inner = f'<g class="bob" style="animation-duration:{bob}s">{path}</g>' if bob else path
        c.add(f'<g class="layer" style="animation-delay:{delay}s">{inner}</g>')
    c.runs(32, baseline(26, 31, "serif", 26), [("Activity, ", "serif", INK), ("month by month", "serif-i", INK)], 26)
    c.text(32, baseline(63, 15, "mono", 11), model["stat2"], "mono", 11, INK2)
    colw = 800 / 12
    for i, lab in enumerate(model["labels"]):
        c.text(20 + i * colw, 247, lab, "mono", 10, INK)
    close(c)
    return c.render()


def stat(name, label, bg, fg, head, body):
    c = Card(269, 236, f"{label}: {''.join(t for t, _ in head)}. {body}")
    frame(c, bg, 14)
    c.text(24, baseline(24, 16, "mono", 12), label.upper(), "mono", 12, fg, spacing=2.16)
    c.add(f'<path d="M232,32 H244 M239.5,27.5 L244,32 L239.5,36.5" fill="none" stroke="{fg}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
    y = 24 + 16 + 22
    size = 44
    while sum(width(t, "serif-i" if it else "serif", size) for t, it in head) > 221 and size > 28:
        size -= 1
    c.runs(24, baseline(y, 42, "serif", size), [(t, "serif-i" if it else "serif", fg) for t, it in head], size, f' letter-spacing="{-size / 100}"')
    y += 42 + 22
    for line in wrap(body, "sans", 14, 221):
        c.text(24, baseline(y, 21, "sans", 14), line, "sans", 14, fg)
        y += 21
    close(c)
    return name, c.render()


def title():
    c = Card(840, 60, "What I built")
    c.runs(0, 46, [("What I ", "serif", INK), ("built", "serif-i", VIOLET)], 46)
    x = width("What I ", "serif", 46) + width("built", "serif-i", 46) + 14
    for i, col in enumerate([VIOLET, CORAL, ORANGE]):
        c.add(f'<circle cx="{x + 4.5 + i * 15}" cy="41.5" r="4.5" fill="{col}"/>')
    return c.render()


def repo(name, label, proj, desc, url, motif):
    c = Card(269, 318, f"{proj}: {desc}")
    frame(c, CREAM, 12)
    motif(c)
    c.text(22, baseline(158, 15, "mono", 11), label.upper(), "mono", 11, MUTED, spacing=1.76)
    c.text(22, baseline(179, 30, "serif", 30), proj, "serif", 30, INK)
    y = 215
    for line in wrap(desc, "sans", 13, 225):
        c.text(22, baseline(y, 18.85, "sans", 13), line, "sans", 13, INK2)
        y += 18.85
    by = 318 - 18 - 3
    c.text(22, by, url, "mono", 11, LINK)
    c.add(link_arrow(22 + width(url, "mono", 11) + 5, by - 8, LINK, 7.5))
    close(c)
    return name, c.render()


def motif_dots(c):
    c.add(
        f'<defs><linearGradient id="mg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PLUM}"/>'
        f'<stop offset=".5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{CORAL}"/></linearGradient></defs>'
        '<rect width="269" height="140" fill="url(#mg)"/>'
    )
    sizes = [4, 7, 10, 13, 17]
    for col in range(12):
        for row in range(5):
            v = rand(col + 7, row) * 0.78 + (col / 12) * 0.3
            lvl = 0 if v < .34 else 1 if v < .52 else 2 if v < .68 else 3 if v < .84 else 4
            fill = f'{CREAM}" fill-opacity=".42' if lvl == 0 else CREAM
            c.add(f'<circle class="dot" cx="{15.5 + col * 20 + 9}" cy="{21 + row * 20 + 9}" r="{sizes[lvl] / 2}" fill="{fill}" style="animation-delay:{col * .06 + row * .01:.2f}s"/>')


def motif_waves(c):
    c.add(f'<rect width="269" height="140" fill="{CREAM2}"/>')
    for fill, args, delay in [("gb", (100, 30, 50, .9, 16), 0), ("gm", (122, 24, 36, 3.1, 14), .2), ("gf", (140, 14, 30, 5.2, 18), .4)]:
        base, amp, rs, seed, step = args
        c.add(f'<g class="layer" style="animation-delay:{delay}s"><path d="{wave_path(269, 140, base, amp, rs, seed, step)}" fill="url(#{fill})" stroke="{INK}" stroke-width=".5"/></g>')


def motif_burst(c):
    c.add(f'<rect width="269" height="140" fill="{CREAM2}"/>')
    c.add(f'<circle class="ring" cx="134" cy="140" r="27.4" fill="none" stroke="{INK}" stroke-width="1.2" stroke-dasharray="4 3" opacity=".6"/>')
    draw_rays(c, 134, 140, rays(26, 190, 350, 34, 34, 104, 2.1), 3)


def main():
    os.makedirs(OUT, exist_ok=True)
    model = calendar_model()
    files = {
        "hero.svg": hero(),
        "heatmap.svg": heatmap(model),
        "activity.svg": activity(model),
        "title-built-light.svg": title(),
    }
    for name, svg in [
        stat("ship.svg", "Ship", VIOLET, "#FBF4EA", [("Pest", 0), ("Pilot", 1)],
             "Ask an ERP anything in plain English. Text-to-SQL over 213 tables, with the records behind every answer."),
        stat("work.svg", "Work", "#C8432A", "#FBF4EA", [("5 ", 0), ("teams", 1)],
             "Quest Diagnostics today. Before that Seravion Connect, Assistive AI, Akai Space and Leo9 Studio."),
        stat("research.svg", "Research", "#F2C94C", "#2A1E26", [("Explainable ", 0), ("AI", 1)],
             "Multimodal models that grade Non-Alcoholic Fatty Liver Disease severity from liver ultrasound and clinical data."),
        repo("repo-orvant.svg", "hybrid rag", "Orvant",
             "Semantic + keyword retrieval to check clinical-trial eligibility.", "clinical-trials", motif_dots),
        repo("repo-rl-trading.svg", "reinforcement learning", "RL Trading Agent",
             "A PPO agent comparing stock strategies on live market data.", "rl-trading-agent", motif_waves),
        repo("repo-vqc-portal.svg", "quantum ml", "VQC Portal",
             "An interactive playground for variational quantum classifiers.", "vqc-portal", motif_burst),
    ]:
        files[name] = svg
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"{name:24s} {len(svg) / 1024:6.1f} KB")
    print("contribution data:", "live" if model["real"] else "sample")


if __name__ == "__main__":
    main()
