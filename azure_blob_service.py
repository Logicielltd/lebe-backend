from azure.storage.blob import BlobServiceClient
from src.config import settings

class AzureBlobService:
    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        self.container_client = self.blob_service_client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)

    def upload_file(self, file_name: str, file_data: bytes):
        blob_client = self.container_client.get_blob_client(file_name)
        blob_client.upload_blob(file_data, overwrite=True)
        return blob_client.url
