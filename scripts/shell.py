"""Run one command in the profile's shared shell.

A visitor opens an issue titled `shell: <command>`. This runs the command
against a small virtual filesystem, writes the reply to vault-reply.md and
appends the run to data/shell.json, which build.py renders on the profile.

Only recognised commands are shown on the profile. Anything else is shown as
"<unknown>", so visitors can't use the profile to display arbitrary text.
"""

import json
import os
import random
import re
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
OWNER = "Shriyan2407"

PROJECTS = {
    "market-ka-baadshah": ("Multi-agent AI equity-research terminal for NSE & BSE.",
                           "Next.js · TypeScript · Prisma · Claude API",
                           "https://github.com/Shriyan2407/r-h-t-i-h", "https://r-h-t-i-h.vercel.app"),
    "doccare": ("Healthcare OS: records, appointments, specialists, AI insights.",
                "React · Vite", "https://github.com/Shriyan2407/DOCCARE", "https://doccare.vercel.app"),
    "circuit-x": ("Network failure-recovery simulator: BFS/DFS, Dijkstra, hand-built min-heap.",
                  "Java", "https://github.com/Shriyan2407/CIRCUIT-X", None),
    "space-mission-control": ("Mission-ops console on custom linked lists, queues and stacks.",
                              "Java", "https://github.com/Shriyan2407/nebulavoltage", None),
}

FILES = {
    "about.txt": [
        "Shriyan Bohra. CSE student from India.",
        "I build things that are fast, useful and hard to break:",
        "AI products, full-stack apps, and the occasional network that heals itself.",
        "Offensive mind, defensive design.",
    ],
    "skills.txt": [
        "lang   TypeScript · JavaScript · Java · Python · C/C++",
        "web    React · Next.js · Node · Express · Tailwind",
        "data   PostgreSQL · Prisma · MongoDB",
        "ops    Git · Docker · Linux · Vercel",
        "sec    threat modelling · secure design · CTFs",
    ],
    "contact.txt": [
        "linkedin  linkedin.com/in/shriyan-bohra-647057386",
        "email     shriyanbohra24077@gmail.com",
        "github    github.com/Shriyan2407",
        "open to   internships · hackathons · collaborations",
    ],
    "now.txt": [
        "building  Market Ka Baadshah v2 (EquityLens AI)",
        "learning  LLM agents · secure architecture · Rust",
        "reading   other people's source code",
    ],
    ".bash_history": [
        "git commit -m 'final fix'",
        "git commit -m 'final fix 2'",
        "git commit -m 'ok this time for real'",
        "sudo make me a sandwich",
        "cat .vault/README",
    ],
    ".vault/README": [
        "THE VAULT. one key. three layers.",
        "the transmission is printed on the profile, under 'The Vault'.",
        "hints live next to this file: hint-1, hint-2, hint-3.",
        "never post the key. post sha256('<your-username>:<KEY>').",
    ],
    ".vault/hint-1": ["the outer layer only needs sixteen symbols: 0-9 and a-f."],
    ".vault/hint-2": ["the middle layer ends where padding would begin. sixty-four symbols."],
    ".vault/hint-3": ["the core was shifted by thirteen. shift it again and it shifts back."],
}

FORTUNES = [
    "It works on my machine. Ship the machine.",
    "There are 10 kinds of people: those who read binary and those who don't.",
    "A secure system is one where the attacker gets bored first.",
    "Weeks of coding can save you hours of planning.",
    "The S in IoT stands for security.",
    "Discipline turns ideas into reality.",
    "Every senior engineer was once a junior who didn't give up.",
]

HELP = [
    "whoami · neofetch · ls [-la] [dir] · cat <file> · open <project>",
    "skills · projects · contact · now · uptime · date · history",
    "fortune · ping shriyan · sudo hire shriyan · hack · and a few secrets",
    "tip: try `ls -la`.",
]


