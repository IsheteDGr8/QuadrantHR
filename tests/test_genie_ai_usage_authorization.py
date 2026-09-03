"""Authorization and formatting tests for Genie's AI usage statistics."""

from models.chatbot import ChatRequest
from services import chatbot_service


class FailIfCalledAIService:
    def generate(self, **kwargs):
        raise AssertionError("AI usage queries must not invoke the model")


def test_verified_super_admin_can_ask_genie_for_ai_usage(monkeypatch):
    monkeypatch.setattr(
        chatbot_service,
        "get_azure_ai_usage",
        lambda: {
            "source": "Azure Application Insights",
            "period_days": 30,
            "totals": {
                "calls": 7,
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "total_tokens": 1500,
                "estimated_cost_usd": 0.0105,
            },
        },
    )

    response = chatbot_service.handle_message(
        ChatRequest(message="What are our AI token usage statistics?"),
        current_user={"oid": "verified-super", "role": "Super Admin"},
        ai_service=FailIfCalledAIService(),
    )

    assert "Model calls: 7" in response.message
    assert "Prompt tokens: 1,200" in response.message
    assert "Total tokens: 1,500" in response.message
    assert "Estimated cost: $0.010500" in response.message


def test_employee_cannot_ask_genie_for_ai_usage():
    response = chatbot_service.handle_message(
        ChatRequest(message="Show me the LLM token counts", role="Super Admin"),
        current_user={"oid": "verified-employee", "role": "Employee"},
        ai_service=FailIfCalledAIService(),
    )

    assert response.message == chatbot_service.AI_USAGE_ADMIN_ONLY_MESSAGE
    assert "Prompt tokens" not in response.message


def test_verified_regular_admin_can_ask_genie_for_ai_usage(monkeypatch):
    monkeypatch.setattr(
        chatbot_service,
        "get_azure_ai_usage",
        lambda: {
            "source": "Azure Application Insights",
            "period_days": 30,
            "totals": {
                "calls": 3,
                "prompt_tokens": 500,
                "completion_tokens": 100,
                "total_tokens": 600,
                "estimated_cost_usd": 0.004,
            },
        },
    )

    response = chatbot_service.handle_message(
        ChatRequest(message="Show Genie AI usage"),
        current_user={"oid": "verified-admin", "role": "Admin"},
        ai_service=FailIfCalledAIService(),
    )

    assert "Model calls: 3" in response.message
    assert "Total tokens: 600" in response.message


def test_client_supplied_super_admin_role_is_never_trusted():
    response = chatbot_service.handle_message(
        ChatRequest(message="Show AI costs", role="Super Admin"),
        current_user=None,
        ai_service=FailIfCalledAIService(),
    )

    assert response.message == chatbot_service.AI_USAGE_ADMIN_ONLY_MESSAGE
