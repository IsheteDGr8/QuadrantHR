from models import TrainingResource, TrainingResourceType
from storage_service import StorageService
from logger import get_logger

logger = get_logger(__name__)

# Separate container from generated-policies — source-documents already
# existed in Terraform for exactly this kind of reference material and was
# otherwise unused.
storage = StorageService(container_name="source-documents")


def _metadata_blob_path(org_id: str, resource_id: str) -> str:
    return f"{org_id}/{resource_id}.json"


def _file_blob_path(org_id: str, resource_id: str) -> str:
    return f"{org_id}/{resource_id}/file"


def create_link_resource(
    org_id: str,
    title: str,
    description: str,
    category: str,
    url: str,
    uploaded_by_user_id: str,
) -> TrainingResource:
    resource = TrainingResource(
        org_id=org_id,
        title=title,
        description=description,
        category=category,
        resource_type=TrainingResourceType.link,
        url=url,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    storage.save_json(_metadata_blob_path(org_id, resource.id), resource.model_dump())
    logger.info(f"Created training link resource {resource.id} for org {org_id}")
    return resource


def create_file_resource(
    org_id: str,
    title: str,
    description: str,
    category: str,
    original_filename: str,
    file_bytes: bytes,
    uploaded_by_user_id: str,
) -> TrainingResource:
    resource = TrainingResource(
        org_id=org_id,
        title=title,
        description=description,
        category=category,
        resource_type=TrainingResourceType.file,
        original_filename=original_filename,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    storage.save_bytes(_file_blob_path(org_id, resource.id), file_bytes)
    storage.save_json(_metadata_blob_path(org_id, resource.id), resource.model_dump())
    logger.info(f"Created training file resource {resource.id} for org {org_id}")
    return resource


def get_resource(org_id: str, resource_id: str) -> TrainingResource | None:
    data = storage.load_json(_metadata_blob_path(org_id, resource_id))
    return TrainingResource(**data) if data else None


def get_resource_file_bytes(org_id: str, resource_id: str) -> bytes | None:
    return storage.load_bytes(_file_blob_path(org_id, resource_id))


def list_resources(org_id: str) -> list[TrainingResource]:
    blob_names = storage.list_blobs(prefix=f"{org_id}/")
    resources = []
    for name in blob_names:
        if not name.endswith(".json"):
            continue  # skip raw file blobs, only metadata is JSON
        data = storage.load_json(name)
        if data:
            resources.append(TrainingResource(**data))
    return sorted(resources, key=lambda r: r.created_at)


def delete_resource(org_id: str, resource_id: str) -> None:
    storage.delete_blob(_metadata_blob_path(org_id, resource_id))
    try:
        storage.delete_blob(_file_blob_path(org_id, resource_id))
    except Exception:
        pass  # link resources have no file blob to delete
