"""Judge a Vault attempt submitted as an issue.

Visitors never post the key itself. They post sha256("<login>:<KEY>"), which
proves they know the key without leaking it to everyone reading the issues.
The key lives only in the VAULT_KEY repository secret.

Inputs come from env vars (never interpolated into shell), output is the
comment body written to vault-reply.md and the updated data/vault.json.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "data", "vault.json")

DENIED = [
    "ACCESS DENIED. The vault didn't even flinch.",
    "ACCESS DENIED. Close... or not. The vault won't tell you.",
    "ACCESS DENIED. Peel the layers in the right order.",
    "ACCESS DENIED. Remember: the hash is of `<your-username>:<KEY>`, all lowercase username.",
]


def main():
    login = os.environ["LOGIN"]
    title = os.environ.get("TITLE", "")
    key = os.environ["VAULT_KEY"].strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)

    found = re.search(r"\b[0-9a-f]{64}\b", title.lower())
    if not found:
        reply = ("### 🔐 Malformed transmission\n\nThe title needs a 64-character SHA-256 hex digest, like:\n\n"
                 "```\nvault: 3f1c...e9a0\n```\n\nCompute it with:\n\n"
                 f"```bash\nprintf '%s' \"{login.lower()}:YOUR_KEY\" | sha256sum\n```\n\nThis didn't count as an attempt.")
    else:
        expected = hashlib.sha256(f"{login.lower()}:{key}".encode()).hexdigest()
        ok = found.group(0) == expected
        already = any(s["login"].lower() == login.lower() for s in state["solvers"])
        state["attempts"] += 1
        state["last"] = {"login": login, "at": now, "ok": ok}
        if ok and not already:
            state["solvers"].append({"login": login, "at": now})
            rank = len(state["solvers"])
            reply = (f"### 🟢 ACCESS GRANTED\n\n@{login}, you cracked the vault. "
                     f"You are breach **#{rank}** of {state['attempts']} attempts.\n\n"
                     "Your name is now in the Hall of Fame on my profile. "
                     "Don't spoil the key for others. Let's connect! 🤝")
        elif ok:
            reply = f"### 🟢 Still valid\n\n@{login}, you already cracked it. Your spot in the Hall of Fame is safe."
        else:
            reply = (f"### 🔴 {DENIED[state['attempts'] % len(DENIED)]}\n\n"
                     f"Attempt **#{state['attempts']}** logged against @{login}. Try again anytime.")

    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    with open(os.path.join(ROOT, "vault-reply.md"), "w", encoding="utf-8") as f:
        f.write(reply + "\n\n<sub>🤖 judged automatically by the vault bot</sub>\n")


if __name__ == "__main__":
    main()
