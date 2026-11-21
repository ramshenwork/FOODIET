import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.profile import service
from app.services.profile.schemas import ConsentIn, FingerprintOut, ProfileIn, ProfileOut

router = APIRouter(tags=["profile"])


@router.get("/me/profile", response_model=ProfileOut)
async def get_profile(p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.get(session, p.user_id)


@router.put("/me/profile", response_model=ProfileOut)
async def put_profile(body: ProfileIn, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.save(session, p.user_id, body)


@router.post("/me/consents", response_model=ProfileOut)
async def set_consent(body: ConsentIn, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.set_consent(session, p.user_id, body)


@router.get("/me/fingerprint", response_model=FingerprintOut)
async def fingerprint(p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.fingerprint(session, p.user_id)


@router.delete("/me/fingerprint/{pref_id}", status_code=204)
async def remove(pref_id: uuid.UUID, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    await service.remove_learned(session, p.user_id, pref_id)
    return Response(status_code=204)
