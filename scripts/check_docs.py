import re
from pathlib import Path

errors = []
for repo in sorted(Path(".").glob("nexus-atom-*")):
    for file in repo.rglob("*.md"):
        if any(part in {".git", ".atom", "dist"} for part in file.parts):
            continue
        for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", file.read_text()):
            link = raw.split()[0].strip("<>")
            if ":" in link or link.startswith("#"):
                continue
            target = (file.parent / link.split("#")[0]).resolve()
            if not target.exists():
                errors.append(f"{file}: {link}")
print("\n".join(errors) if errors else "All repository-local Markdown links resolve.")
raise SystemExit(bool(errors))
