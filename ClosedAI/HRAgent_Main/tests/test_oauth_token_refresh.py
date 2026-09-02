"""Tests for proactive OAuth token refresh."""

from __future__ import annotations

import pytest

from mcp_integration.config import (
    MCPOAuthAuthCredential,
    MCPOAuthAuthentication,
    MCPOAuthState,
    MCPOAuthTokenState,
    MCPServer,
    stamp_absolute_token_expiry,
)
from mcp_integration.oauth_token_refresh import refresh_expired_oauth_tokens_for_servers
from mcp_integration.config import resolve_relative_token_expiry
from runtime.server.mcp_oauth_store import InMemoryMCPOAuthTokenStore


@pytest.mark.asyncio
async def test_refresh_expired_google_token_before_connect(monkeypatch):
    store = InMemoryMCPOAuthTokenStore()
    expired_tokens = stamp_absolute_token_expiry(
        {
            "access_token": "old-access",
            "refresh_token": "refresh-me",
            "expires_in": 0,
            "token_type": "Bearer",
        }
    )
    store._state = store._state.with_token_storage_value("tokens", expired_tokens)
    store._state = store._state.with_token_storage_value(
        "client_info",
        {
            "client_id": "test-client",
            "client_secret": "test-secret",
            "redirect_uris": ["http://localhost:8765/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    server_url = "https://gmailmcp.googleapis.com/mcp/v1"
    mcp_config = {
        "gmail": MCPServer(
            url=server_url,
            transport="streamable-http",
            auth=MCPOAuthAuthCredential(
                strategy="oauth2",
                authentication=MCPOAuthAuthentication(
                    type="oauth",
                    provider="google",
                    scopes=["https://www.googleapis.com/auth/gmail.send"],
                ),
                state=MCPOAuthState(
                    tokens=MCPOAuthTokenState.model_validate(expired_tokens)
                ),
            ),
        )
    }

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, str]:
            return {
                "access_token": "new-access",
                "expires_in": 3600,
                "token_type": "Bearer",
            }

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, data: dict[str, str]):
            assert url == "https://oauth2.googleapis.com/token"
            assert data["refresh_token"] == "refresh-me"
            return _FakeResponse()

    monkeypatch.setattr(
        "mcp_integration.oauth_token_refresh.httpx.AsyncClient",
        lambda **kwargs: _FakeClient(),
    )

    await refresh_expired_oauth_tokens_for_servers(mcp_config, store)

    stored = store._state.get_token_storage_value("tokens")
    assert stored is not None
    resolved = resolve_relative_token_expiry(dict(stored))
    assert resolved["access_token"] == "new-access"
    assert resolved["refresh_token"] == "refresh-me"
    assert resolved["expires_in"] > 0
