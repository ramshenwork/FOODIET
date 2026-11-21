import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.core.net import client_ip
from app.services.qr import service
from app.services.qr.schemas import QrOut

router = APIRouter(tags=["qr"])
public_router = APIRouter()  # mounted at the site root, outside /api


@router.get("/branches/{branch_id}/qr", response_model=QrOut)
async def branch_qr(branch_id: uuid.UUID, p: Principal = access.business_member(),
                    session: AsyncSession = Depends(get_session)):
    return await service.qr_for_branch(session, p.user_id, branch_id)


@public_router.get("/q/{code}", response_class=HTMLResponse, include_in_schema=False)
async def public_menu(code: str, request: Request, session: AsyncSession = Depends(get_session)):
    ip = client_ip(request)
    status, html = await service.public_menu_html(session, code[:16], ip)
    return HTMLResponse(html, status_code=status, headers={"Cache-Control": "public, max-age=60"})
