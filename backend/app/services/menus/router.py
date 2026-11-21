import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.core.storage import MAX_BYTES
from app.core.errors import AppError
from app.services.menus import service
from app.services.menus.schemas import (CategoryIn, CategoryOut, ConfirmOut, DashboardOut, ImportOut, ImportUpdate,
                                        ItemIn, ItemOut, ItemUpdate, MenuOut)

router = APIRouter(tags=["menus"])
B = "/business/{business_id}"
Member = access.business_member


@router.get(B + "/menus", response_model=MenuOut)
async def get_menu(business_id: uuid.UUID, branch_id: uuid.UUID, p: Principal = Member(),
                   session: AsyncSession = Depends(get_session)):
    return await service.get_menu(session, p.user_id, business_id, branch_id)


@router.post(B + "/menus/categories", response_model=CategoryOut, status_code=201)
async def add_category(business_id: uuid.UUID, branch_id: uuid.UUID, body: CategoryIn, p: Principal = Member(),
                       session: AsyncSession = Depends(get_session)):
    return await service.add_category(session, p.user_id, business_id, branch_id, body)


@router.post(B + "/menu-items", response_model=ItemOut, status_code=201)
async def add_item(business_id: uuid.UUID, body: ItemIn, p: Principal = Member(),
                   session: AsyncSession = Depends(get_session)):
    return await service.add_item(session, p.user_id, business_id, body)


@router.put(B + "/menu-items/{item_id}", response_model=ItemOut)
async def update_item(business_id: uuid.UUID, item_id: uuid.UUID, body: ItemUpdate, p: Principal = Member(),
                      session: AsyncSession = Depends(get_session)):
    return await service.update_item(session, p.user_id, business_id, item_id, body)


@router.delete(B + "/menu-items/{item_id}", status_code=204)
async def delete_item(business_id: uuid.UUID, item_id: uuid.UUID, p: Principal = Member(),
                      session: AsyncSession = Depends(get_session)):
    await service.delete_item(session, p.user_id, business_id, item_id)
    return Response(status_code=204)


@router.post(B + "/menu-imports", response_model=ImportOut, status_code=201)
async def create_import(business_id: uuid.UUID, branch_id: uuid.UUID = Form(...), file: UploadFile = File(...),
                        p: Principal = Member(), session: AsyncSession = Depends(get_session)):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise AppError(413, "upload_too_large", "Files can be at most 10 MB.")
    return await service.create_import(session, p.user_id, business_id, branch_id, file.filename or "",
                                       file.content_type or "", data)


@router.get(B + "/menu-imports/{import_id}", response_model=ImportOut)
async def get_import(business_id: uuid.UUID, import_id: uuid.UUID, p: Principal = Member(),
                     session: AsyncSession = Depends(get_session)):
    return await service.get_import(session, p.user_id, business_id, import_id)


@router.put(B + "/menu-imports/{import_id}", response_model=ImportOut)
async def update_import(business_id: uuid.UUID, import_id: uuid.UUID, body: ImportUpdate, p: Principal = Member(),
                        session: AsyncSession = Depends(get_session)):
    return await service.update_import(session, p.user_id, business_id, import_id, body)


@router.post(B + "/menu-imports/{import_id}/confirm", response_model=ConfirmOut)
async def confirm_import(business_id: uuid.UUID, import_id: uuid.UUID, p: Principal = Member(),
                         session: AsyncSession = Depends(get_session)):
    return await service.confirm_import(session, p.user_id, business_id, import_id)


@router.get(B + "/insights", response_model=DashboardOut)
async def insights(business_id: uuid.UUID, p: Principal = Member(), session: AsyncSession = Depends(get_session)):
    return await service.dashboard(session, p.user_id, business_id)
