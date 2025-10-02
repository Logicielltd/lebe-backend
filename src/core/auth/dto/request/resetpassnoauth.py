from pydantic import BaseModel, EmailStr

class ResetPassNoAuth(BaseModel):
    email: EmailStr
    new_password: str
