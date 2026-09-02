"""Slack helpers using the linked Slack MCP OAuth token (and optional bot token).

``list_slack_channels`` and ``send_slack_message`` run after HITL for sends,
mirroring Gmail: the client tool is the approval gate; this module is the
actual delivery. Prefer Slack Web API when the stored token looks like a
Slack token (xoxb-/xoxp-). Otherwise call the official Slack MCP tools
(list_channels / send_message) with the same OAuth store.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
from typing import Any

import httpx

from mcp_integration.config import MCPServer
from mcp_integration.exceptions import MCPReauthenticationRequiredError
from mcp_integration.oauth_token_refresh import refresh_expired_oauth_tokens_for_servers
from runtime.persistence import get_settings_store
from runtime.server.mcp_oauth_store import MCPSettingsOAuthTokenStore
from runtime.telemetry.logger import get_logger


logger = get_logger(__name__)

SLACK_API_BASE = "https://slack.com/api"
SLACK_MCP_SERVER_URL = "https://mcp.slack.com/mcp"
SLACK_SERVER_NAME = "slack"
_SLACK_TOKEN_RE = re.compile(r"^xox[abepsu]-", re.IGNORECASE)


class SlackChannelNotFoundError(RuntimeError):
    """Raised when the requested channel is not in the linked workspace."""

    def __init__(self, requested: str, available: list[str]):
        self.requested = requested
        self.available = available
        listed = ", ".join(f"#{n}" for n in available[:40]) or "(none visible)"
        more = "" if len(available) <= 40 else f" (+{len(available) - 40} more)"
        super().__init__(
            f"Slack channel {requested!r} does not exist in this workspace "
            f"(or this app cannot see it). Available channels: {listed}{more}. "
            "Ask the user which of these to use — do not invent a channel name."
        )


def _run_coro_sync(coro: Any, *, timeout: float = 90.0) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner() -> Any:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result(timeout=timeout)


def normalize_channel_name(channel: str) -> str:
    raw = (channel or "").strip()
    if raw.startswith("<#") and raw.endswith(">"):
        raw = raw[2:-1]
        raw = raw.split("|", 1)[0]
    if raw.startswith("#"):
        raw = raw[1:]
    return raw.strip()


def _slack_server_from_settings() -> MCPServer | None:
    store = get_settings_store()
    settings = store.load()
    if settings is None:
        return None
    return settings.agent_settings.mcp_config.get(SLACK_SERVER_NAME)


def _env_slack_token() -> str | None:
    for key in ("SLACK_BOT_TOKEN", "SLACK_USER_TOKEN", "SLACK_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


async def get_slack_access_token() -> str:
    """Return a Slack token from env or the connected Slack MCP OAuth store."""
    env_token = _env_slack_token()
    if env_token:
        return env_token

    slack = _slack_server_from_settings()
    if slack is None or not slack.url:
        raise MCPReauthenticationRequiredError(SLACK_MCP_SERVER_URL)

    token_store = MCPSettingsOAuthTokenStore()
    await refresh_expired_oauth_tokens_for_servers({SLACK_SERVER_NAME: slack}, token_store)

    tokens = await token_store.get(
        f"{slack.url.rstrip('/')}/tokens",
        collection="mcp-oauth-token",
    )
    if not tokens or not tokens.get("access_token"):
        raise MCPReauthenticationRequiredError(slack.url)

    return str(tokens["access_token"])


def get_slack_access_token_sync() -> str:
    return _run_coro_sync(get_slack_access_token())


def _is_slack_web_token(token: str) -> bool:
    return bool(_SLACK_TOKEN_RE.match(token.strip()))


async def _slack_api(method: str, token: str, **params: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{SLACK_API_BASE}/{method}",
            headers={"Authorization": f"Bearer {token}"},
            data={k: v for k, v in params.items() if v is not None},
        )
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code != 200:
        raise RuntimeError(
            f"Slack API {method} HTTP {response.status_code}: {response.text[:400]}"
        )
    if not isinstance(payload, dict):
        raise RuntimeError(f"Slack API {method} returned a non-object payload.")
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API {method} error: {payload.get('error') or payload}")
    return payload


def format_channel_digest(channels: list[dict[str, Any]]) -> str:
    if not channels:
        return (
            "No Slack channels are visible to this app. Invite the bot to a "
            "channel, or reconnect Slack from MCP Connections. If the user "
            "already named a channel, still call send_slack_message with that "
            "name — delivery will validate it."
        )
    lines = [f"Visible Slack channels ({len(channels)}):"]
    for ch in channels:
        name = ch.get("name") or ch.get("id") or "unknown"
        cid = ch.get("id") or ""
        kind = "private" if ch.get("is_private") else "public"
        member = "member" if ch.get("is_member") else "not a member"
        lines.append(f"- #{name} ({cid}, {kind}, {member})")
    lines.append(
        "If the user already named one of these, immediately call "
        "send_slack_message with that name. Only send to a listed channel; "
        "do not invent a name the user did not give you."
    )
    return "\n".join(lines)


def resolve_channel(channel: str, channels: list[dict[str, Any]]) -> dict[str, Any]:
    requested = (channel or "").strip()
    if not requested:
        raise SlackChannelNotFoundError("(empty)", [str(c.get("name") or "") for c in channels if c.get("name")])
    if requested.startswith("C") or requested.startswith("G") or requested.startswith("D"):
        for ch in channels:
            if ch.get("id") == requested:
                return ch
    name = normalize_channel_name(requested).lower()
    for ch in channels:
        if str(ch.get("name") or "").lower() == name:
            return ch
    available = [str(c.get("name")) for c in channels if c.get("name")]
    raise SlackChannelNotFoundError(requested, available)


def _mcp_text(result: Any) -> str:
    parts: list[str] = []
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return str(result)
    return "\n".join(parts)


def _tool_input_schema(tool: Any) -> dict[str, Any]:
    mcp_tool = getattr(tool, "mcp_tool", None)
    schema = getattr(mcp_tool, "inputSchema", None) if mcp_tool is not None else None
    return schema if isinstance(schema, dict) else {}


def _pick_mcp_tool(tools: list[Any], hints: tuple[str, ...]) -> Any:
    lowered = [(t, str(getattr(t, "name", "")).lower()) for t in tools]
    for hint in hints:
        for tool, name in lowered:
            if name == hint or name.endswith(hint) or hint in name:
                return tool
    names = [getattr(t, "name", "?") for t in tools]
    raise RuntimeError(
        f"Slack MCP has no tool matching {hints}. Available tools: {names}"
    )


def _send_mcp_arguments(channel: str, message: str, schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    args: dict[str, Any] = {}
    if "channel_id" in props:
        args["channel_id"] = channel
    elif "channel" in props:
        args["channel"] = channel
    else:
        args["channel"] = channel
    if "text" in props:
        args["text"] = message
    elif "message" in props:
        args["message"] = message
    else:
        args["text"] = message
    return args


def _parse_mcp_channels(text: str) -> list[dict[str, Any]]:
    """Best-effort parse of Slack MCP list_channels output into {id,name} rows."""
    channels: list[dict[str, Any]] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    rows: list[Any] = []
    if isinstance(payload, dict):
        for key in ("channels", "results", "data"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    elif isinstance(payload, list):
        rows = payload
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("channel") or row.get("channel_name")
        cid = row.get("id") or row.get("channel_id")
        if name or cid:
            channels.append(
                {
                    "id": cid,
                    "name": normalize_channel_name(str(name or cid)),
                    "is_private": bool(row.get("is_private") or row.get("private")),
                    "is_member": row.get("is_member", True),
                }
            )
    if channels:
        return channels
    for match in re.finditer(r"#([a-z0-9][a-z0-9_-]{0,79})", text, flags=re.IGNORECASE):
        name = match.group(1)
        if not any(c.get("name") == name for c in channels):
            channels.append({"id": name, "name": name, "is_private": False, "is_member": True})
    return channels


def _with_slack_mcp(fn: Any) -> Any:
    from mcp_integration.utils import create_mcp_tools

    slack = _slack_server_from_settings()
    if slack is None or not slack.url:
        raise MCPReauthenticationRequiredError(SLACK_MCP_SERVER_URL)
    token_store = MCPSettingsOAuthTokenStore()
    with create_mcp_tools(
        {SLACK_SERVER_NAME: slack},
        timeout=45.0,
        mcp_oauth_token_storage=token_store,
    ) as client:
        return fn(client)


def _invoke_slack_mcp(client: Any, tool_hints: tuple[str, ...], arguments: dict[str, Any]) -> str:
    tool = _pick_mcp_tool(list(client.tools), tool_hints)
    result = client.call_async_from_sync(
        client.call_tool_mcp,
        timeout=45.0,
        name=tool.name,
        arguments=arguments or {},
    )
    text = _mcp_text(result)
    if getattr(result, "isError", False):
        raise RuntimeError(text or f"Slack MCP tool {tool.name} failed.")
    return text


async def list_slack_channels(*, limit: int = 200) -> list[dict[str, Any]]:
    token = await get_slack_access_token()
    if _is_slack_web_token(token):
        try:
            channels: list[dict[str, Any]] = []
            cursor = None
            remaining = max(1, min(int(limit), 1000))
            while remaining > 0:
                page = min(remaining, 200)
                payload = await _slack_api(
                    "conversations.list",
                    token,
                    types="public_channel,private_channel",
                    exclude_archived="true",
                    limit=str(page),
                    cursor=cursor or None,
                )
                for ch in payload.get("channels") or []:
                    if isinstance(ch, dict):
                        channels.append(
                            {
                                "id": ch.get("id"),
                                "name": ch.get("name"),
                                "is_private": bool(ch.get("is_private")),
                                "is_member": bool(ch.get("is_member")),
                            }
                        )
                cursor = (payload.get("response_metadata") or {}).get("next_cursor") or ""
                remaining -= page
                if not cursor:
                    break
            return channels
        except RuntimeError as exc:
            err = str(exc).lower()
            if "invalid_auth" not in err and "not_authed" not in err:
                raise
            logger.warning("Slack Web API list failed (%s); falling back to Slack MCP", exc)

    def _list(client: Any) -> list[dict[str, Any]]:
        tool = _pick_mcp_tool(list(client.tools), ("list_channels", "list-channels"))
        schema = _tool_input_schema(tool)
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        args: dict[str, Any] = {}
        if "limit" in props:
            args["limit"] = limit
        text = _invoke_slack_mcp(client, ("list_channels", "list-channels"), args)
        parsed = _parse_mcp_channels(text)
        if parsed:
            return parsed
        return [{"id": "", "name": text[:80], "is_private": False, "is_member": True, "raw": text}]

    return _with_slack_mcp(_list)


def list_slack_channels_sync(*, limit: int = 200) -> list[dict[str, Any]]:
    return _run_coro_sync(list_slack_channels(limit=limit))


async def send_slack_message(*, channel: str, message: str) -> dict[str, Any]:
    requested = (channel or "").strip()
    text = (message or "").strip()
    if not requested or not text:
        raise RuntimeError("send_slack_message requires channel and message.")

    token = await get_slack_access_token()
    if _is_slack_web_token(token):
        channels = await list_slack_channels()
        target = resolve_channel(requested, channels)
        dest = str(target.get("id") or target.get("name"))
        try:
            payload = await _slack_api(
                "chat.postMessage",
                token,
                channel=dest,
                text=text,
            )
        except RuntimeError as exc:
            err = str(exc).lower()
            if "not_in_channel" in err:
                raise RuntimeError(
                    f"The Slack app is not a member of #{target.get('name') or dest}. "
                    "Invite the bot into that channel, then retry."
                ) from exc
            raise
        return {
            "channel": dest,
            "name": target.get("name") or dest,
            "ts": payload.get("ts"),
        }

    channels = await list_slack_channels()
    real_names = [str(c.get("name")) for c in channels if c.get("name") and not c.get("raw")]
    if real_names:
        target = resolve_channel(requested, channels)
        dest = str(target.get("id") or target.get("name") or requested)
    else:
        dest = requested if requested.startswith(("C", "G", "D", "#")) else f"#{normalize_channel_name(requested)}"

    def _send(client: Any) -> dict[str, Any]:
        tool = _pick_mcp_tool(list(client.tools), ("send_message", "post_message", "post-message"))
        args = _send_mcp_arguments(dest, text, _tool_input_schema(tool))
        result_text = _invoke_slack_mcp(
            client,
            ("send_message", "post_message", "post-message"),
            args,
        )
        if re.search(
            r"channel_not_found|not_in_channel|invalid_channel|unknown_channel",
            result_text,
            re.I,
        ):
            raise SlackChannelNotFoundError(requested, real_names)
        return {
            "channel": dest,
            "name": normalize_channel_name(str(dest)),
            "result": result_text,
        }

    return _with_slack_mcp(_send)


def send_slack_message_sync(*, channel: str, message: str) -> dict[str, Any]:
    return _run_coro_sync(send_slack_message(channel=channel, message=message))
