"""Load ClosedAI .env files and alias MCP credential names into os.environ.

Marketplace MCP templates (${COSMOS_URI}, ${AZURE_SEARCH_API_KEY}, ...) must
resolve without a setup dialog. The repo historically used two name sets
(COSMOS_ENDPOINT vs COSMOS_URI, AZURE_SEARCH_KEY vs AZURE_SEARCH_API_KEY),
and settings-store MCP env values are Fernet-encrypted at rest. This module:

1. Loads repo-root ``.env`` (canonical) then ``HRAgent_Main/.env``.
2. Copies alias names so both the process and MCP subprocesses see the
   names the plugins actually read.
3. Overlays those plaintext values onto an MCP server config when the
   stored env is empty, a leftover ``${VAR}``, or a Fernet token.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from pydantic import SecretStr

if TYPE_CHECKING:
    from mcp_integration.config import MCPServer

# Canonical name -> accepted source names (first non-empty plaintext wins).
MCP_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "COSMOS_URI": ("COSMOS_URI", "COSMOS_ENDPOINT"),
    "COSMOS_KEY": ("COSMOS_KEY",),
    "COSMOS_DATABASE": ("COSMOS_DATABASE", "COSMOS_DATABASE_NAME"),
    "COSMOS_CONTAINER": ("COSMOS_CONTAINER", "COSMOS_CONTAINER_NAME"),
    "AZURE_SEARCH_ENDPOINT": ("AZURE_SEARCH_ENDPOINT",),
    "AZURE_SEARCH_API_KEY": ("AZURE_SEARCH_API_KEY", "AZURE_SEARCH_KEY"),
    "AZURE_SEARCH_INDEX": ("AZURE_SEARCH_INDEX",),
}

MCP_SECRET_NAMES: tuple[str, ...] = tuple(MCP_ENV_ALIASES)


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().strip('"').strip("'")
    return text or None


def _is_unusable(value: str | None) -> bool:
    if not value:
        return True
    return value.startswith("gAAAAA") or value.startswith("${")


def first_env(*names: str) -> str | None:
    for name in names:
        value = _strip(os.environ.get(name))
        if value and not _is_unusable(value):
            return value
    return None


def apply_env_aliases() -> None:
    for canonical, names in MCP_ENV_ALIASES.items():
        value = first_env(*names)
        if value and _is_unusable(_strip(os.environ.get(canonical))):
            os.environ[canonical] = value


def load_closedai_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]

    here = Path(__file__).resolve()
    hragent_main = here.parents[2]
    repo_root = here.parents[3]
    if load_dotenv is not None:
        # HRAgent_Main/.env first, then repo-root .env overrides so the
        # canonical ClosedAI credentials (search host, COSMOS_URI aliases)
        # win over stale copies.
        load_dotenv(hragent_main / ".env", override=False)
        load_dotenv(repo_root / ".env", override=True)
    apply_env_aliases()


def overlay_process_env_on_mcp(
    mcp_config: Mapping[str, "MCPServer"],
) -> dict[str, "MCPServer"]:
    """Replace unusable MCP env values with process-env credentials."""
    apply_env_aliases()
    patched: dict[str, MCPServer] = {}
    hragent_main = Path(__file__).resolve().parents[2]
    workspace_abs = Path(
        os.environ.get("HRAGENT_WORKSPACE_DIR", hragent_main / "workspace")
    )
    if not workspace_abs.is_absolute():
        workspace_abs = (hragent_main / workspace_abs).resolve()
    else:
        workspace_abs = workspace_abs.resolve()

    for name, server in mcp_config.items():
        env = dict(server.env or {})
        changed = False
        for canonical, names in MCP_ENV_ALIASES.items():
            raw = env.get(canonical)
            current = (
                raw.get_secret_value()
                if isinstance(raw, SecretStr)
                else (str(raw) if raw is not None else "")
            )
            if _is_unusable(_strip(current)):
                value = first_env(*names)
                if value:
                    env[canonical] = SecretStr(value)
                    changed = True

        if name == "document-editor":
            if env.get("HRAGENT_WORKSPACE_DIR") is None:
                env["HRAGENT_WORKSPACE_DIR"] = SecretStr(str(workspace_abs))
                changed = True
            updates: dict[str, object] = {}
            if changed:
                updates["env"] = env
            if server.cwd is None:
                updates["cwd"] = str(hragent_main)
            if updates:
                patched[name] = server.model_copy(update=updates)
                continue

        patched[name] = server.model_copy(update={"env": env}) if changed else server
    return patched


def seed_mcp_secrets(secrets_store: object | None) -> None:
    """Copy process-env MCP credentials into the secrets store if missing.

    The MCP setup UI treats a missing secret name as "needs setup". Seeding
    here makes Cosmos / Azure AI Search look connected without a dialog.
    Existing store values are left untouched.
    """
    if secrets_store is None:
        return
    apply_env_aliases()
    load = getattr(secrets_store, "load", None)
    set_secret = getattr(secrets_store, "set_secret", None)
    if not callable(load) or not callable(set_secret):
        return
    try:
        secrets = load()
    except Exception:
        return
    existing = set(getattr(secrets, "custom_secrets", {}) or {}) if secrets else set()
    for name in MCP_SECRET_NAMES:
        if name in existing:
            continue
        value = first_env(*MCP_ENV_ALIASES[name])
        if value:
            try:
                set_secret(name, value, description="Seeded from process .env")
            except Exception:
                continue
