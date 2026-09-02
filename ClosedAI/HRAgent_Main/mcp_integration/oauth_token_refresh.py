"""Proactive OAuth access-token refresh before MCP runtime connections.

FastMCP's OAuth client often receives 401 from tool-gated providers (Google
Gmail MCP included) and then attempts a full interactive authorization flow.
Runtime connections use ``RuntimeOnlyOAuth``, which raises
``MCPReauthenticationRequiredError`` at that point — but the underlying HTTPX
auth generator can leave ``list_tools`` blocked until the outer timeout fires.

Refreshing expired access tokens *before* ``client.connect()`` avoids that
slow failure mode when a still-valid refresh token is available.
"""

from __future__ import annotations

from typing import Any

import httpx
from key_value.aio.protocols import AsyncKeyValue

from mcp_integration.config import (
    MCPOAuthAuthCredential,
    MCPServer,
    resolve_relative_token_expiry,
    stamp_absolute_token_expiry,
)
from mcp_integration.exceptions import MCPReauthenticationRequiredError
from runtime.telemetry.logger import get_logger


logger = get_logger(__name__)

# Refresh when the access token expires within this many seconds.
_REFRESH_SKEW_SECS = 120

_PROVIDER_TOKEN_ENDPOINTS: dict[str, str] = {
    "google": "https://oauth2.googleapis.com/token",
}


def _token_endpoint(provider: str | None) -> str | None:
    if provider is None:
        return None
    return _PROVIDER_TOKEN_ENDPOINTS.get(provider)


async def _storage_get(
    store: AsyncKeyValue,
    server_url: str,
    suffix: str,
    collection: str,
) -> dict[str, Any] | None:
    key = f"{server_url.rstrip('/')}{suffix}"
    value = await store.get(key, collection=collection)
    return dict(value) if isinstance(value, dict) else None


async def _storage_put(
    store: AsyncKeyValue,
    server_url: str,
    suffix: str,
    collection: str,
    value: dict[str, Any],
) -> None:
    key = f"{server_url.rstrip('/')}{suffix}"
    await store.put(key, value, collection=collection)


async def _refresh_access_token(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str | None,
    refresh_token: str,
) -> dict[str, Any]:
    payload: dict[str, str] = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        payload["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(token_endpoint, data=payload)
        if response.status_code != 200:
            raise MCPReauthenticationRequiredError(token_endpoint)
        body = response.json()
        if not isinstance(body, dict) or not body.get("access_token"):
            raise MCPReauthenticationRequiredError(token_endpoint)
        return body


async def refresh_expired_oauth_tokens_for_servers(
    mcp_config: dict[str, MCPServer],
    token_store: AsyncKeyValue | None,
) -> None:
    """Refresh soon-to-expire OAuth access tokens for configured MCP servers."""
    if token_store is None:
        return

    for server_name, server in mcp_config.items():
        auth = server.auth
        if not isinstance(auth, MCPOAuthAuthCredential):
            continue
        server_url = server.url
        if not server_url:
            continue
        authentication = auth.authentication
        provider = authentication.provider if authentication else None
        token_endpoint = _token_endpoint(provider)
        if token_endpoint is None:
            continue

        tokens = await _storage_get(
            token_store, server_url, "/tokens", "mcp-oauth-token"
        )
        if not tokens:
            continue

        tokens = resolve_relative_token_expiry(dict(tokens))
        expires_in = tokens.get("expires_in")
        remaining = int(expires_in) if isinstance(expires_in, (int, float)) else 0
        refresh_token = tokens.get("refresh_token")
        if remaining > _REFRESH_SKEW_SECS or not refresh_token:
            continue

        client_info = await _storage_get(
            token_store, server_url, "/client_info", "mcp-oauth-client-info"
        )
        if not client_info or not client_info.get("client_id"):
            raise MCPReauthenticationRequiredError(server_url)

        client_secret = client_info.get("client_secret")
        try:
            refreshed = await _refresh_access_token(
                token_endpoint=token_endpoint,
                client_id=str(client_info["client_id"]),
                client_secret=str(client_secret) if client_secret else None,
                refresh_token=str(refresh_token),
            )
        except MCPReauthenticationRequiredError:
            logger.warning(
                "OAuth refresh failed for MCP server %r; reconnect from MCP Settings",
                server_name,
            )
            raise MCPReauthenticationRequiredError(server_url) from None

        merged = dict(tokens)
        merged.update(refreshed)
        if "refresh_token" not in refreshed and refresh_token:
            merged["refresh_token"] = refresh_token
        merged = stamp_absolute_token_expiry(merged)

        await _storage_put(
            token_store,
            server_url,
            "/tokens",
            "mcp-oauth-token",
            merged,
        )
        logger.info(
            "Refreshed OAuth access token for MCP server %r (was %ss remaining)",
            server_name,
            remaining,
        )
