from typing import List


def build_policy_prompt(
    company_name: str,
    policy_type: str,
    tone: str,
    requirements: List[str],
    title: str | None = None,
) -> str:
    requirements_text = "\n".join(
        f"- {requirement}" for requirement in requirements
    )

    # "Custom Section" isn't itself a topic — it's just the category for
    # anything that doesn't fit the predefined policy types. Without a
    # real subject, the AI has nothing concrete to write about (it would
    # otherwise be told to write a "Custom Section policy", which means
    # nothing). The caller-supplied title is the actual subject in that
    # case; for predefined types, policy_type already is the subject.
    subject = title if (policy_type == "Custom Section" and title) else policy_type

    prompt = f"""
You are an experienced HR policy writer.

Create a complete {tone.lower()} policy titled "{subject}" for {company_name}.

Organization requirements:
{requirements_text}

Include these sections:
1. Policy title
2. Purpose
3. Scope
4. Eligibility
5. Policy guidelines
6. Employee responsibilities
7. Manager responsibilities
8. Compliance
9. Review and approval

Write clearly and professionally.
Return only the completed policy document.
"""

    return prompt.strip()


def build_policy_chat_prompt(messages: list[dict]) -> str:
    conversation_text = "\n".join(
        f"{'HR' if m['role'] == 'user' else 'Assistant'}: {m['text']}"
        for m in messages
    )

    questions_asked = sum(1 for m in messages if m["role"] == "assistant")

    # Without an explicit budget, "ask a follow-up if it'd help" has no
    # natural stopping point and the model can keep finding one more
    # thing to ask about indefinitely - which is exactly what was
    # happening (conversations running past 10+ questions with no READY,
    # eventually hitting the backend's message-count cap and failing
    # outright rather than ever converging).
    if questions_asked >= 6:
        urgency = (
            "You MUST respond with READY now, even if some details are "
            "still unclear - draft with reasonable defaults for anything "
            "unanswered rather than asking more.\n"
        )
    elif questions_asked >= 4:
        urgency = (
            "You've already asked several questions - lean toward READY "
            "now unless something genuinely critical (who it applies to, "
            "or the core rule itself) is still completely missing.\n"
        )
    else:
        urgency = ""

    prompt = f"""
You are an HR policy consultant helping someone draft a new company policy
section through a short conversation.

Conversation so far:
{conversation_text}

Ask ONE focused follow-up question that would help you understand what this
policy should actually say — who it applies to, the specific rules, or any
exceptions. Base it on what has and hasn't been covered already; do not
repeat something already answered.

If the conversation already covers enough (who it applies to, the key
rules, and any exceptions) to draft a complete policy, respond with exactly:
READY

{urgency}Return only the question, or the word READY — nothing else.
"""
    return prompt.strip()