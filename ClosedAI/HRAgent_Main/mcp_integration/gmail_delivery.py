"""Gmail REST helpers using OAuth tokens from MCP settings.

Outbound: ``send_email`` delivers via ``users.messages.send`` after HITL
approval (Google's hosted Gmail MCP has unreliable create_draft / no attach).

Inbound: ``list_emails`` reads the inbox via ``users.messages.list`` +
``users.messages.get`` so the agent never has to activate the Gmail MCP
server (which times out on connect).
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import json
import os
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Sequence

import httpx

from mcp_integration.config import MCPServer
from mcp_integration.exceptions import MCPReauthenticationRequiredError
from mcp_integration.oauth_token_refresh import refresh_expired_oauth_tokens_for_servers
from runtime.persistence import get_settings_store
from runtime.server.mcp_oauth_store import MCPSettingsOAuthTokenStore
from runtime.telemetry.logger import get_logger


logger = get_logger(__name__)

GMAIL_MCP_SERVER_URL = "https://gmailmcp.googleapis.com/mcp/v1"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GMAIL_SERVER_NAME = "gmail"


def _run_coro_sync(coro: Any, *, timeout: float = 90.0) -> Any:
    """Run an async coroutine from sync tool executors.

    Agent loops already own an event loop, so ``asyncio.run`` raises
    ``RuntimeError``. When a loop is running, execute on a worker thread
    with its own loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner() -> Any:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result(timeout=timeout)


def _workspace_root() -> Path:
    env = os.environ.get("HRAGENT_WORKSPACE_DIR")
    here = Path(__file__).resolve()
    hragent_main = here.parents[1]
    if env:
        root = Path(env)
        if not root.is_absolute():
            root = hragent_main / root
        return root.resolve()
    return (hragent_main / "workspace").resolve()


def resolve_workspace_file(file_path: str) -> Path:
    """Resolve a workspace-relative path (or basename) to an existing file."""
    raw = Path(file_path.replace("\\", "/"))
    root = _workspace_root()
    basename = raw.name
    candidates = [
        raw if raw.is_absolute() else root / raw,
        root / "outputs" / basename,
        root / "uploads" / basename,
        root / basename,
        hragent_main() / basename,
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"Attachment not found: {file_path}")


def hragent_main() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalize_attachments(attachments: Sequence[str] | str | None) -> list[str]:
    if attachments is None:
        return []
    if isinstance(attachments, str):
        return [part.strip() for part in attachments.split(",") if part.strip()]
    return [str(item).strip() for item in attachments if str(item).strip()]


def _build_raw_message(
    *,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: Sequence[str] | str | None = None,
) -> str:
    message = MIMEMultipart("mixed")
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc
    message.attach(MIMEText(body, "plain", "utf-8"))
    for item in _normalize_attachments(attachments):
        path = resolve_workspace_file(item)
        payload = path.read_bytes()
        part = MIMEApplication(payload, _subtype=path.suffix.lstrip(".") or "octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        message.attach(part)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _gmail_server_from_settings() -> MCPServer | None:
    store = get_settings_store()
    settings = store.load()
    if settings is None:
        return None
    return settings.agent_settings.mcp_config.get(GMAIL_SERVER_NAME)


async def get_google_access_token() -> str:
    """Return a fresh Google access token for the configured Gmail integration."""
    gmail = _gmail_server_from_settings()
    if gmail is None or not gmail.url:
        raise MCPReauthenticationRequiredError(GMAIL_MCP_SERVER_URL)

    token_store = MCPSettingsOAuthTokenStore()
    await refresh_expired_oauth_tokens_for_servers({GMAIL_SERVER_NAME: gmail}, token_store)

    tokens = await token_store.get(
        f"{gmail.url.rstrip('/')}/tokens",
        collection="mcp-oauth-token",
    )
    if not tokens or not tokens.get("access_token"):
        raise MCPReauthenticationRequiredError(gmail.url)

    return str(tokens["access_token"])


def get_google_access_token_sync() -> str:
    return _run_coro_sync(get_google_access_token())


async def send_gmail_message(
    *,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    """Send an email immediately via Gmail API ``users.messages.send``."""
    access_token = await get_google_access_token()
    raw = _build_raw_message(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GMAIL_API_BASE}/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
    if response.status_code != 200:
        detail = response.text[:500]
        logger.error("Gmail send failed (%s): %s", response.status_code, detail)
        raise RuntimeError(
            f"Gmail API rejected the send ({response.status_code}): {detail}"
        )
    payload = response.json()
    names = _normalize_attachments(attachments)
    logger.info(
        "Gmail message sent to %r (message id=%s, attachments=%s)",
        to,
        payload.get("id"),
        names,
    )
    return payload


def send_gmail_message_sync(
    *,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    return _run_coro_sync(
        send_gmail_message(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
        )
    )


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    headers = (payload.get("payload") or {}).get("headers") or []
    out: dict[str, str] = {}
    for item in headers:
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name.lower()] = value
    return out


def _decode_body_data(data: str | None) -> str:
    if not data:
        return ""
    pad = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_plain_body(payload: dict[str, Any], *, max_chars: int = 4000) -> str:
    """Best-effort plain-text body from a Gmail message resource."""
    root = payload.get("payload") or {}
    stack: list[dict[str, Any]] = [root]
    plain = ""
    html = ""
    while stack:
        part = stack.pop()
        mime = str(part.get("mimeType") or "")
        body = part.get("body") or {}
        data = body.get("data") if isinstance(body, dict) else None
        if mime == "text/plain" and isinstance(data, str) and not plain:
            plain = _decode_body_data(data)
        elif mime == "text/html" and isinstance(data, str) and not html:
            html = _decode_body_data(data)
        for child in part.get("parts") or []:
            if isinstance(child, dict):
                stack.append(child)
    text = plain.strip() or re.sub(r"<[^>]+>", " ", html).strip()
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


async def list_recent_emails(
    *,
    max_results: int = 10,
    query: str | None = "in:inbox",
) -> list[dict[str, Any]]:
    """Return recent messages from the linked Gmail account (newest first)."""
    limit = max(1, min(int(max_results or 10), 25))
    q = (query or "in:inbox").strip() or "in:inbox"
    access_token = await get_google_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=45.0) as client:
        listed = await client.get(
            f"{GMAIL_API_BASE}/users/me/messages",
            headers=headers,
            params={"maxResults": limit, "q": q},
        )
        if listed.status_code != 200:
            detail = listed.text[:500]
            logger.error("Gmail list failed (%s): %s", listed.status_code, detail)
            raise RuntimeError(
                f"Gmail API rejected list ({listed.status_code}): {detail}"
            )
        ids = [
            item.get("id")
            for item in (listed.json().get("messages") or [])
            if isinstance(item, dict) and item.get("id")
        ]
        results: list[dict[str, Any]] = []
        for message_id in ids:
            got = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
                headers=headers,
                params={"format": "full"},
            )
            if got.status_code != 200:
                logger.warning(
                    "Gmail get message %s failed (%s)", message_id, got.status_code
                )
                continue
            msg = got.json()
            hdrs = _header_map(msg)
            results.append(
                {
                    "id": msg.get("id"),
                    "threadId": msg.get("threadId"),
                    "from": hdrs.get("from", ""),
                    "to": hdrs.get("to", ""),
                    "subject": hdrs.get("subject", "(no subject)"),
                    "date": hdrs.get("date", ""),
                    "snippet": msg.get("snippet") or "",
                    "body": _extract_plain_body(msg),
                    "labelIds": msg.get("labelIds") or [],
                }
            )
    logger.info("Gmail listed %s message(s) (q=%r)", len(results), q)
    return results


