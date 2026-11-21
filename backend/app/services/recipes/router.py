import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.admin import service as admin
from app.services.admin.schemas import DisputeIn, DisputeOut
from app.services.recipes import service
from app.services.recipes.schemas import (ModifierGroupIn, ModifierGroupOut, ModifierIn, ModifierOut, OverrideIn,
                                          PreviewIn, PreviewOut, ReconfirmOut, RecipeIn, RecipeOut, ServingIn,
                                          ServingOut, VersionIn, VersionOut)

router = APIRouter(tags=["recipes"])
B = "/business/{business_id}"
Member = access.business_member


@router.get(B + "/recipes", response_model=list[RecipeOut])
async def list_recipes(business_id: uuid.UUID, p: Principal = Member(), session: AsyncSession = Depends(get_session)):
    return await service.list_recipes(session, p.user_id, business_id)


@router.post(B + "/recipes", response_model=RecipeOut, status_code=201)
async def create_recipe(business_id: uuid.UUID, body: RecipeIn, p: Principal = Member(),
                        session: AsyncSession = Depends(get_session)):
    return await service.create_recipe(session, p.user_id, business_id, body)


@router.post(B + "/recipes/preview", response_model=PreviewOut)
async def preview(business_id: uuid.UUID, body: PreviewIn, recipe_id: uuid.UUID | None = None, p: Principal = Member(),
                  session: AsyncSession = Depends(get_session)):
    return await service.preview(session, p.user_id, business_id, body, recipe_id)


@router.get(B + "/recipes/{recipe_id}", response_model=RecipeOut)
async def get_recipe(business_id: uuid.UUID, recipe_id: uuid.UUID, p: Principal = Member(),
                     session: AsyncSession = Depends(get_session)):
    return await service.get_recipe(session, p.user_id, business_id, recipe_id)


@router.get(B + "/recipes/{recipe_id}/versions", response_model=list[VersionOut])
async def list_versions(business_id: uuid.UUID, recipe_id: uuid.UUID, p: Principal = Member(),
                        session: AsyncSession = Depends(get_session)):
    return await service.list_versions(session, p.user_id, business_id, recipe_id)


@router.post(B + "/recipes/{recipe_id}/versions", response_model=VersionOut, status_code=201)
async def new_version(business_id: uuid.UUID, recipe_id: uuid.UUID, body: VersionIn, p: Principal = Member(),
                      session: AsyncSession = Depends(get_session)):
    return await service.new_version(session, p.user_id, business_id, recipe_id, body)


@router.post("/recipes/{recipe_id}/versions", response_model=VersionOut, status_code=201)
async def new_version_short(recipe_id: uuid.UUID, body: VersionIn, p: Principal = Member(),
                            session: AsyncSession = Depends(get_session)):
    return await service.new_version_by_recipe(session, p.user_id, recipe_id, body)


@router.post(B + "/recipes/{recipe_id}/override", response_model=RecipeOut, status_code=201)
async def override(business_id: uuid.UUID, recipe_id: uuid.UUID, body: OverrideIn, p: Principal = Member(),
                   session: AsyncSession = Depends(get_session)):
    return await service.override_for_branch(session, p.user_id, business_id, recipe_id, body.branch_id)


@router.post("/menu-items/{item_id}/reconfirm", response_model=ReconfirmOut)
async def reconfirm(item_id: uuid.UUID, p: Principal = Member(), session: AsyncSession = Depends(get_session)):
    return ReconfirmOut(expires_at=await service.reconfirm(session, p.user_id, item_id))


@router.get(B + "/menu-items/{item_id}/servings", response_model=list[ServingOut])
async def list_servings(business_id: uuid.UUID, item_id: uuid.UUID, p: Principal = Member(),
                        session: AsyncSession = Depends(get_session)):
    return await service.list_servings(session, p.user_id, business_id, item_id)


@router.post(B + "/menu-items/{item_id}/servings", response_model=ServingOut, status_code=201)
async def add_serving(business_id: uuid.UUID, item_id: uuid.UUID, body: ServingIn, p: Principal = Member(),
                      session: AsyncSession = Depends(get_session)):
    return await service.add_serving(session, p.user_id, business_id, item_id, body)


@router.delete(B + "/servings/{serving_id}", status_code=204)
async def delete_serving(business_id: uuid.UUID, serving_id: uuid.UUID, p: Principal = Member(),
                         session: AsyncSession = Depends(get_session)):
    await service.delete_serving(session, p.user_id, business_id, serving_id)
    return Response(status_code=204)


@router.get(B + "/menu-items/{item_id}/modifier-groups", response_model=list[ModifierGroupOut])
async def list_groups(business_id: uuid.UUID, item_id: uuid.UUID, p: Principal = Member(),
                      session: AsyncSession = Depends(get_session)):
    return await service.list_groups(session, p.user_id, business_id, item_id)


@router.post(B + "/menu-items/{item_id}/modifier-groups", response_model=ModifierGroupOut, status_code=201)
async def add_group(business_id: uuid.UUID, item_id: uuid.UUID, body: ModifierGroupIn, p: Principal = Member(),
                    session: AsyncSession = Depends(get_session)):
    return await service.add_group(session, p.user_id, business_id, item_id, body)


@router.post(B + "/modifier-groups/{group_id}/modifiers", response_model=ModifierOut, status_code=201)
async def add_modifier(business_id: uuid.UUID, group_id: uuid.UUID, body: ModifierIn, p: Principal = Member(),
                       session: AsyncSession = Depends(get_session)):
    return await service.add_modifier(session, p.user_id, business_id, group_id, body)


@router.delete(B + "/modifiers/{modifier_id}", status_code=204)
async def delete_modifier(business_id: uuid.UUID, modifier_id: uuid.UUID, p: Principal = Member(),
                          session: AsyncSession = Depends(get_session)):
    await service.delete_modifier(session, p.user_id, business_id, modifier_id)
    return Response(status_code=204)


@router.post(B + "/disputes", response_model=DisputeOut, status_code=201)
async def raise_dispute(business_id: uuid.UUID, body: DisputeIn, p: Principal = Member(),
                        session: AsyncSession = Depends(get_session)):
    """Explain a held recipe to the reviewer. Nothing can be hidden or removed this way."""
    return await admin.raise_dispute(session, p.user_id, business_id, body)
