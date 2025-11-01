from pydantic import BaseModel

class FileDTO(BaseModel):
    file_name: str
    file_url: str
