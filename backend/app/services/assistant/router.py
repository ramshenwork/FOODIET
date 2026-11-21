from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.assistant import service
from app.services.assistant.schemas import AnswerOut, ConversationOut, QueryIn

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("", response_model=ConversationOut)
async def conversation(p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.conversation(session, p.user_id)


@router.post("/query", response_model=AnswerOut)
async def query(body: QueryIn, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.ask(session, p.user_id, body)
