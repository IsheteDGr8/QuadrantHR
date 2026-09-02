from models import PolicySignature
from storage_service import StorageService
from logger import get_logger

logger = get_logger(__name__)
storage = StorageService()


def _signature_blob_path(org_id: str, policy_id: str, signer_user_id: str) -> str:
    return f"{org_id}/{policy_id}/signatures/{signer_user_id}.json"


def sign_policy(
    org_id: str,
    policy_id: str,
    signer_user_id: str,
    signer_roles: list[str],
    signed_name: str,
) -> PolicySignature:
    # One signature per (policy, user) — signing again overwrites the
    # previous record (updates signed_name/signed_at) rather than creating
    # a duplicate, since a person only needs to have signed a policy once.
    signature = PolicySignature(
        policy_id=policy_id,
        signer_user_id=signer_user_id,
        signer_roles=signer_roles,
        signed_name=signed_name,
    )
    storage.save_json(
        _signature_blob_path(org_id, policy_id, signer_user_id),
        signature.model_dump(),
    )
    logger.info(
        f"Policy {policy_id} signed by {signer_user_id} for org {org_id}"
    )
    return signature


def get_signature(
    org_id: str, policy_id: str, signer_user_id: str
) -> PolicySignature | None:
    data = storage.load_json(_signature_blob_path(org_id, policy_id, signer_user_id))
    return PolicySignature(**data) if data else None


def list_signatures(org_id: str, policy_id: str) -> list[PolicySignature]:
    prefix = f"{org_id}/{policy_id}/signatures/"
    blob_names = storage.list_blobs(prefix=prefix)
    signatures = []
    for name in blob_names:
        data = storage.load_json(name)
        if data:
            signatures.append(PolicySignature(**data))
    return sorted(signatures, key=lambda s: s.signed_at)
