from typing import List, Optional
from pydantic import BaseModel

# Meta WhatsApp Webhook Models
class MessageText(BaseModel):
    body: str

class Message(BaseModel):
    from_: str = None
    id: str
    timestamp: str
    text: Optional[MessageText] = None
    type: str

    class Config:
        populate_by_name = True
        fields = {'from_': 'from'}

class Profile(BaseModel):
    name: str

class Contact(BaseModel):
    profile: Profile
    wa_id: str

class Metadata(BaseModel):
    display_phone_number: str
    phone_number_id: str

class Value(BaseModel):
    messaging_product: str
    metadata: Metadata
    contacts: List[Contact]
    messages: List[Message]

class Change(BaseModel):
    value: Value
    field: str

class Entry(BaseModel):
    id: str
    changes: List[Change]

class DialogRequest(BaseModel):
    object: str
    entry: List[Entry]
