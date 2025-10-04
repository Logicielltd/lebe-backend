from pydantic import BaseModel


class LebeResponse(BaseModel):
    message: str