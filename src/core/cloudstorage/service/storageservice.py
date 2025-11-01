from google.cloud import storage

BUCKET_NAME = "your-bucket-name"

class StorageService:
    def __init__(self):
        #self.client = storage.Client()
        #self.bucket = self.client.bucket(BUCKET_NAME)
        return

    def upload_file(self, file_obj, file_name, content_type=None):
        blob = self.bucket.blob(file_name)
        blob.upload_from_file(file_obj, content_type=content_type)
        return blob.public_url

    def download_file(self, file_name, destination_path):
        blob = self.bucket.blob(file_name)
        blob.download_to_filename(destination_path)
        return f"Downloaded {file_name} to {destination_path}"
