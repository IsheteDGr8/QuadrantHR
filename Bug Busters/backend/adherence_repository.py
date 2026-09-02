from models import AdherenceAcknowledgment
from storage_service import StorageService
from logger import get_logger

logger = get_logger(__name__)
storage = StorageService()


def _blob_path(org_id: str, user_id: str) -> str:
    return f"{org_id}/users/{user_id}/adherence.json"


def acknowledge(org_id: str, user_id: str) -> AdherenceAcknowledgment:
    acknowledgment = AdherenceAcknowledgment(org_id=org_id, user_id=user_id)
    storage.save_json(_blob_path(org_id, user_id), acknowledgment.model_dump())
    logger.info(f"User {user_id} acknowledged company rules for org {org_id}")
    return acknowledgment


def get_acknowledgment(org_id: str, user_id: str) -> AdherenceAcknowledgment | None:
    data = storage.load_json(_blob_path(org_id, user_id))
    return AdherenceAcknowledgment(**data) if data else None
