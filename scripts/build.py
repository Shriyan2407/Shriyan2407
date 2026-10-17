"""Render the live profile: animated SVG scenes + auto-updated README blocks.

Runs from .github/workflows/build.yml (every 6 hours) and after every Vault
attempt. Everything shown is pulled from the GitHub API at build time.
"""

import json
import math
import itertools
import os
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
        "vault": load_vault(),
    }


def load_vault():
    path = os.path.join(ROOT, "data", "vault.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"attempts": 0, "solvers": [], "last": None}


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

def hero_dark(d, c):
    w, h = 880, 560
    v = d["vault"]
    last = d["last"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>',
         f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>']
    # scanlines
    o.append(f'<pattern id="sl" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{c["grid"]}"/></pattern>'
             f'<rect width="{w}" height="{h}" rx="14" fill="url(#sl)" opacity=".55"/>')
    # title bar
    o.append(f'<rect width="{w}" height="38" rx="14" fill="{c["panel"]}"/><rect y="24" width="{w}" height="14" fill="{c["panel"]}"/>')
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        o.append(f'<circle cx="{24 + i * 20}" cy="19" r="6" fill="{col}"/>')
    o.append(f'<text x="{w / 2}" y="24" font-size="12" class="d" text-anchor="middle">guest@shriyan: ~ — ssh — encrypted</text>')
    o.append(f'<text x="{w - 22}" y="24" font-size="11" class="al" text-anchor="end">● REC</text>')

    x, y, tm = 30, 78, 0.4
    o.append(typed(x, y, "$ ssh guest@github.com/Shriyan2407", tm, "a"))
    tm += 1.4
    o.append(appear(f'<text x="{x}" y="{y + 24}" font-size="13" class="ok">[✓] handshake ok · TLS 1.3 · AES-256-GCM · host key verified</text>', tm))
    tm += 0.5
    o.append(typed(x, y + 56, "$ whoami", tm, "a"))
    tm += 0.6
    # Glitch name
    name = "SHRIYAN BOHRA"
    ny = y + 118
    glitch = f"""<g opacity="0">
  <text x="{x - 2}" y="{ny}" font-size="54" font-weight="800" fill="#FF2E63" opacity=".75" class="g1">{name}</text>
  <text x="{x + 2}" y="{ny}" font-size="54" font-weight="800" fill="#08F7FE" opacity=".6" class="g2">{name}</text>
  <text x="{x}" y="{ny}" font-size="54" font-weight="800" fill="url(#gold)">{name}</text>
  <animate attributeName="opacity" from="0" to="1" begin="{tm:.2f}s" dur=".05s" fill="freeze"/></g>"""
    o.append(f'<linearGradient id="gold" x1="0" x2="1"><stop offset="0" stop-color="{c["accent2"]}"/><stop offset=".5" stop-color="{c["accent"]}"/><stop offset="1" stop-color="#8A6D0B"/></linearGradient>')
    o.append(glitch)
    o.append(appear(f'<text x="{x}" y="{ny + 28}" font-size="14" class="d">cse student · offensive-minded, defensive by design · full-stack · india</text>', tm + 0.3))
    tm += 1.0

    y2 = ny + 74
    o.append(typed(x, y2, "$ ./recon --target=self --depth=full", tm, "a"))
    tm += 1.4
    stats = (f"public repos {d['repos']}  ·  commits/yr {d['commits']}  ·  contributions/yr {d['contribs']}  ·  "
             f"online since {fmt_day(d['since'])}")
    o.append(appear(f'<text x="{x}" y="{y2 + 26}" font-size="13" class="t" xml:space="preserve">{t(stats)}</text>', tm))
    tm += 0.3
    by = y2 + 52
    for i, (lang, pct) in enumerate(d["langs"]):
        cx = x + (i % 2) * 420
        cy = by + (i // 2) * 26
        bw = 230
        fill = max(pct / 100 * bw, 3)
        o.append(appear(
            f'<text x="{cx}" y="{cy}" font-size="13" class="t">{t(lang):<11}</text>'
            f'<rect x="{cx + 110}" y="{cy - 10}" width="{bw}" height="10" rx="2" fill="{c["grid"]}" stroke="{c["line"]}"/>'
            f'<rect x="{cx + 110}" y="{cy - 10}" width="0" height="10" rx="2" fill="{c["accent"]}">'
            f'<animate attributeName="width" from="0" to="{fill:.1f}" begin="{tm + 0.1 * i:.2f}s" dur="1.2s" fill="freeze"/></rect>'
            f'<text x="{cx + 350}" y="{cy}" font-size="12" class="d">{pct:4.1f}%</text>', tm + 0.1 * i))
    tm += 0.8
    if last:
        o.append(appear(f'<text x="{x}" y="{by + 64}" font-size="13" class="d">last push → <tspan class="a2">{t(last["name"])}</tspan> · {fmt_day(last["pushed_at"])}</text>', tm))
    tm += 0.5

    y3 = by + 104
    o.append(typed(x, y3, "$ cat /vault/status", tm, "a"))
    tm += 0.9
    solved = len(v["solvers"])
    state = f'<tspan class="al">BREACHED ×{solved}</tspan>' if solved else '<tspan class="ok">SECURE</tspan>'
    o.append(appear(f'<text x="{x}" y="{y3 + 26}" font-size="14" class="t">VAULT: {state} · {v["attempts"]} attempts · scroll down if you think you can.</text>', tm))
    tm += 0.5
    o.append(appear(f'<text x="{x}" y="{y3 + 58}" font-size="14" class="a">$ <tspan class="blink">█</tspan></text>', tm))
    # footer hint
    o.append(f'<line x1="22" x2="{w - 22}" y1="{h - 38}" y2="{h - 38}" stroke="{c["line"]}"/>')
    o.append(f'<text x="30" y="{h - 16}" font-size="11" class="al">◆ RED TEAM VIEW</text>')
    o.append(f'<text x="{w - 30}" y="{h - 16}" font-size="11" class="d" text-anchor="end">same mind // different perspective — switch GitHub to light theme ☀</text>')
    css = """.g1{animation:g1 3.2s infinite steps(1)} .g2{animation:g2 2.7s infinite steps(1)}
  @keyframes g1{0%,86%,100%{transform:translate(0,0)}88%{transform:translate(-5px,2px)}91%{transform:translate(4px,-2px)}94%{transform:translate(-2px,0)}}
  @keyframes g2{0%,80%,100%{transform:translate(0,0)}83%{transform:translate(5px,-1px)}87%{transform:translate(-4px,2px)}90%{transform:translate(2px,0)}}"""
    return svg(w, h, "\n".join(o), c, css)


def hero_light(d, c):
    w, h = 880, 560
    v = d["vault"]
    o = [f'<rect width="{w}" height="{h}" rx="14" fill="{c["bg"]}"/>']
    o.append(f'<pattern id="gr" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="{c["grid"]}"/></pattern>'
             f'<rect width="{w}" height="{h}" rx="14" fill="url(#gr)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{c["line"]}"/>')
    o.append(f'<rect width="{w}" height="44" rx="14" fill="{c["accent2"]}"/><rect y="30" width="{w}" height="14" fill="{c["accent2"]}"/>')
    o.append(f'<text x="28" y="28" font-size="13" font-weight="700" fill="#FFFFFF" letter-spacing="2">THREAT ASSESSMENT // SUBJECT PROFILE</text>')
    o.append(f'<text x="{w - 28}" y="28" font-size="12" fill="#AFC3E8" text-anchor="end">REF SB-2407 · GENERATED {datetime.now(timezone.utc).strftime("%d %b %Y").upper()}</text>')

    x = 36
    o.append(appear(f'<text x="{x}" y="96" font-size="12" class="d" letter-spacing="2">SUBJECT</text>', 0.2))
    o.append(appear(f'<text x="{x}" y="140" font-size="46" font-weight="800" fill="{c["accent2"]}">SHRIYAN BOHRA</text>', 0.4, 0.6))
    o.append(appear(f'<text x="{x}" y="168" font-size="14" class="a">classification: BUILDER · threat level LOW · output level CRITICAL</text>', 0.9))

    fields = [("ROLE", "CSE student / developer"), ("FOCUS", "security · full-stack · AI"),
              ("BASE", "India"), ("ACTIVE SINCE", fmt_day(d["since"])),
              ("PUBLIC REPOS", str(d["repos"])), ("CONTRIBUTIONS/YR", str(d["contribs"])),
              ("COMMITS/YR", str(d["commits"])), ("VAULT", f"{len(v['solvers'])} breaches / {v['attempts']} attempts")]
    for i, (k, val) in enumerate(fields):
        fx = x + (i % 2) * 250
        fy = 212 + (i // 2) * 48
        o.append(appear(f'<text x="{fx}" y="{fy}" font-size="10" class="d" letter-spacing="1.5">{k}</text>'
                        f'<text x="{fx}" y="{fy + 20}" font-size="15" class="t" font-weight="600">{t(val)}</text>'
                        f'<line x1="{fx}" x2="{fx + 225}" y1="{fy + 28}" y2="{fy + 28}" stroke="{c["line"]}"/>', 1.1 + i * 0.12))
    ly = 418
    o.append(appear(f'<text x="{x}" y="{ly}" font-size="10" class="d" letter-spacing="1.5">CAPABILITY SIGNATURE</text>', 2.0))
    for i, (lang, pct) in enumerate(d["langs"]):
        lx = x + (i % 2) * 250
        lyy = ly + 26 + (i // 2) * 26
        bw = 120
        o.append(appear(
            f'<text x="{lx}" y="{lyy}" font-size="12" class="t">{t(lang)}</text>'
            f'<rect x="{lx + 96}" y="{lyy - 9}" width="{bw}" height="8" rx="4" fill="{c["grid"]}"/>'
            f'<rect x="{lx + 96}" y="{lyy - 9}" width="0" height="8" rx="4" fill="{c["accent"]}">'
            f'<animate attributeName="width" from="0" to="{max(pct / 100 * bw, 3):.1f}" begin="{2.1 + i * 0.1:.2f}s" dur="1s" fill="freeze"/></rect>'
            f'<text x="{lx + 96 + bw + 8}" y="{lyy}" font-size="10" class="d">{pct:.1f}%</text>', 2.1 + i * 0.1))

    # Radar
    rx, ry, rr = 700, 300, 125
    radar = [f'<circle cx="{rx}" cy="{ry}" r="{rr}" fill="{c["panel"]}" stroke="{c["line"]}"/>']
    for k in (0.33, 0.66):
        radar.append(f'<circle cx="{rx}" cy="{ry}" r="{rr * k:.0f}" fill="none" stroke="{c["grid"]}"/>')
    radar.append(f'<line x1="{rx - rr}" x2="{rx + rr}" y1="{ry}" y2="{ry}" stroke="{c["grid"]}"/><line x1="{rx}" x2="{rx}" y1="{ry - rr}" y2="{ry + rr}" stroke="{c["grid"]}"/>')
    radar.append(f'<linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c["accent"]}" stop-opacity="0"/><stop offset="1" stop-color="{c["accent"]}" stop-opacity=".45"/></linearGradient>')
    radar.append(f'<g><path d="M{rx} {ry} L{rx + rr} {ry} A{rr} {rr} 0 0 0 {rx + rr * math.cos(math.radians(-40)):.1f} {ry + rr * math.sin(math.radians(-40)):.1f} Z" fill="url(#sw)"/>'
                 f'<animateTransform attributeName="transform" type="rotate" from="0 {rx} {ry}" to="360 {rx} {ry}" dur="4s" repeatCount="indefinite"/></g>')
    names = [n for n, *_ in CASES]
    for i, n in enumerate(names):
        ang = math.radians(35 + i * 83)
        dist = rr * (0.4 + 0.13 * i)
        bx, byy = rx + dist * math.cos(ang), ry + dist * math.sin(ang)
        delay = (math.degrees(ang) % 360) / 360 * 4
        radar.append(f'<circle cx="{bx:.1f}" cy="{byy:.1f}" r="4" fill="{c["alert"]}" opacity="0">'
                     f'<animate attributeName="opacity" values="0;1;0.15" keyTimes="0;0.08;1" dur="4s" begin="{delay:.2f}s" repeatCount="indefinite"/></circle>'
                     f'<text x="{bx + 8:.1f}" y="{byy + 4:.1f}" font-size="9" class="d">{t(n.lower())}</text>')
    o.append(appear("".join(radar), 0.6, 0.8))
    o.append(appear(f'<text x="{rx}" y="{ry + rr + 24}" font-size="10" class="d" text-anchor="middle" letter-spacing="1.5">ACTIVE OPERATIONS SCAN</text>', 1.0))
    # Stamp
    o.append(f'<g opacity="0" transform="rotate(-12 760 140)"><rect x="672" y="112" width="176" height="52" rx="6" fill="none" stroke="{c["alert"]}" stroke-width="3"/>'
             f'<text x="760" y="147" font-size="24" font-weight="800" fill="{c["alert"]}" text-anchor="middle" letter-spacing="4">CLEARED</text>'
             f'<animate attributeName="opacity" from="0" to=".85" begin="2.6s" dur=".15s" fill="freeze"/></g>')
    o.append(f'<line x1="22" x2="{w - 22}" y1="{h - 38}" y2="{h - 38}" stroke="{c["line"]}"/>')
    o.append(f'<text x="30" y="{h - 16}" font-size="11" class="a" font-weight="700">◆ BLUE TEAM VIEW</text>')
    o.append(f'<text x="{w - 30}" y="{h - 16}" font-size="11" class="d" text-anchor="end">same mind // different perspective — switch GitHub to dark theme ☾</text>')
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
    for i, case in enumerate(CASES, 1):
        write(f"case-{i}.svg", case_file(i, case, d["repo_meta"].get(case[0], {}), THEMES["dark"]))

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
