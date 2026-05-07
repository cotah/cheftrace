"""Purchase list endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.purchase_list import PurchaseList
from app.models.purchase_list_item import PurchaseListItem
from app.schemas.purchase_list import (
    PurchaseListCreate,
    PurchaseListItemCreate,
    PurchaseListItemRead,
    PurchaseListItemUpdate,
    PurchaseListRead,
    PurchaseListUpdate,
    PurchaseListWithItemsRead,
    ReceiveItemInput,
)
from app.services.purchase_list_service import PurchaseListService

router = APIRouter(prefix="/restaurants/{restaurant_id}/purchase-lists", tags=["purchase-lists"])


@router.get("", response_model=list[PurchaseListRead])
async def list_purchase_lists(
    membership: CurrentMembership,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseList]:
    query = select(PurchaseList).where(
        PurchaseList.restaurant_id == membership.restaurant_id,
    )
    if status:
        query = query.where(PurchaseList.status == status)
    query = query.order_by(PurchaseList.created_at.desc()).limit(100)  # type: ignore[attr-defined]
    result = await session.exec(query)
    return list(result.all())


@router.post("", response_model=PurchaseListRead, status_code=201)
async def create_purchase_list(
    data: PurchaseListCreate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseList:
    svc = PurchaseListService(session)
    purchase_list = await svc.create_list(
        restaurant_id=membership.restaurant_id,
        list_type=data.type,
        notes=data.notes,
        created_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(purchase_list)
    return purchase_list


@router.get("/{list_id}", response_model=PurchaseListWithItemsRead)
async def get_purchase_list(
    list_id: UUID,
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    list_result = await session.exec(
        select(PurchaseList).where(
            PurchaseList.id == list_id,
            PurchaseList.restaurant_id == membership.restaurant_id,
        )
    )
    purchase_list = list_result.first()
    if not purchase_list:
        raise NotFoundError("PurchaseList")

    items_result = await session.exec(
        select(PurchaseListItem)
        .where(PurchaseListItem.purchase_list_id == list_id)
        .order_by(PurchaseListItem.created_at.asc())  # type: ignore[attr-defined]
    )
    items = list(items_result.all())

    return {
        **PurchaseListRead.model_validate(purchase_list).model_dump(),
        "items": [PurchaseListItemRead.model_validate(item) for item in items],
    }


@router.put("/{list_id}", response_model=PurchaseListRead)
async def update_purchase_list(
    list_id: UUID,
    data: PurchaseListUpdate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseList:
    result = await session.exec(
        select(PurchaseList).where(
            PurchaseList.id == list_id,
            PurchaseList.restaurant_id == membership.restaurant_id,
        )
    )
    purchase_list = result.first()
    if not purchase_list:
        raise NotFoundError("PurchaseList")
    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(purchase_list, field, value)
    session.add(purchase_list)
    await session.commit()
    await session.refresh(purchase_list)
    return purchase_list


@router.post(
    "/{list_id}/items",
    response_model=PurchaseListItemRead,
    status_code=201,
)
async def add_item(
    list_id: UUID,
    data: PurchaseListItemCreate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseListItem:
    svc = PurchaseListService(session)
    item = await svc.add_item(restaurant_id=membership.restaurant_id, list_id=list_id, data=data)
    await session.commit()
    await session.refresh(item)
    return item


@router.put("/{list_id}/items/{item_id}", response_model=PurchaseListItemRead)
async def update_item(
    list_id: UUID,
    item_id: UUID,
    data: PurchaseListItemUpdate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseListItem:
    svc = PurchaseListService(session)
    item = await svc.update_item(restaurant_id=membership.restaurant_id, item_id=item_id, data=data)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/{list_id}/items/{item_id}", status_code=204)
async def delete_item(
    list_id: UUID,
    item_id: UUID,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> None:
    svc = PurchaseListService(session)
    await svc.delete_item(restaurant_id=membership.restaurant_id, item_id=item_id)
    await session.commit()


@router.post("/{list_id}/send", response_model=PurchaseListRead)
async def send_purchase_list(
    list_id: UUID,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseList:
    svc = PurchaseListService(session)
    purchase_list = await svc.mark_sent(restaurant_id=membership.restaurant_id, list_id=list_id)
    await session.commit()
    await session.refresh(purchase_list)
    return purchase_list


@router.post(
    "/{list_id}/items/{item_id}/receive",
    response_model=PurchaseListItemRead,
)
async def receive_item(
    list_id: UUID,
    item_id: UUID,
    data: ReceiveItemInput,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_PURCHASE_LISTS)
    ),
    session: AsyncSession = Depends(get_session),
) -> PurchaseListItem:
    svc = PurchaseListService(session)
    item = await svc.receive_item(
        restaurant_id=membership.restaurant_id,
        item_id=item_id,
        data=data,
        received_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(item)
    return item
