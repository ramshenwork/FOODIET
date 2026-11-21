import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class CitedDish(BaseModel):
    id: uuid.UUID
    name: str
    restaurant: str | None
    energy: str | None
    protein: str | None
    trust: str


class AnswerOut(BaseModel):
    answer: str
    cited: list[CitedDish]
    mode: str                     # 'ai' | 'basic'
    notice: str | None
    remaining_today: int
    limit: int


class MessageOut(BaseModel):
    role: str
    content: str
    cited: list[CitedDish]
    mode: str | None
    at: datetime


class ConversationOut(BaseModel):
    messages: list[MessageOut]
    remaining_today: int
    limit: int
    mode: str                     # what the next answer will use
