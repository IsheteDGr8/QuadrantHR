from models import PolicyAssignment
from storage_service import StorageService
from logger import get_logger

logger = get_logger(__name__)
storage = StorageService()


def _assignment_blob_path(org_id: str, user_id: str, policy_id: str) -> str:
    # Stored per-user (not per-policy, unlike signatures/versions) since
    # the main read pattern is "what was this employee sent" for progress
    # tracking — a per-user prefix makes that a single list_blobs call
    # instead of scanning every policy.
    return f"{org_id}/users/{user_id}/assignments/{policy_id}.json"


def assign_policy(
    org_id: str,
    policy_id: str,
    policy_name: str,
    assigned_to_user_id: str,
    assigned_by_user_id: str,
) -> PolicyAssignment:
    assignment = PolicyAssignment(
        policy_id=policy_id,
        policy_name=policy_name,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=assigned_by_user_id,
    )
    storage.save_json(
        _assignment_blob_path(org_id, assigned_to_user_id, policy_id),
        assignment.model_dump(),
    )
    logger.info(
        f"Policy {policy_id} assigned to user {assigned_to_user_id} for org {org_id}"
    )
    return assignment


def list_user_assignments(org_id: str, user_id: str) -> list[PolicyAssignment]:
    prefix = f"{org_id}/users/{user_id}/assignments/"
    blob_names = storage.list_blobs(prefix=prefix)
    assignments = []
    for name in blob_names:
        data = storage.load_json(name)
        if data:
            assignments.append(PolicyAssignment(**data))
    return sorted(assignments, key=lambda a: a.assigned_at)
