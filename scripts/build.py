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
MONO = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'SFMono-Regular',Menlo,monospace"

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


def svg(w, h, body, c, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{MONO}">
<style>
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

# Face position inside the 400px avatar, used for the lock-on box.
FACE = (158, 52, 278, 178)


def portrait(d, c, theme, px, py, size):
    """The avatar, duotoned, revealed by a scan line through a layer of cipher text."""
    rng = random.Random(2407)
    k = size / 400
    if theme == "dark":
        lo, hi = (0.04, 0.04, 0.045), (0.98, 0.86, 0.52)
    else:
        lo, hi = (0.055, 0.165, 0.36), (0.96, 0.95, 0.92)
    o = [f'''<filter id="duo" color-interpolation-filters="sRGB">
  <feColorMatrix type="saturate" values="0"/>
  <feComponentTransfer>
    <feFuncR type="table" tableValues="{lo[0]} {hi[0]}"/><feFuncG type="table" tableValues="{lo[1]} {hi[1]}"/><feFuncB type="table" tableValues="{lo[2]} {hi[2]}"/>
  </feComponentTransfer></filter>
<clipPath id="shown"><rect x="{px}" y="{py}" width="{size}" height="0">
  <animate attributeName="height" from="0" to="{size}" begin="0.7s" dur="2.4s" fill="freeze"/></rect></clipPath>
<clipPath id="hidden"><rect x="{px}" y="{py}" width="{size}" height="{size}">
  <animate attributeName="y" from="{py}" to="{py + size}" begin="0.7s" dur="2.4s" fill="freeze"/></rect></clipPath>
<clipPath id="frame"><rect x="{px}" y="{py}" width="{size}" height="{size}" rx="6"/></clipPath>''',
         f'<rect x="{px}" y="{py}" width="{size}" height="{size}" rx="6" fill="{c["panel"]}" stroke="{c["line"]}"/>',
         f'<defs><image id="av" href="{d["avatar"]}" x="{px}" y="{py}" width="{size}" height="{size}"/></defs>',
         f'<g clip-path="url(#frame)"><use href="#av" filter="url(#duo)" clip-path="url(#shown)"/>']
    # glitch slices that flicker every few seconds after the reveal
    for i, (sy, sh, dx, col) in enumerate(((0.30, 0.05, 9, "#FF2E63"), (0.55, 0.035, -11, "#08F7FE"), (0.72, 0.06, 7, c["accent"]))):
        o.append(f'<clipPath id="sl{i}"><rect x="{px}" y="{py + size * sy:.0f}" width="{size}" height="{size * sh:.0f}"/></clipPath>'
                 f'<g clip-path="url(#sl{i})" opacity="0"><use href="#av" x="{dx}" filter="url(#duo)"/>'
                 f'<rect x="{px}" y="{py}" width="{size}" height="{size}" fill="{col}" opacity=".35"/>'
                 f'<animate attributeName="opacity" values="0;0;1;0;1;0;0" keyTimes="0;.86;.88;.9;.92;.94;1" dur="{5 + i * 1.3:.1f}s" begin="4s" repeatCount="indefinite"/></g>')
    # cipher layer: two scrambles alternating, clipped to the not-yet-revealed area
    rows = size // 12
    cols = int(size / 6.2)
    for phase in (0, 1):
        lines = "".join(
            f'<text x="{px + 4}" y="{py + 11 + r * 12}" font-size="10">{"".join(rng.choice("0123456789abcdef#$%@*") for _ in range(cols))}</text>'
            for r in range(rows))
        vals = "1;0" if phase == 0 else "0;1"
        o.append(f'<g clip-path="url(#hidden)" fill="{c["accent"]}" opacity=".55"><g>{lines}'
                 f'<animate attributeName="opacity" values="{vals}" dur=".24s" calcMode="discrete" repeatCount="indefinite"/></g></g>')
    # scan line
    o.append(f'<rect x="{px}" y="{py}" width="{size}" height="3" fill="{c["accent"]}" opacity="0">'
             f'<animate attributeName="y" from="{py}" to="{py + size}" begin="0.7s" dur="2.4s" fill="freeze"/>'
             f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.02;.97;1" begin="0.7s" dur="2.4s" fill="freeze"/></rect>')
    o.append("</g>")
    # face lock: box collapses from the full frame onto the face
    fx, fy = px + FACE[0] * k, py + FACE[1] * k
    fw, fh = (FACE[2] - FACE[0]) * k, (FACE[3] - FACE[1]) * k
    lock = c["ok"] if theme == "dark" else c["alert"]
    o.append(f'<rect x="{px}" y="{py}" width="{size}" height="{size}" fill="none" stroke="{lock}" stroke-width="1.6" stroke-dasharray="6 4" opacity="0">'
             f'<set attributeName="opacity" to="1" begin="3.2s"/>'
             f'<animate attributeName="x" from="{px}" to="{fx:.1f}" begin="3.2s" dur=".6s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>'
             f'<animate attributeName="y" from="{py}" to="{fy:.1f}" begin="3.2s" dur=".6s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>'
             f'<animate attributeName="width" from="{size}" to="{fw:.1f}" begin="3.2s" dur=".6s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>'
             f'<animate attributeName="height" from="{size}" to="{fh:.1f}" begin="3.2s" dur=".6s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>')
    o.append(appear(f'<rect x="{fx:.1f}" y="{fy - 18:.1f}" width="{fw:.1f}" height="16" fill="{lock}"/>'
                    f'<text x="{fx + 4:.1f}" y="{fy - 6:.1f}" font-size="10" font-weight="700" fill="{c["bg"]}">MATCH 98.7%</text>', 3.8, 0.1))
    # HUD corner brackets
    for cx, cy, sx, sy in ((px, py, 1, 1), (px + size, py, -1, 1), (px, py + size, 1, -1), (px + size, py + size, -1, -1)):
        o.append(f'<path d="M{cx} {cy + 18 * sy} V{cy} H{cx + 18 * sx}" fill="none" stroke="{c["accent"]}" stroke-width="2.5"/>')
    return "\n".join(o)


def hero_dark(d, c):
    w, h = 880, 600
    v, sh, last = d["vault"], d["shell"], d["last"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<pattern id="sl" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{c["grid"]}"/></pattern>'
         f'<rect width="{w}" height="{h}" rx="14" fill="url(#sl)" opacity=".55"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>',
         f'<rect width="{w}" height="38" rx="14" fill="{c["panel"]}"/><rect y="24" width="{w}" height="14" fill="{c["panel"]}"/>']
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        o.append(f'<circle cx="{24 + i * 20}" cy="19" r="6" fill="{col}"/>')
    o.append(f'<text x="{w / 2}" y="24" font-size="12" class="d" text-anchor="middle">guest@shriyan: ~ — ssh — encrypted</text>')
    o.append(f'<text x="{w - 22}" y="24" font-size="11" class="al" text-anchor="end"><tspan class="blink">●</tspan> REC</text>')

    # left: portrait + identity HUD
    px, py, size = 28, 62, 300
    o.append(portrait(d, c, "dark", px, py, size))
    hud = [("SUBJECT", "SHRIYAN BOHRA"), ("ORIGIN", "INDIA · UTC+05:30"), ("STATUS", "ONLINE · BUILDING")]
    for i, (k, val) in enumerate(hud):
        o.append(appear(f'<text x="{px}" y="{py + size + 30 + i * 22}" font-size="11" class="d" letter-spacing="1.5">{k:<8}</text>'
                        f'<text x="{px + 80}" y="{py + size + 30 + i * 22}" font-size="12" class="{"ok" if k == "STATUS" else "a2"}">{t(val)}</text>', 4.0 + i * 0.15))
    o.append(appear(f'<text x="{px}" y="{py + size + 104}" font-size="11" class="d">identity verified against github.com/{USER}</text>', 4.5))

    # right: the session
    x, tm = 360, 0.5
    o.append(typed(x, 78, "$ ssh guest@github.com/Shriyan2407", tm, "a", 13))
    tm += 1.3
    o.append(appear(f'<text x="{x}" y="100" font-size="12" class="ok">[✓] handshake ok · TLS 1.3 · AES-256-GCM</text>', tm))
    tm += 0.4
    o.append(typed(x, 132, "$ whoami", tm, "a", 13))
    tm += 0.5
    o.append(f'<linearGradient id="gold" x1="0" x2="1"><stop offset="0" stop-color="{c["accent2"]}"/><stop offset=".55" stop-color="{c["accent"]}"/><stop offset="1" stop-color="#8A6D0B"/></linearGradient>')
    for j, word in enumerate(("SHRIYAN", "BOHRA")):
        wy = 188 + j * 56
        o.append(f'''<g opacity="0">
  <text x="{x - 2}" y="{wy}" font-size="54" font-weight="800" fill="#FF2E63" opacity=".75" class="g1">{word}</text>
  <text x="{x + 2}" y="{wy}" font-size="54" font-weight="800" fill="#08F7FE" opacity=".6" class="g2">{word}</text>
  <text x="{x}" y="{wy}" font-size="54" font-weight="800" fill="url(#gold)">{word}</text>
  <animate attributeName="opacity" from="0" to="1" begin="{tm + j * 0.2:.2f}s" dur=".05s" fill="freeze"/></g>''')
    o.append(appear(f'<text x="{x}" y="270" font-size="12" class="d">cse student · offensive mind, defensive design · full-stack</text>', tm + 0.5))
    tm += 1.0
    o.append(typed(x, 304, "$ ./recon --target=self", tm, "a", 13))
    tm += 1.0
    o.append(appear(f'<text x="{x}" y="326" font-size="12" class="t" xml:space="preserve">repos {d["repos"]}  ·  commits/yr {d["commits"]}  ·  contributions/yr {d["contribs"]}</text>', tm))
    if last:
        o.append(appear(f'<text x="{x}" y="346" font-size="12" class="d">last push → <tspan class="a2">{t(last["name"])}</tspan> · {fmt_day(last["pushed_at"])}</text>', tm + 0.15))
    tm += 0.3
    for i, (lang, pct) in enumerate(d["langs"]):
        ly = 376 + i * 22
        bw = 290
        o.append(appear(
            f'<text x="{x}" y="{ly}" font-size="12" class="t">{t(lang)}</text>'
            f'<rect x="{x + 100}" y="{ly - 9}" width="{bw}" height="9" rx="2" fill="{c["grid"]}" stroke="{c["line"]}"/>'
            f'<rect x="{x + 100}" y="{ly - 9}" width="0" height="9" rx="2" fill="{c["accent"]}">'
            f'<animate attributeName="width" from="0" to="{max(pct / 100 * bw, 3):.1f}" begin="{tm + 0.1 * i:.2f}s" dur="1.1s" fill="freeze"/></rect>'
            f'<text x="{x + 400}" y="{ly}" font-size="11" class="d">{pct:4.1f}%</text>', tm + 0.1 * i))
    tm += 0.8
    o.append(typed(x, 480, "$ cat /vault/status", tm, "a", 13))
    tm += 0.8
    solved = len(v["solvers"])
    state = f'<tspan class="al">BREACHED ×{solved}</tspan>' if solved else '<tspan class="ok">SECURE</tspan>'
    o.append(appear(f'<text x="{x}" y="502" font-size="12" class="t">VAULT {state} · {v["attempts"]} attempts · shell: {sh["total"]} cmds by {len(sh["users"])} visitors</text>', tm))
    tm += 0.4
    o.append(appear(f'<text x="{x}" y="530" font-size="13" class="a">$ <tspan class="blink">█</tspan></text>', tm))
    o.append(f'<line x1="22" x2="{w - 22}" y1="{h - 38}" y2="{h - 38}" stroke="{c["line"]}"/>')
    o.append(f'<text x="30" y="{h - 16}" font-size="11" class="al">◆ RED TEAM VIEW</text>')
    o.append(f'<text x="{w - 30}" y="{h - 16}" font-size="11" class="d" text-anchor="end">same mind // different perspective — switch GitHub to light theme ☀</text>')
    css = """.g1{animation:g1 3.2s infinite steps(1)} .g2{animation:g2 2.7s infinite steps(1)}
  @keyframes g1{0%,86%,100%{transform:translate(0,0)}88%{transform:translate(-5px,2px)}91%{transform:translate(4px,-2px)}94%{transform:translate(-2px,0)}}
  @keyframes g2{0%,80%,100%{transform:translate(0,0)}83%{transform:translate(5px,-1px)}87%{transform:translate(-4px,2px)}90%{transform:translate(2px,0)}}"""
    return svg(w, h, "\n".join(o), c, css)


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
    lines = []  # (kind, text, login)
    entries = sh["history"][-4:]
    if not entries:
        lines += [("out", "shriyan-os 1.0 (tty1) · multiplayer edition", None),
                  ("out", "", None),
                  ("out", "this terminal is shared by everyone who visits this profile.", None),
                  ("out", "click a command below. a bot runs it and the output lands here.", None),
                  ("out", "", None),
                  ("out", "no one has connected yet. be the first name on this screen.", None)]
    for e in entries:
        lines.append(("cmd", e["display"], e["login"]))
        out = e["out"][:5]
        lines += [("out", l, None) for l in out]
        if len(e["out"]) > 5:
            lines.append(("dim", f"… {len(e['out']) - 5} more lines in the issue", None))
    lines = lines[-22:]
    h = 92 + len(lines) * 18 + 40
    o = [f'<rect width="{w}" height="{h}" rx="12" fill="{c["bg"] if theme == "dark" else "#0F1729"}"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="{c["line"]}"/>',
         f'<rect width="{w}" height="36" rx="12" fill="{c["panel"] if theme == "dark" else "#16223A"}"/><rect y="24" width="{w}" height="12" fill="{c["panel"] if theme == "dark" else "#16223A"}"/>']
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        o.append(f'<circle cx="{22 + i * 18}" cy="18" r="5.5" fill="{col}"/>')
    acc = c["accent"] if theme == "dark" else "#79A8FF"
    txt = c["text"] if theme == "dark" else "#DCE6F7"
    dim = c["dim"] if theme == "dark" else "#7D8BA5"
    o.append(f'<text x="{w / 2}" y="23" font-size="12" fill="{dim}" text-anchor="middle">shared shell — {sh["total"]} commands · {len(sh["users"])} visitors connected</text>')
    o.append(f'<text x="{w - 20}" y="23" font-size="11" fill="#3FB950" text-anchor="end"><tspan class="blink">●</tspan> LIVE</text>')
    y = 66
    for i, (kind, text, login) in enumerate(lines):
        delay = 0.3 + i * 0.06
        if kind == "cmd":
            row = (f'<text x="24" y="{y}" font-size="13" xml:space="preserve"><tspan fill="#3FB950">@{t(login)}</tspan>'
                   f'<tspan fill="{dim}">@shriyan:~$ </tspan><tspan fill="{acc}" font-weight="700">{t(text)}</tspan></text>')
        else:
            row = f'<text x="24" y="{y}" font-size="12.5" fill="{dim if kind == "dim" else txt}" xml:space="preserve">{t(text)}</text>'
        o.append(appear(row, delay, 0.15))
        y += 18
    o.append(appear(f'<text x="24" y="{y + 10}" font-size="13" xml:space="preserve"><tspan fill="#3FB950">@you</tspan>'
                    f'<tspan fill="{dim}">@shriyan:~$ </tspan><tspan fill="{acc}" class="blink">█</tspan></text>', 0.3 + len(lines) * 0.06))
    return svg(w, h, "\n".join(o), c)


# --------------------------------------------------------------- pulse ----

def pulse(d, c, theme):
    w, h = 880, 190
    days = d["days"][-60:]
    counts = [x["contributionCount"] for x in days]
    peak = max(counts) or 1
    base, top = 118, 50
    step = (w - 60) / len(days)
    pts = [f"M30 {base}"]
    for i, n in enumerate(counts):
        x0 = 30 + i * step
        if n == 0:
            pts.append(f"L{x0 + step:.1f} {base}")
            continue
        amp = (base - top) * (0.25 + 0.75 * math.sqrt(n / peak))
        pts += [f"L{x0 + step * .25:.1f} {base}", f"L{x0 + step * .35:.1f} {base + 6}",
                f"L{x0 + step * .5:.1f} {base - amp:.1f}", f"L{x0 + step * .65:.1f} {base + amp * .35:.1f}",
                f"L{x0 + step * .78:.1f} {base}", f"L{x0 + step:.1f} {base}"]
    path = " ".join(pts)
    last30 = sum(counts[-30:])
    active = sum(1 for n in counts if n)
    line_col = c["accent"] if theme == "dark" else c["alert"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<pattern id="eg" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M10 0H0V10" fill="none" stroke="{c["grid"]}"/></pattern>',
         f'<rect x="20" y="40" width="{w - 40}" height="110" fill="url(#eg)"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>',
         f'<text x="30" y="28" font-size="12" class="a" font-weight="700" letter-spacing="2">♥ SYSTEM VITALS</text>',
         f'<text x="{w - 30}" y="28" font-size="11" class="d" text-anchor="end">commit pulse · last 60 days · live from GitHub</text>',
         f'<filter id="glow"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
         f'<path id="ecg" d="{path}" fill="none" stroke="{line_col}" stroke-opacity=".18" stroke-width="2"/>',
         f'<path d="{path}" fill="none" stroke="{line_col}" stroke-width="2.2" filter="url(#glow)" pathLength="1000" stroke-dasharray="1000" stroke-dashoffset="1000">'
         f'<animate attributeName="stroke-dashoffset" values="1000;0;0" keyTimes="0;.8;1" dur="7s" repeatCount="indefinite"/></path>',
         f'<circle r="4" fill="{line_col}" filter="url(#glow)"><animateMotion dur="7s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;.8;1" calcMode="linear"><mpath href="#ecg"/></animateMotion></circle>',
         ]
    status = "ALIVE" if last30 else "FLATLINE — send help"
    o.append(f'<text x="30" y="176" font-size="12" class="t">30-day bpm <tspan class="a" font-weight="700">{last30}</tspan>'
             f'   ·   active days <tspan class="a" font-weight="700">{active}/60</tspan>'
             f'   ·   peak <tspan class="a" font-weight="700">{peak}</tspan> in a day'
             f'   ·   status <tspan class="{"ok" if last30 else "al"}" font-weight="700">{status}</tspan></text>')
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
    text = replace(text, "HALL", hall(d["vault"]))
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    text = replace(text, "UPDATED", f"<sub><code>last sync {stamp} · rebuilt every 6h by a bot I wrote</code></sub>")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
