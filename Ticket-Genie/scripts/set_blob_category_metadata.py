#!/usr/bin/env python3
"""
scripts/set_blob_category_metadata.py

Sets a `category` metadata key on each blob in the `ticket-genie-knowledge`
container, using the deterministic filename map in
scripts/knowledge_categories.py. Azure AI Search's Blob indexer surfaces
custom blob metadata as document fields with matching names, so setting
`category` here lets the indexer populate group-1's `category` field
(implicit field mapping - no skillset needed).

This never touches blob CONTENT, and never deletes existing metadata keys -
it only adds/updates the `category` key. Still, changing metadata on a
shared container is a real write, so this script defaults to a safe,
no-op check.

Usage:
    python scripts/set_blob_category_metadata.py --check   (default; no changes)
    python scripts/set_blob_category_metadata.py --apply   (writes metadata)

Connection (in preference order):
    1. Azure identity (DefaultAzureCredential) - preferred. Uses whatever
       credential is already active for this environment (az login,
       managed identity, etc.) - no key needed if that identity has the
       right RBAC role. Requires AZURE_STORAGE_ACCOUNT_NAME, or falls back
       to the known account for this container (not a secret).
    2. AZURE_STORAGE_CONNECTION_STRING, if explicitly set.
    3. AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY, if explicitly
       set.
    None of these are currently tracked in this repo's .env/Key Vault -
    see the final report for the exact RBAC role needed instead.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from knowledge_categories import ALL_CATEGORIES, BLOB_CATEGORY_MAP, category_for_blob

CONTAINER_NAME = "ticket-genie-knowledge"
# Discovered read-only via `az storage account list` - not a secret, just
# the resource name. Overridable via AZURE_STORAGE_ACCOUNT_NAME.
DEFAULT_STORAGE_ACCOUNT_NAME = "seed123data"


def _get_container_client():
    from azure.core.exceptions import AzureError
    from azure.storage.blob import BlobServiceClient

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", DEFAULT_STORAGE_ACCOUNT_NAME)
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    if connection_string:
        service_client = BlobServiceClient.from_connection_string(connection_string)
    elif account_key:
        service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key,
        )
    else:
        # Preferred path: no key/connection string needed if the caller's
        # identity already has the right RBAC role on the storage account.
        from azure.identity import DefaultAzureCredential

        service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )

    try:
        return service_client.get_container_client(CONTAINER_NAME)
    except AzureError as exc:
        raise RuntimeError(
            f"Could not open container '{CONTAINER_NAME}': {exc}"
        ) from exc


def _friendly_auth_error(exc: Exception, account_name: str) -> str:
    text = str(exc)
    if "AuthorizationPermissionMismatch" in text or "AuthorizationFailure" in text:
        return (
            "Authenticated, but this identity lacks permission to read "
            f"container '{CONTAINER_NAME}'. Ask an admin to grant the "
            "'Storage Blob Data Reader' role (add 'Storage Blob Data "
            "Contributor' too if writing metadata) on storage account "
            f"'{account_name}' to this identity. Alternatively set "
            "AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_KEY "
            "as a temporary override - no new Key Vault secret should be "
            "added just to work around this."
        )
    return f"failed to list/inspect container blobs: {exc}"


def _plan(container_client):
    """Read-only: compute what would change. Returns a list of plan rows."""

    plan = []
    seen = set()
    for blob in container_client.list_blobs():
        seen.add(blob.name)
        current_metadata = blob.metadata or {}
        current_category = current_metadata.get("category")
        try:
            target_category = category_for_blob(blob.name)
        except KeyError as exc:
            plan.append(
                {
                    "blob": blob.name,
                    "current": current_category,
                    "target": None,
                    "action": f"SKIP (unmapped): {exc}",
                }
            )
            continue

        if current_category == target_category:
            action = "already correct"
        elif current_category is None:
            action = "SET"
        else:
            action = f"UPDATE ({current_category!r} -> {target_category!r})"

        plan.append(
            {
                "blob": blob.name,
                "current": current_category,
                "target": target_category,
                "action": action,
            }
        )

    unmapped_in_container = seen - set(BLOB_CATEGORY_MAP)
    mapped_but_missing = set(BLOB_CATEGORY_MAP) - seen
    return plan, unmapped_in_container, mapped_but_missing


def run(apply_changes: bool) -> int:
    invalid = {c for c in BLOB_CATEGORY_MAP.values() if c not in ALL_CATEGORIES}
    if invalid:
        print(f"BLOCKER: category map contains unknown categories: {invalid}")
        return 1

    try:
        container_client = _get_container_client()
    except RuntimeError as exc:
        print(f"BLOCKER: {exc}")
        return 1

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", DEFAULT_STORAGE_ACCOUNT_NAME)
    try:
        plan, unmapped_in_container, mapped_but_missing = _plan(container_client)
    except Exception as exc:
        print(f"BLOCKER: {_friendly_auth_error(exc, account_name)}")
        return 1

    print(f"Container: {CONTAINER_NAME}")
    print(f"Blobs found: {len(plan)}")
    print()
    for row in plan:
        print(f"  {row['blob']:<45} current={row['current']!r:<12} -> {row['action']}")

    if unmapped_in_container:
        print()
        count = len(unmapped_in_container)
        print(f"BLOCKER: {count} blob(s) have no category mapping:")
        for name in sorted(unmapped_in_container):
            print(f"  - {name}")

    if mapped_but_missing:
        print()
        print("NOTE: mapped filenames not currently present in the container:")
        for name in sorted(mapped_but_missing):
            print(f"  - {name}")

    if not apply_changes:
        print()
        print("Check mode only - no metadata changed. Re-run with --apply to write.")
        return 1 if unmapped_in_container else 0

    if unmapped_in_container:
        print()
        print("Refusing to apply: unmapped blobs present (see BLOCKER above).")
        return 1

    print()
    print("Applying category metadata...")
    changed = 0
    for row in plan:
        if row["action"] in ("already correct",) or row["action"].startswith("SKIP"):
            continue
        blob_client = container_client.get_blob_client(row["blob"])
        existing_metadata = dict(blob_client.get_blob_properties().metadata or {})
        existing_metadata["category"] = row["target"]
        blob_client.set_blob_metadata(existing_metadata)
        changed += 1
        print(f"  set category={row['target']!r} on {row['blob']}")

    print(f"Done. {changed} blob(s) updated.")
    return 0


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only check (default behavior; accepted explicitly too).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write metadata (default is a read-only check).",
    )
    args = parser.parse_args()
    sys.exit(run(apply_changes=args.apply))


if __name__ == "__main__":
    main()
