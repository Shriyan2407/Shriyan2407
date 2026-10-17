"""Render the live profile: animated SVG scenes + auto-updated README blocks.

Runs from .github/workflows/build.yml (every 6 hours) and after every Vault
attempt. Everything shown is pulled from the GitHub API at build time.
"""

import json
import math
import base64
import itertools
import os
import random
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

USER = "Shriyan2407"
ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "assets", "live")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MONO = "'JBM','JetBrains Mono','Cascadia Code',Consolas,'SFMono-Regular',Menlo,monospace"

# Featured case files: repo -> how it is presented.
CASES = [
    ("r-h-t-i-h", "MARKET KA BAADSHAH", "OPERATION: BULL RUN",
     "Multi-agent AI equity-research terminal for NSE & BSE. Technical + fundamental analysis, macro intel, watchlists, alerts and a decisive AI verdict.",
     "Next.js · TypeScript · Prisma · Claude API · Docker"),
    ("DOCCARE", "DOCCARE", "OPERATION: LIFELINE",
     "Healthcare operating system: records, appointments, specialists and AI insights behind one secure front door.",
     "React · Vite · JavaScript"),
    ("CIRCUIT-X", "CIRCUIT-X", "OPERATION: BLACKOUT",
     "Kill nodes, cut links, watch the network heal. Failure-recovery simulator with BFS/DFS and Dijkstra on a hand-built min-heap.",
     "Java · Graphs · DSA"),
    ("nebulavoltage", "SPACE MISSION CONTROL", "OPERATION: ORBIT",
     "Mission-ops console: crew on a custom linked list, missions on a queue, emergencies on a stack, all persisted to disk.",
     "Java · Data Structures"),
]

THEMES = {
    "dark": dict(bg="#0A0A0B", panel="#111214", line="#2A2618", text="#E9E4D4", dim="#7D7766",
                 accent="#D4AF37", accent2="#F5E6B3", ok="#3FB950", alert="#FF4D4D", grid="#16140E"),
    "light": dict(bg="#F5F2EA", panel="#FFFFFF", line="#C9CFDA", text="#16233F", dim="#6B778C",
                  accent="#1F5FD1", accent2="#0E2A5C", ok="#1A7F37", alert="#C62828", grid="#E3E7EE"),
}


# ---------------------------------------------------------------- data ----

