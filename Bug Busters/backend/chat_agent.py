import json

from openai_service import OpenAIService
from demo_login_repository import list_users
from logger import get_logger

logger = get_logger(__name__)

# Kept short and generic on purpose - the widget appears on the public
# Landing page (no signed-in user, no org context) as well as HRDashboard,
# so the prompt can't assume a role or reference a specific policy the way
# /ask-ai does for highlighted text.
SYSTEM_CONTEXT = """You are the small help-chat widget on Policy Guardian, \
an internal HR policy platform for Quadrant Technologies. Visitors may not \
be signed in yet.

Scope: you ONLY answer questions about Quadrant Technologies, its people/ \
team/roles (see the directory below), its policies, or how to use this \
Policy Guardian platform. For anything else - general knowledge, public \
figures, unrelated topics, anything not about this company or app - do \
NOT answer it. Instead reply briefly that you can only help with \
Quadrant Technologies/policy questions.

Answer briefly and helpfully within that scope. If the question needs \
specifics you don't have (a company's actual policy text, an account, a \
signed-in role), say so plainly and point them to signing in or asking \
HR - don't invent company-specific policy details."""

MAX_CHARS_FOR_MESSAGE = 2000


class ChatAgentError(Exception):
    """Raised when the chat backend can't produce a reply - callers should
    show a generic "try again" message rather than a fabricated answer."""


def _build_roster_context() -> str:
    try:
        users = list_users()
    except Exception as exc:
        logger.warning(f"Could not load roster for chat context: {exc}")
        return ""

    if not users:
        return ""

    lines = "\n".join(f"- {u['display_name']} ({u['email']}) - {u['role']}" for u in users)

    return f"\n\nQuadrant Technologies team directory (use this to answer " \
           f"\"who is X\" questions - don't guess beyond it):\n{lines}"


def _build_prompt(message: str) -> str:
    return f"""{SYSTEM_CONTEXT}{_build_roster_context()}

User message:
{message[:MAX_CHARS_FOR_MESSAGE]}

Reply directly to the user - no preamble, no restating the question."""


def answer_chat_message(message: str) -> str:
    if not message.strip():
        raise ChatAgentError("message is empty - nothing to answer.")

    service = OpenAIService()
    prompt = _build_prompt(message)

    try:
        reply = service.generate_policy(prompt)
    except Exception as exc:
        raise ChatAgentError(f"LLM call failed: {exc}") from exc

    reply = reply.strip()

    if not reply:
        raise ChatAgentError("LLM returned an empty reply.")

    return reply


# --------------------------------------------------
# Chat-driven actions (theme switching, page navigation)
#
# Classified by the LLM, not string/regex matching - people phrase "make
# it dark" a hundred different ways ("dark mode", "dark theme", "make it
# darker", "night mode", "switch to light"...), and a fixed keyword list
# is exactly the kind of thing that quietly breaks the moment someone
# phrases it differently. The frontend still owns actually performing the
# action (theme/localStorage, setView) - this only decides what they meant.
# --------------------------------------------------

VALID_THEMES = {"dark", "light"}
VALID_INTENTS = {"set_theme", "navigate", "other"}


def _build_intent_prompt(message: str, screens: list[dict]) -> str:
    screens_list = "\n".join(f'- id: "{s["id"]}", name: "{s["name"]}"' for s in screens) or "(none provided)"

    return f"""You are the action-classifier for Buggy, the small chat widget on \
Policy Guardian (an internal HR policy platform). Given one user message, decide \
whether they want to (a) change the app's visual theme, (b) navigate to a \
specific screen, or (c) neither. Judge by meaning, not fixed keywords - "dark \
theme", "dark mode", "make it darker", "night mode", and "switch to light" all \
mean set_theme; "go to", "open", "take me to", "show me", and "switch to" + a \
screen name all mean navigate.

Available screens (screen_id must be exactly one of these ids, or null):
{screens_list}

User message:
{message[:MAX_CHARS_FOR_MESSAGE]}

Return ONLY JSON, no other text, in exactly this shape:
{{"intent": "set_theme" | "navigate" | "other", "theme": "dark" | "light" | null, "screen_id": "<id from the list above>" | null}}

Rules:
- intent "set_theme": only when the user clearly wants a dark or light \
appearance. theme must be exactly "dark" or "light" - if they want something \
else (a specific color, font, text size), use intent "other" instead.
- intent "navigate": only when one of the screens above is a good match for \
where they're asking to go. screen_id must come from the list above - never \
invent one.
- Otherwise use intent "other" with theme and screen_id both null."""


def _parse_intent(raw_response: str, valid_ids: set[str]) -> dict:
    cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ChatAgentError(f"LLM returned unparseable intent: {raw_response!r}") from exc

    if not isinstance(parsed, dict):
        raise ChatAgentError("LLM intent response was not a JSON object.")

    intent = parsed.get("intent")
    if intent not in VALID_INTENTS:
        intent = "other"

    theme = parsed.get("theme")
    if theme not in VALID_THEMES:
        theme = None

    screen_id = parsed.get("screen_id")
    if screen_id not in valid_ids:
        screen_id = None

    if intent == "set_theme" and theme is None:
        intent = "other"

    if intent == "navigate" and screen_id is None:
        intent = "other"

    return {
        "intent": intent,
        "theme": theme if intent == "set_theme" else None,
        "screen_id": screen_id if intent == "navigate" else None,
    }


def interpret_chat_intent(message: str, screens: list[dict]) -> dict:
    if not message.strip():
        raise ChatAgentError("message is empty - nothing to interpret.")

    service = OpenAIService()
    prompt = _build_intent_prompt(message, screens)

    try:
        raw_response = service.generate_policy(prompt)
    except Exception as exc:
        raise ChatAgentError(f"LLM call failed: {exc}") from exc

    return _parse_intent(raw_response, valid_ids={s["id"] for s in screens})
