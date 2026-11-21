from pydantic import BaseModel


class EventIn(BaseModel):
    name: str
    properties: dict | None = None
