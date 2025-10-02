from fastapi import HTTPException


class FileTooLargeError(HTTPException):
    def __init__(self, max_size: str):
        super().__init__(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {max_size}"
        )

class InvalidFileTypeError(HTTPException):
    def __init__(self, allowed_types: list):
        super().__init__(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )


class FileUploadError(HTTPException):
    def __init__(self, detail: str = "File upload failed"):
        super().__init__(status_code=500, detail=detail)