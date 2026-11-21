from pydantic import BaseModel


class Email(BaseModel):
    to: str
    subject: str
    text: str
