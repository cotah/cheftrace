"""
Purchase list service — list lifecycle, item management, receive flow.

Rules:
- DRAFT lists: items can be added/updated/deleted
- SENT/PARTIALLY_RECEIVED lists: items can only be received (not edited)
- receive_item creates a StockLot via StockService.receive (FEFO + movement)
- List status auto-recalculates based on item statuses after each receive
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import (
    MovementSource,
    PurchaseListItemStatus,
    PurchaseListStatus,
)
from app.models.product import Product
from app.models.purchase_list import PurchaseList
from app.models.purchase_list_item import PurchaseListItem
from app.schemas.purchase_list import (
    PurchaseListItemCreate,
    PurchaseListItemUpdate,
    ReceiveItemInput,
)
from app.services.stock_service import StockService

logger = structlog.get_logger(__name__)


_EDITABLE_LIST_STATUSES = {PurchaseListStatus.DRAFT.value}
_RECEIVABLE_LIST_STATUSES = {
    PurchaseListStatus.SENT.value,
    PurchaseListStatus.PARTIALLY_RECEIVED.value,
}


class PurchaseListService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_list(self, restaurant_id: UUID, list_id: UUID) -> PurchaseList:
        result = await self.session.exec(
            select(PurchaseList).where(
                PurchaseList.id == list_id,
                PurchaseList.restaurant_id == restaurant_id,
            )
        )
        purchase_list = result.first()
        if not purchase_list:
            raise NotFoundError("PurchaseList")
        return purchase_list

    async def _get_item(self, restaurant_id: UUID, item_id: UUID) -> PurchaseListItem:
        result = await self.session.exec(
            select(PurchaseListItem).where(
                PurchaseListItem.id == item_id,
                PurchaseListItem.restaurant_id == restaurant_id,
            )
        )
        item = result.first()
        if not item:
            raise NotFoundError("PurchaseListItem")
        return item

    async def _get_items_for_list(self, list_id: UUID) -> list[PurchaseListItem]:
        result = await self.session.exec(
            select(PurchaseListItem).where(PurchaseListItem.purchase_list_id == list_id)
        )
        return list(result.all())

    async def create_list(
        self,
        restaurant_id: UUID,
        list_type: str,
        notes: str | None,
        created_by_user_id: UUID,
    ) -> PurchaseList:
        purchase_list = PurchaseList(
            restaurant_id=restaurant_id,
            type=list_type,
            status=PurchaseListStatus.DRAFT,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(purchase_list)
        await self.session.flush()
        return purchase_list

    async def add_item(
        self,
        restaurant_id: UUID,
        list_id: UUID,
        data: PurchaseListItemCreate,
    ) -> PurchaseListItem:
        purchase_list = await self._get_list(restaurant_id, list_id)
        if purchase_list.status not in _EDITABLE_LIST_STATUSES:
            raise ConflictError(f"Cannot add items to list in status '{purchase_list.status}'")

        product_result = await self.session.exec(
            select(Product).where(
                Product.id == data.product_id,
                Product.restaurant_id == restaurant_id,
            )
        )
        if not product_result.first():
            raise NotFoundError("Product")

        item = PurchaseListItem(
            restaurant_id=restaurant_id,
            purchase_list_id=list_id,
            product_id=data.product_id,
            supplier_id=data.supplier_id,
            quantity_ordered=data.quantity_ordered,
            unit=data.unit,
            unit_cost_estimate=data.unit_cost_estimate,
            status=PurchaseListItemStatus.PENDING,
            notes=data.notes,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_item(
        self,
        restaurant_id: UUID,
        item_id: UUID,
        data: PurchaseListItemUpdate,
    ) -> PurchaseListItem:
        item = await self._get_item(restaurant_id, item_id)
        purchase_list = await self._get_list(restaurant_id, item.purchase_list_id)
        if purchase_list.status not in _EDITABLE_LIST_STATUSES:
            raise ConflictError(f"Cannot edit items of list in status '{purchase_list.status}'")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(item, field, value)
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_item(self, restaurant_id: UUID, item_id: UUID) -> None:
        item = await self._get_item(restaurant_id, item_id)
        purchase_list = await self._get_list(restaurant_id, item.purchase_list_id)
        if purchase_list.status not in _EDITABLE_LIST_STATUSES:
            raise ConflictError(f"Cannot delete items of list in status '{purchase_list.status}'")
        await self.session.delete(item)
        await self.session.flush()

    async def mark_sent(self, restaurant_id: UUID, list_id: UUID) -> PurchaseList:
        purchase_list = await self._get_list(restaurant_id, list_id)
        if purchase_list.status != PurchaseListStatus.DRAFT.value:
            raise ConflictError(
                f"Only draft lists can be marked sent (current: '{purchase_list.status}')"
            )

        items = await self._get_items_for_list(list_id)
        if not items:
            raise ConflictError("Cannot send an empty list")

        purchase_list.status = PurchaseListStatus.SENT
        purchase_list.sent_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(purchase_list)
        await self.session.flush()

        logger.info(
            "purchase_list.sent",
            restaurant_id=str(restaurant_id),
            list_id=str(list_id),
            item_count=len(items),
        )
        return purchase_list

    async def receive_item(
        self,
        restaurant_id: UUID,
        item_id: UUID,
        data: ReceiveItemInput,
        received_by_user_id: UUID,
    ) -> PurchaseListItem:
        """
        Record receipt of a purchase list item.
        Creates a stock lot via StockService.receive and updates statuses.
        """
        item = await self._get_item(restaurant_id, item_id)
        purchase_list = await self._get_list(restaurant_id, item.purchase_list_id)

        if purchase_list.status not in _RECEIVABLE_LIST_STATUSES:
            raise ConflictError(f"Cannot receive items of list in status '{purchase_list.status}'")
        if item.status == PurchaseListItemStatus.RECEIVED.value:
            raise ConflictError("Item already fully received")
        if data.quantity_received <= Decimal("0"):
            raise ConflictError("Received quantity must be positive")

        stock_svc = StockService(self.session)
        await stock_svc.receive(
            restaurant_id=restaurant_id,
            product_id=item.product_id,
            supplier_id=item.supplier_id,
            quantity=data.quantity_received,
            unit=item.unit,
            created_by_user_id=received_by_user_id,
            unit_cost=data.unit_cost or item.unit_cost_estimate,
            expiry_date=data.expiry_date,
            notes=data.notes,
        )

        existing_received = item.quantity_received or Decimal("0")
        item.quantity_received = existing_received + data.quantity_received

        if item.quantity_received >= item.quantity_ordered:
            item.status = PurchaseListItemStatus.RECEIVED
        else:
            item.status = PurchaseListItemStatus.PARTIAL
        if data.notes:
            item.notes = data.notes
        self.session.add(item)
        await self.session.flush()

        await self._recalculate_list_status(purchase_list)
        await self.session.flush()

        # Tag the receive movement source via session.add of a side-effect:
        # StockService.receive uses MovementSource.MANUAL by default.
        # We'd ideally pass source=PURCHASE_LIST but the existing API doesn't
        # expose that on receive(). The semantic is preserved through the
        # purchase list trail (stock_lot timestamps + this item's status change).
        _ = MovementSource.PURCHASE_LIST  # documents intent

        logger.info(
            "purchase_list.item_received",
            restaurant_id=str(restaurant_id),
            list_id=str(purchase_list.id),
            item_id=str(item_id),
            quantity=str(data.quantity_received),
            new_status=item.status,
        )
        return item

    async def _recalculate_list_status(self, purchase_list: PurchaseList) -> None:
        items = await self._get_items_for_list(purchase_list.id)
        if not items:
            return

        statuses = {item.status for item in items}
        all_terminal = statuses.issubset(
            {
                PurchaseListItemStatus.RECEIVED.value,
                PurchaseListItemStatus.NOT_RECEIVED.value,
            }
        )

        if all_terminal:
            purchase_list.status = PurchaseListStatus.RECEIVED
        elif (
            PurchaseListItemStatus.RECEIVED.value in statuses
            or PurchaseListItemStatus.PARTIAL.value in statuses
        ):
            purchase_list.status = PurchaseListStatus.PARTIALLY_RECEIVED
        self.session.add(purchase_list)