def list_recent_emails_sync(
    *,
    max_results: int = 10,
    query: str | None = "in:inbox",
) -> list[dict[str, Any]]:
    return _run_coro_sync(
        list_recent_emails(max_results=max_results, query=query),
        timeout=120.0,
    )


def format_email_digest(emails: Sequence[dict[str, Any]]) -> str:
    """Render inbox rows as plain text for the agent observation."""
    if not emails:
        return "No emails matched the query."
    lines = [f"Fetched {len(emails)} email(s) (newest first):", ""]
    for i, item in enumerate(emails, start=1):
        lines.extend(
            [
                f"### {i}. {item.get('subject') or '(no subject)'}",
                f"- From: {item.get('from') or ''}",
                f"- Date: {item.get('date') or ''}",
                f"- To: {item.get('to') or ''}",
                f"- Snippet: {item.get('snippet') or ''}",
                f"- Body: {item.get('body') or ''}",
                "",
            ]
        )
    return "\n".join(lines).strip()


async def send_gmail_draft(draft_id: str) -> dict[str, Any]:
    """Send an existing Gmail draft via ``users.drafts.send``."""
    access_token = await get_google_access_token()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GMAIL_API_BASE}/users/me/drafts/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"id": draft_id},
        )
    if response.status_code != 200:
        detail = response.text[:500]
        logger.error("Gmail draft send failed (%s): %s", response.status_code, detail)
        raise RuntimeError(
            f"Gmail API rejected draft send ({response.status_code}): {detail}"
        )
    payload = response.json()
    logger.info("Gmail draft %r sent (message id=%s)", draft_id, payload.get("id"))
    return payload


_DRAFT_ID_PATTERN = re.compile(r'"id"\s*:\s*"([^"]+)"')


def extract_draft_id(text: str) -> str | None:
    """Best-effort draft id extraction from MCP tool output text."""
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        draft_id = parsed.get("id")
        if isinstance(draft_id, str) and draft_id:
            return draft_id
        message = parsed.get("message")
        if isinstance(message, dict):
            nested = message.get("id")
            if isinstance(nested, str) and nested:
                return nested
    match = _DRAFT_ID_PATTERN.search(text)
    return match.group(1) if match else None


def gmail_client_url(client: Any) -> str | None:
    """Return the remote MCP URL if this client is connected to Gmail."""
    transport = getattr(client, "transport", None)
    if transport is None:
        return None
    config = getattr(transport, "config", None)
    servers = getattr(config, "mcpServers", None) if config is not None else None
    if isinstance(servers, dict):
        for server in servers.values():
            url = getattr(server, "url", None)
            if isinstance(url, str) and "gmailmcp.googleapis.com" in url:
                return url.rstrip("/")
    underlying = getattr(transport, "_underlying_transports", None) or []
    for item in underlying:
        url = getattr(item, "url", None)
        if isinstance(url, str) and "gmailmcp.googleapis.com" in url:
            return url.rstrip("/")
    return None


def is_gmail_create_draft_tool(tool_name: str, client: Any) -> bool:
    if tool_name != "create_draft" and not tool_name.endswith("_create_draft"):
        return False
    return gmail_client_url(client) is not None
