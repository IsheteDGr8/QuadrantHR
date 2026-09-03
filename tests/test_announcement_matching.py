from services.announcement_match_service import find_matching_announcement

ANNOUNCEMENTS = [
    {
        "id": "anc-vpn",
        "title": "VPN service outage",
        "content": "Remote access is unavailable while the network team restores service.",
        "category": "IT System Update",
    },
    {
        "id": "anc-policy",
        "title": "Updated expense reimbursement policy",
        "content": "Review the new receipt and travel expense requirements.",
        "category": "Policy Update",
    },
]


def test_matches_ticket_to_active_service_announcement():
    result = find_matching_announcement(
        "VPN is not working",
        "I cannot connect remotely to the company network.",
        ANNOUNCEMENTS,
    )

    assert result is not None
    assert result["announcement"]["id"] == "anc-vpn"
    assert "vpn" in result["matched_terms"]


def test_matches_policy_question_using_multiple_meaningful_terms():
    result = find_matching_announcement(
        "Travel expense question",
        "Where can I find the updated receipt reimbursement requirements?",
        ANNOUNCEMENTS,
    )

    assert result is not None
    assert result["announcement"]["id"] == "anc-policy"


def test_does_not_warn_for_unrelated_ticket():
    result = find_matching_announcement(
        "Laptop keyboard replacement",
        "Several keys are physically broken and need replacement.",
        ANNOUNCEMENTS,
    )

    assert result is None


def test_generic_single_word_does_not_trigger_false_positive():
    result = find_matching_announcement(
        "Policy access",
        "I need access to an unrelated document.",
        ANNOUNCEMENTS,
    )

    assert result is None


def test_matches_wifi_ticket_to_announcement_describing_issues():
    result = find_matching_announcement(
        "Difficulty connecting to wifi",
        "I cannot get online from the office.",
        [
            {
                "id": "anc-wifi",
                "title": "Office wide wifi issues",
                "content": "The technology team is investigating.",
                "category": "IT System Update",
            }
        ],
    )

    assert result is not None
    assert result["announcement"]["id"] == "anc-wifi"
    assert "wifi" in result["matched_terms"]
