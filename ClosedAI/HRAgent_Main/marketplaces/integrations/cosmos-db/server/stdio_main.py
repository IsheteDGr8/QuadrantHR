#!/usr/bin/env python3
"""Stdio entrypoint for the vendored Azure Cosmos DB MCP server.

The upstream sample (AzureCosmosDB/azure-cosmos-mcp-server-samples, see
cosmos_server.py + LICENSE-upstream) only ships a streamable-http entrypoint
(cosmos_server.main() hardcodes mcp.run(transport="streamable-http", ...)).
Every other marketplace integration in this repo is spawned per-conversation
over stdio (see ../azure-ai-search/.mcp.json, ../postgres/.mcp.json), which
is simpler to operate -- no separately-managed long-running sidecar process,
and credentials are scoped to a single subprocess's environment instead of a
shared server.

This file changes nothing about the upstream tool implementations
(query_cosmos, list_collections, describe_container, etc.) or how they talk
to Cosmos DB -- it only swaps the transport the same FastMCP instance is
served over, so the plugin fits the stdio/npx-style pattern the rest of the
marketplace uses.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cosmos_server  # noqa: E402


def _env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if not raw:
            continue
        value = raw.strip().strip('"').strip("'")
        if value and not value.startswith("gAAAAA") and not value.startswith("${"):
            return value
    return None


def main() -> None:
    # Accept both the marketplace plugin names (COSMOS_URI/DATABASE/CONTAINER)
    # and the repo .env names (COSMOS_ENDPOINT/DATABASE_NAME/CONTAINER_NAME).
    uri = _env("COSMOS_URI", "COSMOS_ENDPOINT")
    key = _env("COSMOS_KEY")
    database = _env("COSMOS_DATABASE", "COSMOS_DATABASE_NAME")
    container = _env("COSMOS_CONTAINER", "COSMOS_CONTAINER_NAME")
    use_managed_identity = os.environ.get("COSMOS_USE_MANAGED_IDENTITY", "").lower() in (
        "1",
        "true",
        "yes",
    )

    missing = [
        name
        for name, value in (
            ("COSMOS_URI", uri),
            ("COSMOS_DATABASE", database),
            ("COSMOS_CONTAINER", container),
        )
        if not value
    ]
    if not use_managed_identity and not key:
        missing.append("COSMOS_KEY (or set COSMOS_USE_MANAGED_IDENTITY=true)")
    if missing:
        print(f"[cosmos-db mcp] missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    cosmos_server.cosmos_connection = cosmos_server.CosmosDBConnection(
        uri=uri,
        key=key,
        database=database,
        container=container,
        use_managed_identity=use_managed_identity,
    )
    # Probe the default container but do not abort: a transient network error
    # must not kill the MCP stdio session (that surfaces as "Connection closed").
    try:
        cosmos_server.cosmos_connection.get_container_client()
    except Exception as exc:  # noqa: BLE001
        print(f"[cosmos-db mcp] warning: could not reach default container: {exc}", file=sys.stderr)

    cosmos_server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
