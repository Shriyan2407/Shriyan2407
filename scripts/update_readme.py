"""Refresh the auto-generated sections of the profile README.

Runs daily from .github/workflows/update-readme.yml. Only the blocks between
the <!--NAME:START--> / <!--NAME:END--> markers are rewritten.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USER = "Shriyan2407"
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

LANG_EMOJI = {
    "TypeScript": "🟦", "JavaScript": "🟨", "Python": "🐍", "Java": "☕",
    "Rust": "🦀", "C++": "⚙️", "C": "⚙️", "HTML": "🌐", "CSS": "🎨",
}


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def day(iso):
    # Absolute dates stay correct between the daily refreshes.
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")


def repo_link(full_name):
    name = full_name.split("/", 1)[1] if full_name.startswith(f"{USER}/") else full_name
    return f"[**{name}**](https://github.com/{full_name})"


def recent_repos(limit=6):
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=100")
    rows = []
    for r in repos:
        if r["fork"] or r["size"] == 0 or r["name"] == USER:
            continue
        lang = r["language"] or "—"
        desc = (r["description"] or "").strip() or "_No description yet_"
        live = f" · [🔗 live]({r['homepage']})" if r.get("homepage") else ""
        rows.append(
            f"| {LANG_EMOJI.get(lang, '📦')} [**{r['name']}**]({r['html_url']}){live} "
            f"| {desc} | `{lang}` | {day(r['pushed_at'])} |"
        )
        if len(rows) == limit:
            break
    head = "| Project | What it is | Lang | Updated |\n|:--|:--|:--:|:--:|"
    return head + "\n" + "\n".join(rows)


def describe(ev, pushes):
    name = ev["repo"]["name"]
    repo = repo_link(name)
    p = ev.get("payload", {})
    t = ev["type"]
    if t == "PushEvent":
        # The events API no longer includes commit counts, so count pushes.
        branch = p.get("ref", "").replace("refs/heads/", "")
        n = pushes[(name, branch)]
        return f"🚀 Pushed {n} time{'s' if n != 1 else ''} to `{branch}` in {repo}"
    if t == "CreateEvent":
        if p.get("ref_type") == "repository":
            return f"✨ Created repository {repo}"
        return f"🌱 Created {p.get('ref_type')} `{p.get('ref')}` in {repo}"
    if t == "PullRequestEvent":
        action = p.get("action", "")
        action = "Merged" if action == "merged" or p["pull_request"].get("merged") else action.capitalize()
        return f"🔀 {action} PR [#{p['number']}](https://github.com/{name}/pull/{p['number']}) in {repo}"
    if t == "IssuesEvent":
        n = p["issue"]["number"]
        return f"🐛 {p.get('action', '').capitalize()} issue [#{n}](https://github.com/{name}/issues/{n}) in {repo}"
    if t == "PublicEvent":
        return f"🌍 Open-sourced {repo}"
    if t == "MemberEvent":
        return f"🤝 Joined {repo} as a collaborator"
    if t == "ForkEvent":
        return f"🍴 Forked {repo}"
    if t == "WatchEvent" and not name.startswith(f"{USER}/"):
        return f"⭐ Starred {repo}"
    if t == "ReleaseEvent":
        return f"🏷️ Released `{p['release']['tag_name']}` in {repo}"
    return None


def recent_activity(limit=8):
    events = api(f"/users/{USER}/events/public?per_page=100")
    events = [e for e in events if e["repo"]["name"] != f"{USER}/{USER}"]
    events.sort(key=lambda e: e["created_at"], reverse=True)

    pushes = {}
    for ev in events:
        if ev["type"] == "PushEvent":
            key = (ev["repo"]["name"], ev["payload"].get("ref", "").replace("refs/heads/", ""))
            pushes[key] = pushes.get(key, 0) + 1

    lines, seen = [], set()
    for ev in events:
        text = describe(ev, pushes)
        # Show each repo/branch's pushes once, at its most recent push.
        key = (ev["repo"]["name"], ev["payload"].get("ref")) if ev["type"] == "PushEvent" else ev["id"]
        if not text or key in seen:
            continue
        seen.add(key)
        lines.append(f"{len(lines) + 1}. {text} <sub>· {day(ev['created_at'])}</sub>")
        if len(lines) == limit:
            break
    return "\n".join(lines) or "_Nothing public in the last 90 days._"


def replace(text, name, body):
    pattern = re.compile(rf"(<!--{name}:START-->).*?(<!--{name}:END-->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = replace(text, "REPOS", recent_repos())
    text = replace(text, "ACTIVITY", recent_activity())
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    text = replace(text, "UPDATED", f"<sub>🤖 Auto-updated {stamp}</sub>")
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
