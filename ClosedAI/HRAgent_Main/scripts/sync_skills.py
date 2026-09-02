"""Install the repo's canonical HR skills into the user skills directory.

The chat backend is started with ``agent_context.load_user_skills = true``, which
discovers skills from ``~/.HRAgent/skills/`` (see ``skills.load_user_skills`` /
``USER_SKILLS_DIRS``). We keep the source-of-truth copies versioned in the repo
under ``HRAgent_Main/.HRAgent/skills/`` and sync them into the user directory so
the running agent picks them up without any code change.

We intentionally do NOT rely on ``load_project_skills`` for these, because that
loader also scans the git repo root and would pull unrelated ``.agents/skills``
IDE skills into the HR agent's catalog.

Usage:
    python scripts/sync_skills.py           # copy repo skills -> ~/.HRAgent/skills
    python scripts/sync_skills.py --list    # show what would be synced, no writes
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Repo skills live next to this script: HRAgent_Main/.HRAgent/skills/<name>/SKILL.md
REPO_SKILLS_DIR = Path(__file__).resolve().parents[1] / ".HRAgent" / "skills"
USER_SKILLS_DIR = Path.home() / ".HRAgent" / "skills"


def _discover() -> list[Path]:
    """Return every skill directory under the repo that contains SKILL.md."""
    if not REPO_SKILLS_DIR.is_dir():
        return []
    found: list[Path] = []
    for child in sorted(REPO_SKILLS_DIR.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            found.append(child)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show what would be synced without writing anything.",
    )
    args = parser.parse_args()

    sources = _discover()
    if not sources:
        print("No skills found in repo; nothing to do.", file=sys.stderr)
        return 1

    print(f"Repo skills:  {REPO_SKILLS_DIR}")
    print(f"User skills:  {USER_SKILLS_DIR}")
    print(f"Skills found: {len(sources)}")
    print()

    if args.list:
        for src in sources:
            print(f"  would sync: {src.name}")
        return 0

    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for src in sources:
        dest = USER_SKILLS_DIR / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        print(f"  synced: {src.name} -> {dest}")

    print(f"\nDone. Synced {len(sources)} skills. Restart the backend to re-scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
