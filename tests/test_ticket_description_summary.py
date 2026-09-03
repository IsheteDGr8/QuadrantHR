"""
Ticket draft description/title quality tests.

Previously, ticket_draft_service._merge_description() concatenated each
turn's newly-extracted text onto the running draft description, so a
multi-turn conversation produced a growing, transcript-like description.
The fix is two-part:
- chatbot_agent.CHATBOT_DECISION_PROMPT now instructs GPT to return the
  full, up-to-date, concise (~3-4 sentence) summary of the whole
  conversation every turn - not just this turn's new sentence.
- _merge_description() now REPLACES the running description with a fresh
  non-empty extraction instead of appending to it, since GPT is expected
  to already include everything relevant.

We cannot make live GPT calls in tests, so:
- the merge-layer (deterministic, testable) behavior is tested directly
  with realistic fixture text a real GPT-5.2 call would plausibly return
  each turn.
- the prompt's instructions are checked structurally (key constraints
  present), not pinned to exact wording - per this task's explicit
  "do not write brittle tests requiring one exact sentence" guidance.
"""

from agents.chatbot_agent import CHATBOT_DECISION_PROMPT, ExtractedTicketFields
from models.chatbot import ChatIntent, TicketDraft
from services.ticket_draft_service import _fallback_title, merge_extracted_fields

VPN_TURN_1 = ExtractedTicketFields(
    title="VPN not working", description="The VPN is not connecting."
)
VPN_TURN_2 = ExtractedTicketFields(
    title="VPN connection timeout on Mac",
    description=(
        "The VPN has not been connecting on the user's Mac; the connection "
        "attempt times out."
    ),
)
VPN_TURN_3_FINAL = ExtractedTicketFields(
    title="VPN connection timeout on Mac",
    description=(
        "The VPN has not been connecting since this morning on the user's "
        "Mac. The connection attempt times out, preventing access to "
        "company resources. The issue is currently blocking normal work "
        "and still persists."
    ),
)


def _draft_after_turns(*turns: ExtractedTicketFields) -> TicketDraft:
    draft = None
    for turn in turns:
        draft, _missing = merge_extracted_fields(
            turn,
            existing_draft=draft,
            gpt_missing_fields=[],
            intent=ChatIntent.SUPPORT_ISSUE,
        )
    return draft


def test_multi_turn_conversation_becomes_final_summary_not_transcript():
    draft = _draft_after_turns(VPN_TURN_1, VPN_TURN_2, VPN_TURN_3_FINAL)
    # The final draft is GPT's latest full synthesis, not a concatenation
    # of all three turns' text (the old, broken behavior).
    assert draft.description == VPN_TURN_3_FINAL.description
    assert VPN_TURN_1.description not in draft.description
    assert draft.description.count("VPN has not been connecting") == 1


def test_repeated_information_is_not_duplicated():
    same_text = ExtractedTicketFields(description="My VPN is not working.")
    draft = _draft_after_turns(same_text, same_text, same_text)
    assert draft.description.count("My VPN is not working.") == 1


def test_important_earlier_facts_are_not_silently_dropped_by_the_merge_layer():
    # The merge layer must faithfully carry forward whatever GPT includes
    # in its latest full synthesis (GPT itself is instructed to preserve
    # earlier facts - see the prompt-content check below).
    draft = _draft_after_turns(VPN_TURN_1, VPN_TURN_3_FINAL)
    assert "this morning" in draft.description
    assert "Mac" in draft.description
    assert "company resources" in draft.description


def test_final_description_is_reasonably_concise():
    draft = _draft_after_turns(VPN_TURN_1, VPN_TURN_2, VPN_TURN_3_FINAL)
    sentence_count = draft.description.count(".")
    assert sentence_count <= 5
    assert len(draft.description.split()) < 80


def test_title_stays_concise_across_turns():
    draft = _draft_after_turns(VPN_TURN_1, VPN_TURN_2, VPN_TURN_3_FINAL)
    assert len(draft.title.split()) <= 10


def test_fallback_title_when_none_extracted_is_still_short():
    title = _fallback_title(
        "The VPN has not been connecting since this morning on the user's "
        "Mac and is blocking work.",
    )
    assert len(title.split()) <= 10


def test_prompt_instructs_full_resynthesis_not_incremental_append():
    assert "re-synthesize" in CHATBOT_DECISION_PROMPT.lower() or (
        "replacing" in CHATBOT_DECISION_PROMPT.lower()
        and "previous description" in CHATBOT_DECISION_PROMPT.lower()
    )


def test_prompt_sets_a_concise_sentence_target():
    assert "3-4 sentence" in CHATBOT_DECISION_PROMPT


def test_prompt_forbids_inventing_details():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "never invent" in lowered


def test_prompt_forbids_repeating_facts_and_verbatim_quoting():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "never state the same fact twice" in lowered
    assert "verbatim" in lowered


def test_prompt_requires_preserving_earlier_facts():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "preserve every important fact" in lowered


def test_prompt_keeps_title_short_and_descriptive():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "title" in lowered
    assert "3-8 words" in CHATBOT_DECISION_PROMPT
