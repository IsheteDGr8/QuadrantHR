"""Verify HR skills are discovered, loaded, and invocable by the real system.

Run from HRAgent_Main:  python scripts/verify_skills.py
Exit code is non-zero if any check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_SKILLS_DIR = Path(__file__).resolve().parents[1] / ".HRAgent" / "skills"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  {status}  {name}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def _repo_skill_names() -> set[str]:
    if not REPO_SKILLS_DIR.is_dir():
        return set()
    return {
        p.name
        for p in REPO_SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    }


# 1) Repo catalog size and legacy dummy removal
repo_names = _repo_skill_names()
check("repo has skills catalog", len(repo_names) >= 100, f"count={len(repo_names)}")
check("hr-onboarding present in repo", "hr-onboarding" in repo_names)
check("legacy hr-employee-transfer removed", "hr-employee-transfer" not in repo_names)
check("legacy hr-pto-leave removed", "hr-pto-leave" not in repo_names)

# 2) User-scope discovery (what the chat backend uses: load_user_skills=true)
from skills import load_user_skills

user_skills = {s.name: s for s in load_user_skills()}
check("user skills discovered", len(user_skills) >= 100, f"count={len(user_skills)}")

# Spot-check representative pack skills
SPOT_CHECK = [
    "hr-onboarding",
    "hr-offboarding",
    "hr-recruiting",
    "hr-job-description",
    "hr-performance-management",
    "hr-total-rewards",
]
for name in SPOT_CHECK:
    s = user_skills.get(name)
    check(f"discovered: {name}", s is not None)
    if s is not None:
        check(
            f"agentskills format + invocable: {name}",
            bool(s.is_agentskills_format) and not s.disable_model_invocation,
        )

# 3) Onboarding: operational content + triggers (priority merge)
onboarding = user_skills.get("hr-onboarding")
if onboarding:
    body = onboarding.content or ""
    for needle in (
        "office_fill_pdf_form",
        "office_fill_docx_form",
        "send_email",
        "outputs/",
        "i9_form.pdf",
        "Operational Guide",
    ):
        check(f"onboarding operational content: {needle!r}", needle in body)
    check(
        "onboarding has keyword triggers",
        onboarding.trigger is not None,
        type(onboarding.trigger).__name__ if onboarding.trigger else "None",
    )
    matched = bool(onboarding.trigger and onboarding.match_trigger("help me onboard a new hire"))
    check("onboarding trigger matches sample query", matched)

# 4) Catalog appears in system prompt via AgentContext
from context import AgentContext

ctx = AgentContext(load_user_skills=True)
suffix = ctx.get_system_message_suffix() or ""
check("onboarding listed in system prompt catalog", "hr-onboarding" in suffix)
check("recruiting listed in system prompt catalog", "hr-recruiting" in suffix)
check("invoke_skill guidance present in prompt", "invoke_skill" in suffix)

# 5) invoke_skill executor returns real content (progressive disclosure)
from types import SimpleNamespace

from tools.builtins.invoke_skill import (
    InvokeSkillAction,
    InvokeSkillExecutor,
    InvokeSkillTool,
)

check("InvokeSkillTool importable", InvokeSkillTool is not None)

fake_conv = SimpleNamespace(
    state=SimpleNamespace(
        agent=SimpleNamespace(
            agent_context=SimpleNamespace(skills=list(user_skills.values()))
        ),
        workspace=SimpleNamespace(working_dir=None),
        invoked_skills=[],
    )
)
executor = InvokeSkillExecutor()

invoke_probes = {
    "hr-onboarding": "Operational Guide",
    "hr-recruiting": "recruit",
    "hr-offboarding": "offboard",
}
for name, needle in invoke_probes.items():
    obs = executor(InvokeSkillAction(name=name), conversation=fake_conv)
    body = obs.text or ""
    check(
        f"invoke_skill returns content: {name}",
        (not obs.is_error) and needle.lower() in body.lower() and len(body) > 200,
        f"error={obs.is_error} len={len(body)}",
    )

bad = executor(InvokeSkillAction(name="does-not-exist"), conversation=fake_conv)
check("unknown skill errors cleanly", bool(bad.is_error) and "Unknown skill" in (bad.text or ""))

print()
if failures:
    print(f"RESULT: {len(failures)} failed -> {', '.join(failures)}")
    raise SystemExit(1)
print("RESULT: all checks passed")
