import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from prompt_builder import build_policy_prompt, build_policy_chat_prompt


def test_predefined_policy_type_uses_policy_type_as_subject():
    prompt = build_policy_prompt(
        company_name="Acme Corp",
        policy_type="Security Policy",
        tone="Professional",
        requirements=["Use MFA."],
    )

    assert 'titled "Security Policy"' in prompt


def test_custom_section_uses_title_as_subject():
    prompt = build_policy_prompt(
        company_name="Acme Corp",
        policy_type="Custom Section",
        tone="Professional",
        requirements=["No pets in the server room."],
        title="Office Pet Policy",
    )

    assert 'titled "Office Pet Policy"' in prompt
    assert "Custom Section" not in prompt


def test_custom_section_without_title_falls_back_to_policy_type():
    # main.py's PolicyRequest validation should prevent this in practice,
    # but the prompt builder itself shouldn't produce something worse than
    # the pre-fix behavior if it's ever called without a title.
    prompt = build_policy_prompt(
        company_name="Acme Corp",
        policy_type="Custom Section",
        tone="Professional",
        requirements=["Something."],
    )

    assert 'titled "Custom Section"' in prompt


def _messages(user_turns):
    # Alternates user/assistant, ending on a user turn - matches the real
    # shape PolicyChatCreate.jsx sends.
    messages = []
    for i in range(user_turns):
        messages.append({"role": "user", "text": f"answer {i}"})
        if i < user_turns - 1:
            messages.append({"role": "assistant", "text": f"question {i}"})
    return messages


def test_short_conversation_has_no_urgency_nudge():
    prompt = build_policy_chat_prompt(_messages(2))

    assert "lean toward READY" not in prompt
    assert "MUST respond with READY" not in prompt


def test_conversation_with_four_questions_gets_soft_nudge():
    prompt = build_policy_chat_prompt(_messages(5))  # 4 assistant turns

    assert "lean toward READY" in prompt
    assert "MUST respond with READY" not in prompt


def test_conversation_with_six_questions_gets_hard_nudge():
    prompt = build_policy_chat_prompt(_messages(7))  # 6 assistant turns

    assert "MUST respond with READY" in prompt
