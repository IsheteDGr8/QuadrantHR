import json

from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

from settings import AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_NAME
from logger import get_logger


logger = get_logger(__name__)

CONTAINER_NAME = "generated-policies"


class StorageService:
    def __init__(self, container_name: str = CONTAINER_NAME):
        self.client = None
        self.container = None
        self.container_name = container_name

        try:
            if AZURE_STORAGE_CONNECTION_STRING:
                self.client = BlobServiceClient.from_connection_string(
                    AZURE_STORAGE_CONNECTION_STRING
                )
            elif AZURE_STORAGE_ACCOUNT_NAME:
                # Managed-identity path — this is what the backend's
                # system-assigned identity + "Storage Blob Data Contributor"
                # role assignment (see terraform/app-service.tf) is for.
                # Connection string takes priority above so this doesn't
                # change current behavior until AZURE_STORAGE_CONNECTION_STRING
                # is actually removed from the App Service config.
                account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
                self.client = BlobServiceClient(
                    account_url=account_url,
                    credential=DefaultAzureCredential(),
                )
            else:
                logger.warning(
                    "Neither AZURE_STORAGE_CONNECTION_STRING nor "
                    "AZURE_STORAGE_ACCOUNT_NAME is configured. Blob Storage "
                    "operations will be unavailable."
                )
                return

            self.container = self.client.get_container_client(self.container_name)

            try:
                self.container.create_container()
            except Exception:
                pass  # container already exists

        except Exception as exc:
            logger.error(f"Failed to initialize Blob Storage: {exc}")
            self.client = None
            self.container = None

    def _ensure_storage_available(self):
        if self.container is None:
            raise RuntimeError(
                "Azure Blob Storage is not configured. "
                "Set AZURE_STORAGE_CONNECTION_STRING."
            )

    def save_json(self, blob_name: str, data: dict) -> None:
        self._ensure_storage_available()

        logger.info(f"Saving blob: {blob_name}")

        self.container.upload_blob(
            blob_name,
            json.dumps(data, default=str),
            overwrite=True,
        )

    def load_json(self, blob_name: str) -> dict | None:
        self._ensure_storage_available()

        try:
            blob = self.container.download_blob(blob_name)
            return json.loads(blob.readall())

        except Exception:
            logger.warning(f"Blob not found: {blob_name}")
            return None

    def delete_blob(self, blob_name: str) -> None:
        self._ensure_storage_available()

        self.container.delete_blob(blob_name)

    def save_bytes(self, blob_name: str, data: bytes) -> None:
        self._ensure_storage_available()

        logger.info(f"Saving binary blob: {blob_name}")

        self.container.upload_blob(blob_name, data, overwrite=True)

    def load_bytes(self, blob_name: str) -> bytes | None:
        self._ensure_storage_available()

        try:
            blob = self.container.download_blob(blob_name)
            return blob.readall()

        except Exception:
            logger.warning(f"Blob not found: {blob_name}")
            return None

    def list_blobs(self, prefix: str) -> list[str]:
        self._ensure_storage_available()

        return [
            blob.name
            for blob in self.container.list_blobs(
                name_starts_with=prefix
            )
        ]