def _req(url, data=None):
    req = urllib.request.Request(url, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def api(path):
    return _req(f"https://api.github.com{path}")


def graphql(query):
    body = json.dumps({"query": query}).encode()
    return _req("https://api.github.com/graphql", body)["data"]


def collect():
    g = graphql("""query { user(login: "%s") {
      createdAt
      contributionsCollection { totalCommitContributions
        contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } }
      repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
        totalCount nodes { name languages(first: 10) { edges { size node { name } } } } } } }""" % USER)["user"]
    days = [d for w in g["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs = {}
    for repo in g["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            if e["node"]["name"] not in ("Dockerfile", "Shell", "Batchfile", "Makefile"):
                langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    top = sorted(((n, s / total * 100) for n, s in langs.items()), key=lambda x: -x[1])[:4]
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=100")
    own = [r for r in repos if not r["fork"] and r["size"] > 0 and r["name"] != USER]
    return {
        "since": g["createdAt"][:10],
        "repos": g["repositories"]["totalCount"],
        "commits": g["contributionsCollection"]["totalCommitContributions"],
        "contribs": g["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "days": days,
        "langs": top,
        "last": own[0] if own else None,
        "repo_meta": {r["name"]: r for r in repos},
        "vault": load_json("vault.json", {"attempts": 0, "solvers": [], "last": None}),
        "shell": load_json("shell.json", {"total": 0, "users": [], "history": []}),
        "avatar": avatar(),
    }


def avatar():
    # Embedded as a data URI: images inside an <img>-loaded SVG can't fetch URLs.
    req = urllib.request.Request(f"https://avatars.githubusercontent.com/{USER}?s=300")
    with urllib.request.urlopen(req, timeout=30) as resp:
        mime = resp.headers.get_content_type() or "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(resp.read()).decode()


def load_json(name, default):
    path = os.path.join(ROOT, "data", name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def fmt_day(iso):
    return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d %b %Y")


# ------------------------------------------------------------- helpers ----

_ids = itertools.count()

def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def t(s):
    return escape(str(s), quote=True)


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + ([cur] if cur else [])



_FONT_CACHE = {}


def font_faces(weights=(400, 700, 800)):
    # JetBrains Mono (OFL), subset and embedded so every viewer sees the same type.
    faces = []
    for weight in weights:
        if weight not in _FONT_CACHE:
            with open(os.path.join(ROOT, "assets", "fonts", f"jbm-{weight}.woff2"), "rb") as f:
                _FONT_CACHE[weight] = base64.b64encode(f.read()).decode()
        faces.append(f"@font-face{{font-family:'JBM';font-weight:{weight};src:url(data:font/woff2;base64,{_FONT_CACHE[weight]}) format('woff2')}}")
    return "\n  ".join(faces)


def svg(w, h, body, c, extra_css="", weights=(400, 700, 800)):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{MONO}">
<style>
  {font_faces(weights)}
  .t{{fill:{c['text']}}} .d{{fill:{c['dim']}}} .a{{fill:{c['accent']}}} .a2{{fill:{c['accent2']}}}
  .ok{{fill:{c['ok']}}} .al{{fill:{c['alert']}}}
  .blink{{animation:blink 1s steps(1) infinite}} @keyframes blink{{50%{{opacity:0}}}}
  {extra_css}
</style>
{body}
</svg>"""


def typed(x, y, text, begin, cls="t", size=14, cps=28):
    """Text that types itself out character by character (SMIL, works inside <img>)."""
    cw = size * 0.62
    n = len(text)
    widths = ";".join(f"{i * cw:.1f}" for i in range(n + 1))
    dur = max(n / cps, 0.05)
    cid = f"ty{next(_ids)}"
    return f"""<clipPath id="{cid}"><rect x="{x}" y="{y - size}" height="{size * 1.6}" width="0">
  <animate attributeName="width" values="{widths}" calcMode="discrete" begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>
<text x="{x}" y="{y}" font-size="{size}" class="{cls}" clip-path="url(#{cid})" xml:space="preserve">{t(text)}</text>"""


def appear(inner, begin, dur=0.25):
    return f"""<g opacity="0">{inner}<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="{dur}s" fill="freeze"/></g>"""


# ---------------------------------------------------------------- hero ----

# Face position inside the 400px avatar, used for the lock-on reticle.
FACE = (158, 52, 278, 178)


def portrait(d, c, theme, px, py, size):
    """The avatar, duotoned, decrypted by a scan line, then locked by a reticle."""
    rng = random.Random(2407)
    k = size / 400
    if theme == "dark":   # deep black → warm gold, S-curve for contrast
        r, g, b = "0.03 0.09 0.42 0.86 1", "0.03 0.07 0.33 0.72 0.95", "0.035 0.04 0.10 0.33 0.70"
        lock = c["accent"]
    else:                 # ink navy → paper
        r, g, b = "0.04 0.09 0.30 0.76 0.97", "0.10 0.19 0.42 0.83 0.96", "0.25 0.38 0.62 0.90 0.94"
        lock = c["alert"]
    o = [f'''<filter id="duo" color-interpolation-filters="sRGB">
  <feColorMatrix type="saturate" values="0"/>
  <feComponentTransfer><feFuncR type="table" tableValues="{r}"/><feFuncG type="table" tableValues="{g}"/><feFuncB type="table" tableValues="{b}"/></feComponentTransfer>
</filter>
<pattern id="psl" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1" fill="#000" opacity=".28"/></pattern>
<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["accent"]}" stop-opacity="0"/><stop offset=".85" stop-color="{c["accent"]}" stop-opacity=".22"/><stop offset="1" stop-color="{c["accent2"]}" stop-opacity=".9"/></linearGradient>
<clipPath id="shown"><rect x="{px}" y="{py}" width="{size}" height="0"><animate attributeName="height" from="0" to="{size}" begin="0.7s" dur="2.4s" fill="freeze"/></rect></clipPath>
<clipPath id="hidden"><rect x="{px}" y="{py}" width="{size}" height="{size}"><animate attributeName="y" from="{py}" to="{py + size}" begin="0.7s" dur="2.4s" fill="freeze"/></rect></clipPath>
<clipPath id="frame"><rect x="{px}" y="{py}" width="{size}" height="{size}" rx="4"/></clipPath>
<defs><image id="av" href="{d["avatar"]}" x="{px}" y="{py}" width="{size}" height="{size}"/></defs>''',
         f'<rect x="{px}" y="{py}" width="{size}" height="{size}" rx="4" fill="{c["panel"]}"/>',
         f'<g clip-path="url(#frame)"><use href="#av" filter="url(#duo)" clip-path="url(#shown)"/>',
         f'<rect x="{px}" y="{py}" width="{size}" height="{size}" fill="url(#psl)" clip-path="url(#shown)"/>']
    # glitch slices that tear sideways every few seconds once revealed
    for i, (sy, sh, dx, col) in enumerate(((0.31, 0.045, 9, "#FF2E63"), (0.56, 0.03, -11, "#08F7FE"), (0.74, 0.055, 7, c["accent"]))):
        o.append(f'<clipPath id="sl{i}"><rect x="{px}" y="{py + size * sy:.0f}" width="{size}" height="{size * sh:.0f}"/></clipPath>'
                 f'<g clip-path="url(#sl{i})" opacity="0"><use href="#av" x="{dx}" filter="url(#duo)"/>'
                 f'<rect x="{px}" y="{py}" width="{size}" height="{size}" fill="{col}" opacity=".35"/>'
                 f'<animate attributeName="opacity" values="0;0;1;0;1;0;0" keyTimes="0;.86;.88;.9;.92;.94;1" dur="{5 + i * 1.3:.1f}s" begin="4s" repeatCount="indefinite"/></g>')
    # cipher layer over the part not yet decrypted
    rows, cols = size // 12, int(size / 6.0)
    for phase in (0, 1):
        lines = "".join(f'<text x="{px + 4}" y="{py + 11 + r_ * 12}" font-size="10">{"".join(rng.choice("0123456789abcdef#$%@*") for _ in range(cols))}</text>'
                        for r_ in range(rows))
        o.append(f'<g clip-path="url(#hidden)" fill="{c["accent"]}" opacity=".5"><g>{lines}'
                 f'<animate attributeName="opacity" values="{"1;0" if phase == 0 else "0;1"}" dur=".24s" calcMode="discrete" repeatCount="indefinite"/></g></g>')
    # the decrypt sweep, then a soft re-scan every 7s
    o.append(f'<rect x="{px}" y="{py - 40}" width="{size}" height="42" fill="url(#band)" opacity="0">'
             f'<animate attributeName="y" from="{py - 40}" to="{py + size - 40}" begin="0.7s" dur="2.4s" fill="freeze"/>'
             f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.03;.96;1" begin="0.7s" dur="2.4s" fill="freeze"/></rect>')
    o.append(f'<rect x="{px}" y="{py - 40}" width="{size}" height="42" fill="url(#band)" opacity="0">'
             f'<animate attributeName="y" values="{py - 40};{py + size}" dur="2.2s" begin="6s;rs.end+4.8s" id="rs"/>'
             f'<animate attributeName="opacity" values="0;.45;.45;0" keyTimes="0;.1;.9;1" dur="2.2s" begin="6s;rs.end+4.8s"/></rect>')
    o.append("</g>")
    o.append(f'<rect x="{px + .5}" y="{py + .5}" width="{size - 1}" height="{size - 1}" rx="4" fill="none" stroke="{c["line"]}"/>')

    # reticle: four corners fly from the frame onto the face
    fx0, fy0 = px + FACE[0] * k, py + FACE[1] * k
    fx1, fy1 = px + FACE[2] * k, py + FACE[3] * k
    arm = 12
    corners = (((px, py), (fx0, fy0), (1, 1)), ((px + size, py), (fx1, fy0), (-1, 1)),
               ((px, py + size), (fx0, fy1), (1, -1)), ((px + size, py + size), (fx1, fy1), (-1, -1)))
    for (sx, sy), (ex, ey), (dx, dy) in corners:
        o.append(f'<g opacity="0"><set attributeName="opacity" to="1" begin="3.2s"/>'
                 f'<path d="M0 {arm * dy} V0 H{arm * dx}" fill="none" stroke="{lock}" stroke-width="2.5"/>'
                 f'<animateTransform attributeName="transform" type="translate" from="{sx} {sy}" to="{ex:.1f} {ey:.1f}" begin="3.2s" dur=".55s" fill="freeze" calcMode="spline" keySplines=".2 .9 .2 1" keyTimes="0;1"/></g>')
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    o.append(appear(f'<path d="M{cx - 5:.1f} {cy:.1f} H{cx + 5:.1f} M{cx:.1f} {cy - 5:.1f} V{cy + 5:.1f}" stroke="{lock}" stroke-width="1" opacity=".7"/>'
                    f'<rect x="{fx0:.1f}" y="{fy0 - 21:.1f}" width="{fx1 - fx0:.1f}" height="16" fill="{lock}"/>'
                    f'<text x="{fx0 + 5:.1f}" y="{fy0 - 9:.1f}" font-size="9.5" font-weight="800" fill="{c["bg"]}">MATCH 98.7%</text>'
                    f'<rect x="{fx0:.1f}" y="{fy1 + 5:.1f}" width="{fx1 - fx0:.1f}" height="14" fill="{c["bg"]}" opacity=".82"/>'
                    f'<text x="{fx0 + 5:.1f}" y="{fy1 + 15:.1f}" font-size="9" font-weight="700" fill="{lock}">ID SB-2407 · LOCKED</text>', 3.75, 0.12))
    # frame brackets
    for bx, by, sx, sy in ((px, py, 1, 1), (px + size, py, -1, 1), (px, py + size, 1, -1), (px + size, py + size, -1, -1)):
        o.append(f'<path d="M{bx - 6 * sx} {by + 22 * sy} V{by - 6 * sy} H{bx + 22 * sx}" fill="none" stroke="{c["accent"]}" stroke-width="2"/>')
    return "\n".join(o)


def decrypt_word(word, x, y, size, begin, fill, frames=7):
    """Each letter cycles through random glyphs before locking into place."""
    rng = random.Random(word)
    adv = size * 0.6  # JetBrains Mono advance width
    out = []
    for i, ch in enumerate(word):
        lx = x + i * adv
        t0 = begin + i * 0.07
        for f in range(frames):
            g = rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%@&*")
            out.append(f'<text x="{lx:.1f}" y="{y}" font-size="{size}" font-weight="800" fill="{fill}" opacity="0">{t(g)}'
                       f'<set attributeName="opacity" to=".55" begin="{t0 + f * 0.055:.3f}s" dur=".055s"/></text>')
        out.append(f'<text x="{lx:.1f}" y="{y}" font-size="{size}" font-weight="800" fill="url(#gold)" opacity="0">{t(ch)}'
                   f'<set attributeName="opacity" to="1" begin="{t0 + frames * 0.055:.3f}s"/></text>')
    return "".join(out), begin + len(word) * 0.07 + frames * 0.055


def led_meter(x, y, pct, begin, c, segs=32):
    lit = max(1, round(pct / 100 * segs))
    out = []
    for j in range(segs):
        sx = x + j * 10
        if j < lit:
            out.append(f'<rect x="{sx}" y="{y - 10}" width="7" height="11" rx="1" fill="{c["accent"]}" opacity="0">'
                       f'<set attributeName="opacity" to="1" begin="{begin + j * 0.025:.3f}s"/></rect>')
        else:
            out.append(f'<rect x="{sx}" y="{y - 10}" width="7" height="11" rx="1" fill="{c["grid"]}" stroke="{c["line"]}" stroke-width=".6"/>')
    return "".join(out)


def hero_dark(d, c):
    w, h = 880, 560
    v, sh, last = d["vault"], d["shell"], d["last"]
    o = [f'<radialGradient id="vig" cx=".5" cy=".45" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>',
         f'<linearGradient id="crt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["accent"]}" stop-opacity="0"/><stop offset=".5" stop-color="{c["accent"]}" stop-opacity=".045"/><stop offset="1" stop-color="{c["accent"]}" stop-opacity="0"/></linearGradient>',
         f'<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFF4CC"/><stop offset=".45" stop-color="{c["accent2"]}"/><stop offset=".55" stop-color="{c["accent"]}"/><stop offset="1" stop-color="#9C7A12"/></linearGradient>',
         f'<filter id="glow" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="6"/></filter>',
         f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<pattern id="sl" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{c["grid"]}"/></pattern>'
         f'<rect width="{w}" height="{h}" rx="14" fill="url(#sl)" opacity=".6"/>',
         # CRT refresh band rolling down the screen
         f'<rect x="0" y="-160" width="{w}" height="160" fill="url(#crt)"><animate attributeName="y" values="-160;{h}" dur="7s" repeatCount="indefinite"/></rect>',
         f'<rect width="{w}" height="38" rx="14" fill="{c["panel"]}"/><rect y="24" width="{w}" height="14" fill="{c["panel"]}"/>',
         f'<line x1="0" x2="{w}" y1="38" y2="38" stroke="{c["line"]}"/>']
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        o.append(f'<circle cx="{24 + i * 20}" cy="19" r="6" fill="{col}"/>')
    o.append(f'<text x="{w / 2}" y="24" font-size="12" class="d" text-anchor="middle">guest@shriyan: ~ — ssh — end-to-end encrypted</text>')
    o.append(f'<text x="{w - 22}" y="24" font-size="11" class="al" text-anchor="end" font-weight="700"><tspan class="blink">●</tspan> REC</text>')

    # left column: portrait + identity HUD
    px, py, size = 30, 62, 280
    o.append(portrait(d, c, "dark", px, py, size))
    hy = py + size + 30
    hud = [("SUBJECT", "SHRIYAN BOHRA", "a2"), ("ORIGIN", "INDIA · UTC+05:30", "a2"),
           ("CLEARANCE", "PUBLIC · LEVEL 5", "a2"), ("STATUS", "ONLINE · BUILDING", "ok")]
    for i, (k_, val, cls) in enumerate(hud):
        o.append(appear(f'<text x="{px}" y="{hy + i * 21}" font-size="10" class="d" letter-spacing="1.8">{k_}</text>'
                        f'<text x="{px + 92}" y="{hy + i * 21}" font-size="12" font-weight="700" class="{cls}">{t(val)}</text>', 4.0 + i * 0.12))
    uy = hy + 4 * 21 + 8
    bars = "".join(f'<rect x="{px + 92 + j * 9}" y="{uy - 9 - j * 1.5:.1f}" width="6" height="{10 + j * 1.5:.1f}" fill="{c["ok"] if j < 4 else c["line"]}">'
                   + (f'<animate attributeName="opacity" values="1;.35;1" dur="{1.1 + j * .2:.1f}s" repeatCount="indefinite"/>' if j < 4 else "") + '</rect>'
                   for j in range(5))
    o.append(appear(f'<text x="{px}" y="{uy}" font-size="10" class="d" letter-spacing="1.8">UPLINK</text>{bars}'
                    f'<text x="{px + 145}" y="{uy}" font-size="11" class="d">secure · 24ms</text>', 4.6))

    # right column: the session
    x, tm = 342, 0.5
    o.append(typed(x, 72, "$ ssh guest@github.com/Shriyan2407", tm, "a", 13))
    tm += 1.3
    o.append(appear(f'<text x="{x}" y="93" font-size="12" class="ok">[✓] handshake ok · TLS 1.3 · AES-256-GCM · key pinned</text>', tm))
    tm += 0.4
    o.append(typed(x, 124, "$ whoami", tm, "a", 13))
    tm += 0.5
    # name: glow underlay + per-letter decrypt + RGB-split bursts
    for j, word in enumerate(("SHRIYAN", "BOHRA")):
        wy = 186 + j * 62
        o.append(f'<text x="{x}" y="{wy}" font-size="62" font-weight="800" fill="{c["accent"]}" opacity="0" filter="url(#glow)">{word}'
                 f'<animate attributeName="opacity" from="0" to=".35" begin="{tm + 0.7 + j * 0.3:.2f}s" dur=".6s" fill="freeze"/></text>')
        letters, end = decrypt_word(word, x, wy, 62, tm + j * 0.25, c["accent"])
        o.append(letters)
        for col, dx in (("#FF2E63", -4), ("#08F7FE", 4)):
            o.append(f'<text x="{x + dx}" y="{wy}" font-size="62" font-weight="800" fill="{col}" opacity="0" style="mix-blend-mode:screen">{word}'
                     f'<animate attributeName="opacity" values="0;0;.75;0;.6;0;0" keyTimes="0;.88;.895;.91;.925;.94;1" dur="{4.2 + j * 0.9 + (dx > 0) * 0.4:.1f}s" begin="{end + 1:.2f}s" repeatCount="indefinite"/></text>')
    tm += 1.6
    o.append(appear(f'<text x="{x}" y="276" font-size="12" class="d">cse student · offensive mind, defensive design · full-stack</text>', tm))
    tm += 0.4
    o.append(typed(x, 308, "$ ./recon --target=self", tm, "a", 13))
    tm += 1.0
    o.append(appear(f'<text x="{x}" y="330" font-size="12" class="t" xml:space="preserve">repos <tspan class="a2" font-weight="700">{d["repos"]}</tspan>  ·  commits/yr <tspan class="a2" font-weight="700">{d["commits"]}</tspan>  ·  contributions/yr <tspan class="a2" font-weight="700">{d["contribs"]}</tspan></text>', tm))
    if last:
        o.append(appear(f'<text x="{x}" y="350" font-size="12" class="d">last push → <tspan class="a2">{t(last["name"])}</tspan> · {fmt_day(last["pushed_at"])}</text>', tm + 0.15))
    tm += 0.35
    for i, (lang, pct) in enumerate(d["langs"]):
        ly = 384 + i * 23
        o.append(appear(f'<text x="{x}" y="{ly}" font-size="12" class="t">{t(lang)}</text>'
                        f'<text x="{x + 476}" y="{ly}" font-size="11" class="d" text-anchor="end">{pct:.1f}%</text>', tm + 0.1 * i))
        o.append(appear(led_meter(x + 100, ly, pct, tm + 0.1 * i, c), tm + 0.1 * i, 0.1))
    tm += 1.2
    solved = len(v["solvers"])
    state = f'<tspan class="al" font-weight="700">BREACHED ×{solved}</tspan>' if solved else '<tspan class="ok" font-weight="700">SECURE</tspan>'
    o.append(appear(f'<text x="{x}" y="484" font-size="12" class="t">vault {state} · {plural(v["attempts"], "attempt")} · shell {plural(sh["total"], "cmd")} by {plural(len(sh["users"]), "visitor")}</text>', tm))
    tm += 0.3
    o.append(appear(f'<text x="{x}" y="510" font-size="13" class="a">guest@shriyan:~$ <tspan class="blink">█</tspan></text>', tm))
    o.append(f'<rect width="{w}" height="{h}" rx="14" fill="url(#vig)" pointer-events="none"/>')
    o.append(f'<line x1="22" x2="{w - 22}" y1="{h - 30}" y2="{h - 30}" stroke="{c["line"]}"/>')
    o.append(f'<text x="30" y="{h - 11}" font-size="10.5" class="al" font-weight="700" letter-spacing="1">◆ RED TEAM VIEW</text>')
    o.append(f'<text x="{w - 30}" y="{h - 11}" font-size="10.5" class="d" text-anchor="end">same mind // different perspective · switch GitHub to light theme</text>')
    o.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>')
    return svg(w, h, "\n".join(o), c)


def hero_light(d, c):
    w, h = 880, 600
    v, sh = d["vault"], d["shell"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<pattern id="gr" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="{c["grid"]}"/></pattern>'
         f'<rect width="{w}" height="{h}" rx="14" fill="url(#gr)"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>',
         f'<rect width="{w}" height="44" rx="14" fill="{c["accent2"]}"/><rect y="30" width="{w}" height="14" fill="{c["accent2"]}"/>',
         f'<text x="28" y="28" font-size="13" font-weight="700" fill="#FFFFFF" letter-spacing="2">THREAT ASSESSMENT // SUBJECT PROFILE</text>',
         f'<text x="{w - 28}" y="28" font-size="12" fill="#AFC3E8" text-anchor="end">REF SB-2407 · GENERATED {datetime.now(timezone.utc).strftime("%d %b %Y").upper()}</text>']
    px, py, size = 28, 70, 300
    o.append(portrait(d, c, "light", px, py, size))
    o.append(appear(f'<text x="{px}" y="{py + size + 22}" font-size="10" class="d" letter-spacing="1.5">FIG. 1 — SUBJECT IMAGE, RECONSTRUCTED</text>', 3.4))
    o.append(f'<g opacity="0" transform="rotate(-10 {px + 230} {py + size + 50})"><rect x="{px + 150}" y="{py + size + 30}" width="170" height="46" rx="6" fill="none" stroke="{c["alert"]}" stroke-width="3"/>'
             f'<text x="{px + 235}" y="{py + size + 62}" font-size="22" font-weight="800" fill="{c["alert"]}" text-anchor="middle" letter-spacing="4">CLEARED</text>'
             f'<animate attributeName="opacity" from="0" to=".85" begin="4.2s" dur=".15s" fill="freeze"/></g>')
    x = 360
    o.append(appear(f'<text x="{x}" y="88" font-size="11" class="d" letter-spacing="2">SUBJECT</text>', 0.2))
    o.append(appear(f'<text x="{x}" y="130" font-size="42" font-weight="800" fill="{c["accent2"]}">SHRIYAN BOHRA</text>', 0.4, 0.6))
    o.append(appear(f'<text x="{x}" y="156" font-size="12" class="a">class: BUILDER · threat LOW · output CRITICAL</text>', 0.9))
    fields = [("ROLE", "CSE student / developer"), ("FOCUS", "security · full-stack · AI"),
              ("BASE", "India"), ("ACTIVE SINCE", fmt_day(d["since"])),
              ("PUBLIC REPOS", str(d["repos"])), ("CONTRIBUTIONS/YR", str(d["contribs"])),
              ("VAULT", f"{len(v['solvers'])} breach / {v['attempts']} tries"), ("SHELL", f"{sh['total']} cmds · {len(sh['users'])} visitors")]
    for i, (k, val) in enumerate(fields):
        fx = x + (i % 2) * 250
        fy = 196 + (i // 2) * 48
        o.append(appear(f'<text x="{fx}" y="{fy}" font-size="10" class="d" letter-spacing="1.5">{k}</text>'
                        f'<text x="{fx}" y="{fy + 20}" font-size="14" class="t" font-weight="600">{t(val)}</text>'
                        f'<line x1="{fx}" x2="{fx + 225}" y1="{fy + 28}" y2="{fy + 28}" stroke="{c["line"]}"/>', 1.1 + i * 0.12))
    ly = 404
    o.append(appear(f'<text x="{x}" y="{ly}" font-size="10" class="d" letter-spacing="1.5">CAPABILITY SIGNATURE</text>', 2.0))
    for i, (lang, pct) in enumerate(d["langs"]):
        lyy = ly + 26 + i * 24
        bw = 300
        o.append(appear(
            f'<text x="{x}" y="{lyy}" font-size="12" class="t">{t(lang)}</text>'
            f'<rect x="{x + 100}" y="{lyy - 9}" width="{bw}" height="8" rx="4" fill="{c["grid"]}"/>'
            f'<rect x="{x + 100}" y="{lyy - 9}" width="0" height="8" rx="4" fill="{c["accent"]}">'
            f'<animate attributeName="width" from="0" to="{max(pct / 100 * bw, 3):.1f}" begin="{2.1 + i * 0.1:.2f}s" dur="1s" fill="freeze"/></rect>'
            f'<text x="{x + 410}" y="{lyy}" font-size="10" class="d">{pct:.1f}%</text>', 2.1 + i * 0.1))
    o.append(f'<line x1="22" x2="{w - 22}" y1="{h - 38}" y2="{h - 38}" stroke="{c["line"]}"/>')
    o.append(f'<text x="30" y="{h - 16}" font-size="11" class="a" font-weight="700">◆ BLUE TEAM VIEW</text>')
    o.append(f'<text x="{w - 30}" y="{h - 16}" font-size="11" class="d" text-anchor="end">same mind // different perspective — switch GitHub to dark theme ☾</text>')
    return svg(w, h, "\n".join(o), c)


# --------------------------------------------------------------- shell ----


def shell_scene(d, c, theme):
    w = 880
    sh = d["shell"]
    dark = theme == "dark"
    bg, bar = (c["bg"], c["panel"]) if dark else ("#0F1729", "#16223A")
    acc = c["accent"] if dark else "#79A8FF"
    txt = c["text"] if dark else "#DCE6F7"
    dim = c["dim"] if dark else "#7D8BA5"
    green = "#3FB950"
    entries = sh["history"][-4:]
    y = 64
    body = []
    if not entries:
        body.append(appear(f'<text x="26" y="{y + 18}" font-size="30" font-weight="800" fill="{acc}" letter-spacing="1">shriyan-os</text>'
                           f'<text x="230" y="{y + 18}" font-size="12" fill="{dim}">v1.0 · multiplayer edition · tty1</text>', 0.2))
        y += 52
        motd = [("→", "this terminal is shared by everyone who visits this profile."),
                ("→", "click any command below and its output opens instantly."),
                ("→", "the gold key runs one for real: a bot puts your @username up here."),
                ("→", "there are hidden files. `help` won't list everything.")]
        for i, (m, line) in enumerate(motd):
            body.append(appear(f'<text x="26" y="{y}" font-size="13" xml:space="preserve"><tspan fill="{acc}">{m}</tspan> <tspan fill="{txt}">{t(line)}</tspan></text>', 0.5 + i * 0.15))
            y += 22
        y += 8
        body.append(appear(f'<text x="26" y="{y}" font-size="13" font-weight="700" fill="{acc}">no one has connected yet. be the first name on this screen.</text>', 1.1))
        y += 30
    else:
        n = 0
        for e in entries:
            body.append(appear(f'<text x="26" y="{y}" font-size="13" xml:space="preserve"><tspan fill="{green}" font-weight="700">@{t(e["login"])}</tspan>'
                               f'<tspan fill="{dim}">@shriyan:~$ </tspan><tspan fill="{acc}" font-weight="700">{t(e["display"])}</tspan></text>', 0.3 + n * 0.06, 0.15))
            y += 19
            n += 1
            out = e["out"][:5] + ([f"… {len(e['out']) - 5} more lines in the issue"] if len(e["out"]) > 5 else [])
            for j, line in enumerate(out):
                faded = j == 5
                body.append(appear(f'<text x="26" y="{y}" font-size="12.5" fill="{dim if faded else txt}" xml:space="preserve">{t(line)}</text>', 0.3 + n * 0.06, 0.15))
                y += 18
                n += 1
            y += 8
        y += 6
    body.append(appear(f'<text x="26" y="{y}" font-size="13" xml:space="preserve"><tspan fill="{green}" font-weight="700">@you</tspan>'
                       f'<tspan fill="{dim}">@shriyan:~$ </tspan><tspan fill="{acc}" class="blink">█</tspan></text>', 1.3))
    y += 22
    h = y + 30
    last = sh["history"][-1] if sh["history"] else None
    right = f"last: @{last['login']} · {fmt_day(last['at'])}" if last else "waiting for the first visitor"
    o = [f'<rect width="{w}" height="{h}" rx="12" fill="{bg}"/>',
         f'<pattern id="ssl" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#FFFFFF" opacity=".018"/></pattern>',
         f'<rect width="{w}" height="{h}" rx="12" fill="url(#ssl)"/>',
         f'<rect width="{w}" height="36" rx="12" fill="{bar}"/><rect y="24" width="{w}" height="12" fill="{bar}"/>',
         f'<line x1="0" x2="{w}" y1="36" y2="36" stroke="{c["line"] if dark else "#24324F"}"/>']
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        o.append(f'<circle cx="{22 + i * 18}" cy="18" r="5.5" fill="{col}"/>')
    o.append(f'<text x="{w / 2}" y="23" font-size="12" fill="{dim}" text-anchor="middle">guest@shriyan: ~ — shared session</text>')
    o.append(f'<text x="{w - 20}" y="23" font-size="11" font-weight="700" fill="{green}" text-anchor="end"><tspan class="blink">●</tspan> LIVE</text>')
    o += body
    # tmux-style status line
    sy = h - 26
    o.append(f'<path d="M0 {sy} H{w} V{h - 12} Q{w} {h} {w - 12} {h} H12 Q0 {h} 0 {h - 12} Z" fill="{bar}"/>')
    o.append(f'<path d="M0 {sy} H150 V{h} H12 Q0 {h} 0 {h - 12} Z" fill="{acc}"/>')
    o.append(f'<text x="14" y="{sy + 17}" font-size="11" font-weight="800" fill="{bg}">[tty1] shriyan-os</text>')
    o.append(f'<text x="170" y="{sy + 17}" font-size="11" fill="{txt}">{plural(sh["total"], "command")} · {plural(len(sh["users"]), "visitor")}</text>')
    o.append(f'<text x="{w - 16}" y="{sy + 17}" font-size="11" fill="{dim}" text-anchor="end">{t(right)}</text>')
    o.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="{c["line"] if dark else "#24324F"}"/>')
    return svg(w, h, "\n".join(o), c)


# --------------------------------------------------------------- pulse ----


def pulse(d, c, theme):
    w, h = 880, 236
    dark = theme == "dark"
    days = d["days"][-60:]
    counts = [x["contributionCount"] for x in days]
    peak = max(counts) or 1
    x0, x1, top, bot = 24, 628, 50, 190
    base = 140
    step = (x1 - x0) / len(days)
    pts = [f"M{x0} {base}"]
    for i, n in enumerate(counts):
        a = x0 + i * step
        if n == 0:
            pts.append(f"L{a + step:.1f} {base}")
            continue
        amp = (base - top - 6) * (0.22 + 0.78 * math.sqrt(n / peak))
        # P wave, QRS complex, T wave
        pts += [f"L{a + step * .10:.1f} {base}", f"Q{a + step * .17:.1f} {base - 5} {a + step * .24:.1f} {base}",
                f"L{a + step * .33:.1f} {base + 4}", f"L{a + step * .43:.1f} {base - amp:.1f}",
                f"L{a + step * .53:.1f} {base + amp * .28 + 4:.1f}", f"L{a + step * .62:.1f} {base}",
                f"Q{a + step * .78:.1f} {base - 9} {a + step * .92:.1f} {base}", f"L{a + step:.1f} {base}"]
    path = " ".join(pts)
    last30 = sum(counts[-30:])
    active = sum(1 for n in counts if n)
    alive = last30 > 0
    trace = c["accent"] if dark else c["alert"]
    cyan = "#08F7FE" if dark else c["accent"]
    grid_minor = c["grid"]
    grid_major = c["line"]
    dur = 6
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<pattern id="gmin" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M6 0H0V6" fill="none" stroke="{grid_minor}" stroke-width=".6"/></pattern>',
         f'<pattern id="gmaj" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="{grid_major}" stroke-width=".8" opacity=".6"/></pattern>',
         f'<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
         f'<linearGradient id="scan" x1="0" x2="1"><stop offset="0" stop-color="{trace}" stop-opacity="0"/><stop offset="1" stop-color="{trace}" stop-opacity=".35"/></linearGradient>',
         f'<clipPath id="rev"><rect x="{x0}" y="{top - 10}" width="0" height="{bot - top + 20}">'
         f'<animate attributeName="width" values="0;{x1 - x0}" dur="{dur}s" repeatCount="indefinite"/></rect></clipPath>',
         f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="{bot - top}" fill="url(#gmin)"/>',
         f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="{bot - top}" fill="url(#gmaj)"/>',
         f'<path d="{path}" fill="none" stroke="{trace}" stroke-opacity=".16" stroke-width="1.6" stroke-linejoin="round"/>',
         f'<path d="{path}" fill="none" stroke="{trace}" stroke-width="2" stroke-linejoin="round" filter="url(#glow)" clip-path="url(#rev)"/>',
         f'<rect x="{x0 - 40}" y="{top}" width="40" height="{bot - top}" fill="url(#scan)">'
         f'<animate attributeName="x" values="{x0 - 40};{x1 - 40}" dur="{dur}s" repeatCount="indefinite"/></rect>',
         f'<rect x="{x0}" y="{top}" width="2" height="{bot - top}" fill="{trace}" opacity=".9">'
         f'<animate attributeName="x" values="{x0};{x1}" dur="{dur}s" repeatCount="indefinite"/></rect>']
    # date axis
    for i in range(0, len(days), 10):
        tx = x0 + i * step
        o.append(f'<line x1="{tx:.1f}" x2="{tx:.1f}" y1="{bot}" y2="{bot + 5}" stroke="{c["dim"]}"/>'
                 f'<text x="{tx:.1f}" y="{bot + 18}" font-size="10" class="d">{fmt_day(days[i]["date"])[:6]}</text>')
    o.append(f'<text x="{x1}" y="{bot + 18}" font-size="10" class="d" text-anchor="end">today</text>')
    # header
    o.append(f'<circle cx="32" cy="27" r="4.5" fill="{c["alert"]}"><animate attributeName="opacity" values="1;.2;1" dur=".9s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="44" y="31" font-size="12" font-weight="800" class="a" letter-spacing="2.5">SYSTEM VITALS</text>')
    o.append(f'<text x="{x1}" y="31" font-size="10.5" class="d" text-anchor="end">lead II · contribution activity · 60 days · @{USER}</text>')
    # readouts panel
    px = 652
    o.append(f'<line x1="{px - 8}" x2="{px - 8}" y1="20" y2="{h - 20}" stroke="{c["line"]}"/>')
    o.append(f'<text x="{px + 8}" y="40" font-size="10" class="d" letter-spacing="1.5">HR · CONTRIBUTIONS / 30D</text>')
    o.append(f'<text x="{px + 6}" y="96" font-size="56" font-weight="800" fill="{trace}" filter="url(#glow)">{last30}</text>')
    o.append(f'<text x="{w - 22}" y="62" font-size="18" fill="{c["alert"]}" text-anchor="end">♥<animate attributeName="opacity" values="1;.25;1" dur=".9s" repeatCount="indefinite"/></text>')
    o.append(f'<line x1="{px + 8}" x2="{w - 22}" y1="114" y2="114" stroke="{c["line"]}"/>')
    o.append(f'<text x="{px + 8}" y="134" font-size="10" class="d" letter-spacing="1.5">ACTIVE</text>'
             f'<text x="{px + 8}" y="162" font-size="24" font-weight="800" fill="{cyan}">{active}<tspan font-size="13" class="d">/60</tspan></text>')
    o.append(f'<text x="{px + 112}" y="134" font-size="10" class="d" letter-spacing="1.5">PEAK/DAY</text>'
             f'<text x="{px + 112}" y="162" font-size="24" font-weight="800" class="ok">{peak}</text>')
    pill = c["ok"] if alive else c["alert"]
    label = "● ALIVE · STABLE" if alive else "● FLATLINE"
    o.append(f'<rect x="{px + 8}" y="182" width="{w - 22 - px - 8}" height="26" rx="5" fill="none" stroke="{pill}" stroke-width="1.5"/>'
             f'<text x="{(px + 8 + w - 22) / 2:.0f}" y="199" font-size="11.5" font-weight="800" fill="{pill}" text-anchor="middle" letter-spacing="1.5">{label}</text>')
    o.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>')
    return svg(w, h, "\n".join(o), c)


# --------------------------------------------------------------- vault ----

def vault(d, c, theme):
    w, h = 880, 220
    v = d["vault"]
    solved = len(v["solvers"])
    cx, cy, r = 120, 110, 78
    ring = c["accent"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{r + 10}" fill="{c["panel"]}" stroke="{c["line"]}" stroke-width="2"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ring}" stroke-width="3"/>']
    ticks = "".join(
        f'<line x1="{cx}" y1="{cy - r + 4}" x2="{cx}" y2="{cy - r + (14 if k % 5 == 0 else 8)}" stroke="{ring}" stroke-width="{2 if k % 5 == 0 else 1}" transform="rotate({k * 6} {cx} {cy})"/>'
        for k in range(60))
    o.append(f'<g>{ticks}<animateTransform attributeName="transform" type="rotate" values="0 {cx} {cy};140 {cx} {cy};40 {cx} {cy};260 {cx} {cy};0 {cx} {cy}" '
             f'keyTimes="0;.25;.5;.75;1" dur="9s" repeatCount="indefinite" calcMode="spline" keySplines=".6 0 .2 1;.6 0 .2 1;.6 0 .2 1;.6 0 .2 1"/></g>')
    for k in range(4):
        o.append(f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r + 22}" stroke="{c["dim"]}" stroke-width="5" stroke-linecap="round" transform="rotate({k * 90 + 45} {cx} {cy})"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="16" fill="{c["bg"]}" stroke="{ring}" stroke-width="3"/>')
    light = c["alert"] if solved else c["ok"]
    o.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{light}"><animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle>')

    x = 250
    head = f"BREACHED ×{solved}" if solved else "SECURE"
    o.append(f'<text x="{x}" y="52" font-size="12" class="d" letter-spacing="2">THE VAULT · STATUS</text>')
    o.append(f'<text x="{x}" y="94" font-size="38" font-weight="800" class="{"al" if solved else "ok"}">{head}</text>')
    o.append(f'<text x="{x}" y="128" font-size="14" class="t">attempts <tspan class="a" font-weight="700">{v["attempts"]}</tspan>'
             f'   ·   cracked by <tspan class="a" font-weight="700">{solved}</tspan>'
             f'   ·   success rate <tspan class="a" font-weight="700">{(solved / v["attempts"] * 100 if v["attempts"] else 0):.1f}%</tspan></text>')
    last = v.get("last")
    if last:
        res = '<tspan class="ok">ACCESS GRANTED</tspan>' if last["ok"] else '<tspan class="al">ACCESS DENIED</tspan>'
        o.append(f'<text x="{x}" y="158" font-size="13" class="d">last attempt: @{t(last["login"])} · {fmt_day(last["at"])} · {res}</text>')
    else:
        o.append(f'<text x="{x}" y="158" font-size="13" class="d">no one has tried yet. be the first name in the log.</text>')
    o.append(f'<text x="{x}" y="190" font-size="12" class="a">3 layers of encoding · 1 key · 0 shortcuts</text>'
             f'<text x="{w - 30}" y="190" font-size="12" class="a blink" text-anchor="end">▼ intercepted transmission below</text>')
    return svg(w, h, "\n".join(o), c)


# ---------------------------------------------------------- case files ----

def case_file(idx, case, meta, c):
    repo, title, codename, desc, stack = case
    w, h = 430, 250
    live = bool(meta.get("homepage"))
    o = [f'<rect width="{w}" height="{h}" rx="12" fill="{c["panel"]}"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="{c["line"]}"/>',
         f'<path d="M0 12 Q0 0 12 0 H150 L166 18 H{w - 12} Q{w} 18 {w} 30 V34 H0 Z" fill="{c["line"]}" opacity=".7"/>',
         f'<text x="16" y="15" font-size="10" class="a" letter-spacing="2" font-weight="700">CASE FILE #{idx:02d}</text>',
         f'<text x="{w - 16}" y="29" font-size="9" class="d" text-anchor="end" letter-spacing="1.5">CLEARANCE: PUBLIC</text>',
         f'<text x="18" y="68" font-size="22" font-weight="800" class="a2">{t(title)}</text>',
         f'<text x="18" y="88" font-size="11" class="a" letter-spacing="1.5">{t(codename)}</text>']
    for i, line in enumerate(wrap(desc, 52)[:4]):
        ly = 116 + i * 18
        o.append(f'<text x="18" y="{ly}" font-size="12" class="t">{t(line)}</text>')
        bw = len(line) * 7.5 + 6
        o.append(f'<rect x="15" y="{ly - 12}" width="{bw:.0f}" height="16" fill="#000" rx="1">'
                 f'<animate attributeName="width" from="{bw:.0f}" to="0" begin="{0.8 + idx * 0.25 + i * 0.35:.2f}s" dur=".45s" fill="freeze"/></rect>')
    o.append(f'<line x1="18" x2="{w - 18}" y1="198" y2="198" stroke="{c["line"]}"/>')
    o.append(f'<text x="18" y="218" font-size="10" class="d">{t(stack)}</text>')
    pushed = fmt_day(meta["pushed_at"]) if meta.get("pushed_at") else "—"
    o.append(f'<text x="18" y="236" font-size="10" class="d">last activity {pushed}</text>')
    stamp, col = ("LIVE ●", c["ok"]) if live else ("OPEN SOURCE", c["accent"])
    o.append(f'<g opacity="0" transform="rotate(-8 {w - 66} 66)"><rect x="{w - 120}" y="52" width="106" height="28" rx="4" fill="none" stroke="{col}" stroke-width="2"/>'
             f'<text x="{w - 67}" y="71" font-size="11" font-weight="800" fill="{col}" text-anchor="middle" letter-spacing="1.5">{stamp}</text>'
             f'<animate attributeName="opacity" from="0" to="1" begin="{2.4 + idx * 0.25:.2f}s" dur=".12s" fill="freeze"/></g>')
    o.append(f'<text x="{w - 18}" y="236" font-size="10" class="a" text-anchor="end">open file →</text>')
    return svg(w, h, "\n".join(o), c)


# ------------------------------------------------- buttons & headers ----


NAV = [("linkedin", "in", "LINKEDIN"), ("email", "@", "EMAIL"), ("demo", "▶", "LIVE DEMO"),
       ("shell", "$", "SHARED SHELL"), ("vault", "#", "THE VAULT")]
# Commands shown as click-to-expand prompts. The README can't run code, so each
# output is pre-rendered by the same engine the multiplayer bot uses.
INSTANT = [("neofetch", "system info"), ("whoami", "who's there?"), ("ls -la", "list files, even hidden ones"),
           ("cat about.txt", "who I am"), ("projects", "what I've built"), ("skills", "tech stack"),
           ("contact", "reach me"), ("fortune", "a random line of wisdom"),
           ("history", "what other visitors ran"), ("sudo hire shriyan", "you know you want to")]


def instant_commands(d, stats):
    import shell  # scripts/shell.py, the same engine the bot runs
    seed = datetime.now(timezone.utc).timetuple().tm_yday  # fortune changes daily
    blocks = []
    for cmd, hint in INSTANT:
        display, out = shell.run(cmd, None, d["shell"], stats, seed)
        body = "\n".join(out).replace("```", "'''")
        blocks.append(f"<details>\n<summary><code>guest@shriyan:~$ {cmd}</code> <sub>{escape(hint)}</sub></summary>\n\n"
                      f"```text\n{body}\n```\n\n</details>")
    return "\n".join(blocks)


def key_button(prefix, label, primary=False):
    c = THEMES["dark"]
    text_w = (len(prefix) + 1 + len(label)) * 7.8
    w, h = int(text_w + 32), 38
    face = c["accent"] if primary else "#141416"
    edge = "#8A6D0B" if primary else "#2C2718"
    fg = c["bg"] if primary else c["text"]
    pre = c["bg"] if primary else c["accent"]
    o = [f'<rect x="1" y="4" width="{w - 2}" height="{h - 5}" rx="8" fill="{edge}"/>',
         f'<rect x="1" y="1" width="{w - 2}" height="{h - 6}" rx="8" fill="{face}" stroke="{edge}"/>',
         f'<line x1="9" x2="{w - 9}" y1="2.5" y2="2.5" stroke="#FFFFFF" stroke-opacity="{.35 if primary else .07}"/>',
         f'<text x="16" y="{h / 2 + 1:.0f}" font-size="13" font-weight="700" xml:space="preserve">'
         f'<tspan fill="{pre}">{t(prefix)}</tspan><tspan fill="{fg}"> {t(label)}</tspan></text>']
    return svg(w, h, "\n".join(o), c, weights=(700,))


def section_header(num, title, tag, theme):
    c = THEMES[theme]
    w, h = 880, 54
    tw = len(title) * (19 * 0.6 + 2)  # advance + letter-spacing
    o = [f'<text x="2" y="36" font-size="13" font-weight="700" class="d">{num}</text>',
         f'<text x="30" y="36" font-size="13" font-weight="700" class="a">//</text>',
         f'<text x="56" y="37" font-size="19" font-weight="800" class="a2" letter-spacing="2">{t(title)}</text>',
         f'<line x1="{56 + tw + 18:.0f}" x2="{w - len(tag) * 7.2 - 22:.0f}" y1="31" y2="31" stroke="{c["line"]}"/>',
         f'<rect x="{56 + tw + 18:.0f}" y="29" width="0" height="3" fill="{c["accent"]}"><animate attributeName="width" from="0" to="60" dur=".8s" fill="freeze"/></rect>',
         f'<text x="{w - 2}" y="35" font-size="11" class="d" text-anchor="end">{t(tag)}</text>']
    return svg(w, h, "\n".join(o), c, weights=(700, 800))


# -------------------------------------------------------------- readme ----

def repo_link(full_name):
    name = full_name.split("/", 1)[1] if full_name.startswith(f"{USER}/") else full_name
    return f"[**{name}**](https://github.com/{full_name})"


def describe(ev, pushes):
    name = ev["repo"]["name"]
    repo = repo_link(name)
    p = ev.get("payload", {})
    kind = ev["type"]
    if kind == "PushEvent":
        # The events API no longer includes commit counts, so count pushes.
        branch = p.get("ref", "").replace("refs/heads/", "")
        n = pushes[(name, branch)]
        return f"PUSH     {n}× → `{branch}` · {repo}"
    if kind == "CreateEvent":
        if p.get("ref_type") == "repository":
            return f"CREATE   repository {repo}"
        return f"CREATE   {p.get('ref_type')} `{p.get('ref')}` · {repo}"
    if kind == "PullRequestEvent":
        action = p.get("action", "")
        action = "merged" if action == "merged" or p["pull_request"].get("merged") else action
        return f"PR       {action} [#{p['number']}](https://github.com/{name}/pull/{p['number']}) · {repo}"
    if kind == "IssuesEvent":
        n = p["issue"]["number"]
        return f"ISSUE    {p.get('action', '')} [#{n}](https://github.com/{name}/issues/{n}) · {repo}"
    if kind == "PublicEvent":
        return f"RELEASE  open-sourced {repo}"
    if kind == "MemberEvent":
        return f"JOIN     collaborator on {repo}"
    if kind == "ForkEvent":
        return f"FORK     {repo}"
    if kind == "WatchEvent" and not name.startswith(f"{USER}/"):
        return f"STAR     {repo}"
    return None


def activity(limit=10):
    events = [e for e in api(f"/users/{USER}/events/public?per_page=100") if e["repo"]["name"] != f"{USER}/{USER}"]
    events.sort(key=lambda e: e["created_at"], reverse=True)
    pushes = {}
    for ev in events:
        if ev["type"] == "PushEvent":
            key = (ev["repo"]["name"], ev["payload"].get("ref", "").replace("refs/heads/", ""))
            pushes[key] = pushes.get(key, 0) + 1
    lines, seen = [], set()
    for ev in events:
        text = describe(ev, pushes)
        key = (ev["repo"]["name"], ev["payload"].get("ref")) if ev["type"] == "PushEvent" else ev["id"]
        if not text or key in seen:
            continue
        seen.add(key)
        lines.append(f"- `{ev['created_at'][:16].replace('T', ' ')}` {text}")
        if len(lines) == limit:
            break
    return "\n".join(lines) or "- _quiet. too quiet._"


def hall(v):
    if not v["solvers"]:
        return "| # | Hacker | Cracked at |\n|:--:|:--|:--|\n| — | _nobody yet. the vault is undefeated._ | — |"
    rows = [f"| {'🥇🥈🥉'[i] if i < 3 else i + 1} | [@{s['login']}](https://github.com/{s['login']}) | {s['at'][:16].replace('T', ' ')} UTC |"
            for i, s in enumerate(v["solvers"])]
    return "| # | Hacker | Cracked at |\n|:--:|:--|:--|\n" + "\n".join(rows)


def replace(text, name, body):
    pattern = re.compile(rf"(<!--{name}:START-->).*?(<!--{name}:END-->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def write(name, content):
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = collect()
    for theme, c in THEMES.items():
        write(f"hero-{theme}.svg", (hero_dark if theme == "dark" else hero_light)(d, c))
        write(f"pulse-{theme}.svg", pulse(d, c, theme))
        write(f"vault-{theme}.svg", vault(d, c, theme))
        write(f"shell-{theme}.svg", shell_scene(d, c, theme))
        for num, key, title, tag in (("02", "shell", "SHARED SHELL", "multiplayer · live"),
                                     ("03", "cases", "DECLASSIFIED", "4 case files · clearance: public"),
                                     ("04", "vault", "THE VAULT", "capture the flag · 1 key")):
            write(f"head-{key}-{theme}.svg", section_header(num, title, tag, theme))
    for key, prefix, label in NAV:
        write(f"btn-{key}.svg", key_button(prefix, label))
    write("key-custom.svg", key_button(">", "type your own command", primary=True))
    for i, case in enumerate(CASES, 1):
        write(f"case-{i}.svg", case_file(i, case, d["repo_meta"].get(case[0], {}), THEMES["dark"]))

    # Live numbers for the shell's neofetch / uptime commands.
    stats = {k: d[k] for k in ("since", "repos", "commits", "contribs")}
    stats["langs"] = [[n, round(p, 1)] for n, p in d["langs"]]
    stats["last"] = d["last"]["name"] if d["last"] else None
    with open(os.path.join(ROOT, "data", "stats.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, indent=2)
        f.write("\n")

    path = os.path.join(ROOT, "README.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = replace(text, "LOG", activity())
    text = replace(text, "KEYS", instant_commands(d, stats))
    text = replace(text, "HALL", hall(d["vault"]))
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    text = replace(text, "UPDATED", f"<sub><code>last sync {stamp} · rebuilt every 6h by a bot I wrote</code></sub>")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
