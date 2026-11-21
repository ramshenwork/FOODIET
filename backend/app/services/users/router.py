import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.users import service
from app.services.profile.schemas import DeleteIn
from app.services.users.schemas import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.me(session, p.user_id)


@router.get("/me/export")
async def export(p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    """Everything we hold about you, as JSON. Available at every access level, including lapsed."""
    data = await service.export(session, p.user_id)
    return Response(content=json.dumps(data, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="my-data.json"'})


@router.delete("/me", status_code=204)
async def delete_me(body: DeleteIn, response: Response, p: Principal = access.signed_in(),
                    session: AsyncSession = Depends(get_session)):
    await service.delete_account(session, p.user_id)
    for name, path in (("access_token", "/"), ("refresh_token", "/api/v1/auth"), ("csrf_token", "/")):
        response.delete_cookie(name, path=path)
    response.status_code = 204
    return response
