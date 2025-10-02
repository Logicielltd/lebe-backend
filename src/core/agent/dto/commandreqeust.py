from pydantic import BaseModel

class CommandRequest(BaseModel):
    query: str
