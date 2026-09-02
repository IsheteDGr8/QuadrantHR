from models import StoredPolicy, PolicyVersion
from storage_service import StorageService
from datetime import datetime, UTC
from logger import get_logger

logger = get_logger(__name__)
storage = StorageService()


def _blob_path(org_id: str, policy_id: str) -> str:
    return f"{org_id}/{policy_id}.json"


def _version_blob_path(org_id: str, policy_id: str, version: int) -> str:
    return f"{org_id}/{policy_id}/versions/{version}.json"


def create_policy(org_id: str, policy: StoredPolicy) -> StoredPolicy:
    storage.save_json(_blob_path(org_id, policy.id), policy.model_dump())
    logger.info(f"Created policy {policy.id} for org {org_id}")
    return policy


def get_policy(org_id: str, policy_id: str) -> StoredPolicy | None:
    data = storage.load_json(_blob_path(org_id, policy_id))
    return StoredPolicy(**data) if data else None


def update_policy(
    org_id: str,
    policy_id: str,
    updates: dict,
    edited_by: str | None = None,
) -> StoredPolicy | None:
    existing = get_policy(org_id, policy_id)
    if not existing:
        return None

    # Snapshot the CURRENT version before overwriting it
    snapshot = PolicyVersion(
        policy_id=existing.id,
        version=existing.version,
        content=existing.content,
        tone=existing.tone,
        edited_by=edited_by,
    )
    storage.save_json(
        _version_blob_path(org_id, policy_id, existing.version),
        snapshot.model_dump(),
    )

    updated_data = existing.model_dump()
    updated_data.update(updates)
    updated_data["updated_at"] = datetime.now(UTC)
    updated_data["version"] = existing.version + 1

    updated_policy = StoredPolicy(**updated_data)
    storage.save_json(_blob_path(org_id, policy_id), updated_policy.model_dump())
    logger.info(f"Updated policy {policy_id} for org {org_id} to version {updated_policy.version}")
    return updated_policy


def get_policy_history(org_id: str, policy_id: str) -> list[PolicyVersion]:
    prefix = f"{org_id}/{policy_id}/versions/"
    blob_names = storage.list_blobs(prefix=prefix)
    versions = []
    for name in blob_names:
        data = storage.load_json(name)
        if data:
            versions.append(PolicyVersion(**data))
    return sorted(versions, key=lambda v: v.version)


def delete_policy(org_id: str, policy_id: str) -> None:
    storage.delete_blob(_blob_path(org_id, policy_id))


def list_policies(org_id: str) -> list[StoredPolicy]:
    blob_names = storage.list_blobs(prefix=f"{org_id}/")
    policies = []
    for name in blob_names:
        # Skip version snapshots, signature records, and anything under
        # {org_id}/users/... (assignments, adherence acknowledgments, and
        # any future per-user data) — none of these parse as StoredPolicy.
        if "/versions/" in name or "/signatures/" in name or f"{org_id}/users/" in name:
            continue
        data = storage.load_json(name)
        if data:
            policies.append(StoredPolicy(**data))
    return policies