import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.businesses import service
from app.services.businesses.schemas import (BranchIn, BranchOut, BusinessIn, BusinessOut, BusinessUpdate, MemberIn,
                                             MemberOut)

router = APIRouter(tags=["business"])


@router.post("/business", response_model=BusinessOut, status_code=201)
async def create_business(body: BusinessIn, p: Principal = access.business_member(),
                          session: AsyncSession = Depends(get_session)):
    return await service.create(session, p.user_id, body)


@router.get("/business", response_model=list[BusinessOut])
async def my_businesses(p: Principal = access.business_member(), session: AsyncSession = Depends(get_session)):
    return await service.mine(session, p.user_id)


@router.get("/business/{business_id}", response_model=BusinessOut)
async def get_business(business_id: uuid.UUID, p: Principal = access.business_member(),
                       session: AsyncSession = Depends(get_session)):
    return await service.get(session, p.user_id, business_id)


@router.put("/business/{business_id}", response_model=BusinessOut)
async def update_business(business_id: uuid.UUID, body: BusinessUpdate, p: Principal = access.business_member(),
                          session: AsyncSession = Depends(get_session)):
    return await service.update(session, p.user_id, business_id, body.name)


@router.post("/business/{business_id}/branches", response_model=BranchOut, status_code=201)
async def add_branch(business_id: uuid.UUID, body: BranchIn, p: Principal = access.business_member(),
                     session: AsyncSession = Depends(get_session)):
    return await service.add_branch(session, p.user_id, business_id, body)


@router.put("/business/{business_id}/branches/{branch_id}", response_model=BranchOut)
async def update_branch(business_id: uuid.UUID, branch_id: uuid.UUID, body: BranchIn,
                        p: Principal = access.business_member(), session: AsyncSession = Depends(get_session)):
    return await service.update_branch(session, p.user_id, business_id, branch_id, body)


@router.get("/business/{business_id}/team", response_model=list[MemberOut])
async def get_team(business_id: uuid.UUID, p: Principal = access.business_member(),
                   session: AsyncSession = Depends(get_session)):
    return await service.team(session, p.user_id, business_id)


@router.post("/business/{business_id}/team", response_model=MemberOut, status_code=201)
async def add_member(business_id: uuid.UUID, body: MemberIn, p: Principal = access.business_member(),
                     session: AsyncSession = Depends(get_session)):
    return await service.add_member(session, p.user_id, business_id, body)