def load(name, default):
    path = os.path.join(DATA, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def run(raw, login, state, stats, seed):
    """Return (display, output_lines). display is safe to render publicly."""
    parts = raw.split()
    if not parts:
        return "help", HELP
    cmd, args = parts[0].lower(), [a for a in parts[1:]]
    arg = " ".join(args)

    if cmd == "help":
        return "help", HELP
    if cmd == "whoami":
        return "whoami", [f"you: @{login}, running command #{state['total'] + 1} on this shell.",
                          "me:  Shriyan Bohra. CSE student, security-minded builder."]
    if cmd == "pwd":
        return "pwd", ["/home/shriyan"]
    if cmd == "ls":
        flags = [a for a in args if re.fullmatch(r"-[la]{1,2}", a)]
        target = next((a for a in args if not a.startswith("-")), "").strip("/").lower()
        hidden = any("a" in f for f in flags)
        if target in ("", "~", "."):
            names = ["about.txt", "contact.txt", "now.txt", "projects/", "skills.txt"]
            if hidden:
                names = [".bash_history", ".vault/"] + names
            return f"ls {' '.join(flags)}".strip(), ["  ".join(names)]
        if target == "projects":
            return "ls projects", ["  ".join(PROJECTS)]
        if target == ".vault":
            return "ls .vault", ["README  hint-1  hint-2  hint-3"]
        return "ls <unknown>", ["ls: no such file or directory"]
    if cmd == "cat":
        name = arg.strip().removeprefix("~/").removeprefix("./")
        if name in FILES:
            return f"cat {name}", FILES[name]
        proj = name.removeprefix("projects/")
        if proj in PROJECTS:
            return f"cat projects/{proj}", project_lines(proj)
        return "cat <unknown>", ["cat: no such file. try `ls -la`."]
    if cmd == "open":
        name = arg.strip().lower().removeprefix("projects/")
        if name in PROJECTS:
            return f"open {name}", project_lines(name)
        return "open <unknown>", ["open: unknown project. try `ls projects`."]
    if cmd in ("skills", "contact", "now", "about"):
        return cmd, FILES[f"{cmd}.txt"]
    if cmd == "projects":
        return "projects", [f"{k:<22} {v[0]}" for k, v in PROJECTS.items()]
    if cmd == "neofetch":
        return "neofetch", neofetch(stats, state)
    if cmd == "uptime":
        days = (datetime.now(timezone.utc).date() - datetime.strptime(stats.get("since", "2025-06-10"), "%Y-%m-%d").date()).days
        return "uptime", [f"up {days} days on GitHub · {stats.get('contribs', '?')} contributions this year · load: high"]
    if cmd == "date":
        return "date", [datetime.now(timezone.utc).strftime("%a %d %b %Y %H:%M:%S UTC")]
    if cmd == "history":
        recent = state["history"][-5:]
        return "history", [f"@{h['login']}: {h['display']}" for h in recent] or ["you're the first one here."]
    if cmd == "fortune":
        return "fortune", [random.Random(seed).choice(FORTUNES)]
    if cmd == "ping":
        return "ping shriyan", ["PING shriyan: 64 bytes, time=~24h", "faster route: linkedin.com/in/shriyan-bohra-647057386"]
    if cmd == "sudo":
        if re.fullmatch(r"hire\s+shriyan.*", arg.lower()):
            return "sudo hire shriyan", [f"[sudo] password for {login}: ********",
                                         "✓ permission granted. excellent judgement.",
                                         "→ shriyanbohra24077@gmail.com · linkedin.com/in/shriyan-bohra-647057386"]
        return "sudo <redacted>", [f"{login} is not in the sudoers file. This incident will be reported."]
    if cmd == "rm":
        return "rm <redacted>", ["rm: refusing to delete what took this long to build."]
    if cmd == "hack":
        return "hack", ["[■■■■■■■■■■] 100%  access... denied.", "real hackers don't type `hack`. try the vault."]
    if cmd in ("exit", "logout", "quit"):
        return cmd, ["there is no exit. only git push."]
    if cmd in ("clear", "cls"):
        return cmd, ["this terminal has no clear. it remembers everything."]
    if cmd in ("vim", "vi", "nano", "emacs"):
        return cmd, ["you are now trapped in the editor. (relax: :q!)"]
    if cmd == "cd":
        return "cd", ["cd: this shell is stateless. try `ls projects` or `cat about.txt`."]
    return "<unknown>", ["command not found. type `help`."]


def project_lines(name):
    desc, stack, repo, live = PROJECTS[name]
    out = [desc, f"stack  {stack}", f"code   {repo}"]
    if live:
        out.append(f"live   {live}")
    return out


def neofetch(stats, state):
    langs = " · ".join(f"{n} {p}%" for n, p in stats.get("langs", [])[:3])
    return [
        "   ▄▄▄▄▄▄     shriyan@github",
        "  █ ▄▄▄ █     ──────────────",
        "  █ ███ █     os      shriyan-os 1.0 (multiplayer)",
        "  █▄▄▄▄▄█     repos   " + str(stats.get("repos", "?")) + " public",
        "   ▀▀▀▀▀      commits " + str(stats.get("commits", "?")) + " this year",
        "              langs   " + langs,
        "              shell   " + f"{state['total'] + 1} command{'' if state['total'] == 0 else 's'} served",
    ]


def main():
    login = os.environ["LOGIN"]
    title = os.environ.get("TITLE", "")[:120]
    number = int(os.environ.get("NUMBER", "0"))
    raw = re.sub(r"^\s*shell\s*:?", "", title, flags=re.I).strip().strip("`$ ").strip()

    state = load("shell.json", {"total": 0, "users": [], "history": []})
    stats = load("stats.json", {})
    display, out = run(raw, login, state, stats, number)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["total"] += 1
    if login not in state["users"] and login != OWNER:
        state["users"].append(login)
    state["history"] = (state["history"] + [{"login": login, "display": display, "out": out, "at": now}])[-30:]
    with open(os.path.join(DATA, "shell.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")

    body = "\n".join(out).replace("```", "'''")
    reply = (f"```console\n{login}@shriyan:~$ {display}\n{body}\n```\n\n"
             "Your command is now live on [the profile](https://github.com/Shriyan2407) for everyone to see. "
             "Run another anytime.")
    with open(os.path.join(ROOT, "vault-reply.md"), "w", encoding="utf-8") as f:
        f.write(reply + "\n\n<sub>🤖 executed by the shared-shell bot</sub>\n")


if __name__ == "__main__":
    main()
