import os
from azure.storage.blob import BlobServiceClient, ContentSettings


class StorageService:
    """Azure Blob Storage implementation used by the app.

    It reads configuration from environment variables:
      - AZURE_STORAGE_CONNECTION_STRING
      - AZURE_STORAGE_CONTAINER

    Methods:
      - upload_file(file_obj, file_name, content_type=None) -> str (blob url)
      - download_file(file_name, destination_path) -> str
    """

    def __init__(self, connection_string: str | None = None, container_name: str | None = None):
        connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = container_name or os.getenv("AZURE_STORAGE_CONTAINER")

        if not connection_string or not container_name:
            raise ValueError(
                "Azure Storage connection string and container name must be set: "
                "AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER"
            )

        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)

        # Ensure container exists (create if not). If it already exists, ignore the error.
        try:
            self.container_client.create_container()
        except Exception:
            # Container likely already exists or creation not permitted; continue.
            pass

    def upload_file(self, file_obj, file_name: str, content_type: str | None = None) -> str:
        """Upload a file-like object to Azure Blob Storage and return the blob URL.

        file_obj must be a readable file-like object (e.g. UploadFile.file from FastAPI).
        """
        blob_client = self.container_client.get_blob_client(file_name)
        content_settings = ContentSettings(content_type=content_type) if content_type else None

        # Make sure we start reading from beginning
        try:
            file_obj.seek(0)
        except Exception:
            pass

        # Upload stream. Overwrite existing blob if any.
        # Set 30 second timeout to prevent hanging indefinitely
        blob_client.upload_blob(file_obj, overwrite=True, content_settings=content_settings, timeout=30)

        # Return URL to blob (access depends on container ACL or SAS)
        return blob_client.url

    def download_file(self, file_name: str, destination_path: str) -> str:
        """Download blob to local file path.

        Raises exceptions from Azure SDK if blob not found.
        """
        blob_client = self.container_client.get_blob_client(file_name)
        downloader = blob_client.download_blob()

        # Write bytes to the destination file
        with open(destination_path, "wb") as f:
            downloader.readinto(f)

        return f"Downloaded {file_name} to {destination_path}"
