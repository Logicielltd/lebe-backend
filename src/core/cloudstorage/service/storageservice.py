import os
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class StorageService:
    """Contabo S3-compatible storage implementation used by the app.

    It reads configuration from environment variables:
      - CONTABO_ACCESS_KEY
      - CONTABO_SECRET_KEY
      - CONTABO_ENDPOINT
      - CONTABO_BUCKET

    Methods:
      - upload_file(file_obj, file_name, content_type=None) -> str (blob url)
      - download_file(file_name, destination_path) -> str
    """

    def __init__(self):
        self.access_key = os.getenv("CONTABO_ACCESS_KEY")
        self.secret_key = os.getenv("CONTABO_SECRET_KEY")
        self.endpoint = os.getenv("CONTABO_ENDPOINT", "https://usc1.contabostorage.com")
        self.bucket = os.getenv("CONTABO_BUCKET")

        if not self.access_key or not self.secret_key or not self.bucket:
            raise ValueError(
                "Contabo storage credentials and bucket must be set: "
                "CONTABO_ACCESS_KEY, CONTABO_SECRET_KEY, and CONTABO_BUCKET"
            )

        # Initialize S3 client with Contabo endpoint
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="us-east-1"  # Required but not used by Contabo
        )

        # Ensure bucket exists (create if not). If it already exists, ignore the error.
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket)
                except ClientError:
                    pass  # Bucket creation not permitted; continue.
            else:
                pass  # Other errors; continue.

    def upload_file(self, file_obj, file_name: str, content_type: str | None = None, timeout_seconds: int = 30) -> str:
        """Upload a file-like object to Contabo S3 storage and return the object URL.

        file_obj must be a readable file-like object (e.g. UploadFile.file from FastAPI).

        Args:
            file_obj: File-like object to upload
            file_name: Name/path for the object
            content_type: MIME type for the object
            timeout_seconds: Maximum seconds to wait for upload (default: 30)

        Returns:
            str: URL of the uploaded object

        Raises:
            TimeoutError: If upload takes longer than timeout_seconds
            Exception: Other S3 storage exceptions
        """
        # Make sure we start reading from beginning
        try:
            file_obj.seek(0)
        except Exception:
            pass

        # Define upload function to run in thread
        def _upload():
            try:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                
                self.s3_client.upload_fileobj(
                    file_obj,
                    self.bucket,
                    file_name,
                    ExtraArgs=extra_args if extra_args else None
                )
                
                # Generate URL for the uploaded object
                url = f"{self.endpoint}/{self.bucket}/{file_name}"
                return url
            except Exception as e:
                logger.error(f"Contabo S3 upload error: {str(e)}")
                raise

        # Execute upload with hard timeout using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_upload)
            try:
                # Wait for result with timeout
                result = future.result(timeout=timeout_seconds)
                logger.info(f"Successfully uploaded {file_name} to Contabo S3 storage")
                return result
            except FuturesTimeoutError:
                logger.error(f"Upload timeout after {timeout_seconds}s for {file_name}")
                # Cancel the future (though the upload might still continue in background)
                future.cancel()
                raise TimeoutError(f"Contabo S3 upload timed out after {timeout_seconds} seconds")
            except Exception as e:
                logger.error(f"Upload failed for {file_name}: {str(e)}")
                raise

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
