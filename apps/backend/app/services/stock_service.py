"""
Stock service — FEFO consumption, manual movements, lot management.

Rules:
- consume() always uses FEFO (expiry_date ASC NULLS LAST, received_date ASC, created_at ASC)
- manual_out() uses FEFO if lot_id is None, otherwise uses specified lot
- All movements are immutable — no UPDATE or DELETE ever
- quantity_remaining is denormalised on StockLot — updated within transaction
- SELECT ... FOR UPDATE prevents race conditions on concurrent consume
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.audit_log import AuditLog
from app.models.enums import (
    AuditAction,
    AuditEntity,
    LotStatus,
    MovementKind,
    MovementSource,
)
from app.models.stock_lot import StockLot
from app.models.stock_movement import StockMovement


@dataclass(frozen=True)
class FEFOAllocation:
    """A proposed deduction from a single lot. Used by previews."""

    lot_id: UUID
    expiry_date: date | None
    quantity_from_lot: Decimal
    unit_cost: Decimal | None
    unit: str


logger = structlog.get_logger(__name__)


class InsufficientStockError(ConflictError):
    def __init__(self, product_id: UUID, requested: Decimal, available: Decimal) -> None:
        super().__init__(
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )
        self.product_id = product_id
        self.requested = requested
        self.available = available


class StockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_lot_for_update(self, restaurant_id: UUID, lot_id: UUID) -> StockLot:
        """Fetch a single lot with row-level lock."""
        result = await self.session.exec(
            select(StockLot)
            .where(
                StockLot.id == lot_id,
                StockLot.restaurant_id == restaurant_id,
            )
            .with_for_update()
        )
        lot = result.first()
        if not lot:
            raise NotFoundError("StockLot")
        return lot

    async def _active_lots_fefo(self, restaurant_id: UUID, product_id: UUID) -> list[StockLot]:
        """Return active lots for a product in FEFO order, locked for update."""
        result = await self.session.exec(
            select(StockLot)
            .where(
                StockLot.restaurant_id == restaurant_id,
                StockLot.product_id == product_id,
                StockLot.status == LotStatus.ACTIVE,
                StockLot.quantity_remaining > Decimal("0"),
            )
            .order_by(
                StockLot.expiry_date.asc().nulls_last(),  # type: ignore[union-attr]
                StockLot.received_date.asc(),  # type: ignore[attr-defined]
                StockLot.created_at.asc(),  # type: ignore[attr-defined]
            )
            .with_for_update()
        )
        return list(result.all())

    def _create_movement(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        lot_id: UUID | None,
        kind: MovementKind,
        quantity: Decimal,
        unit: str,
        created_by_user_id: UUID,
        source: MovementSource = MovementSource.MANUAL,
        source_id: UUID | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> StockMovement:
        return StockMovement(
            restaurant_id=restaurant_id,
            product_id=product_id,
            lot_id=lot_id,
            kind=kind,
            source=source,
            source_id=source_id,
            quantity=quantity,
            unit=unit,
            reason=reason,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )

    async def peek_fefo_allocations(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        quantity_needed: Decimal,
    ) -> tuple[list[FEFOAllocation], Decimal]:
        """Read-only FEFO plan.

        Returns (allocations, total_available). If total_available < quantity_needed
        the caller is responsible for surfacing the shortage; allocations cover
        whatever stock IS available so the UI can render a partial preview.

        Does NOT lock the rows (unlike consume()) because the result is shown
        to the user before they commit. The real consumption re-queries with
        FOR UPDATE, so concurrent users still get correct totals.
        """
        result = await self.session.exec(
            select(StockLot)
            .where(
                StockLot.restaurant_id == restaurant_id,
                StockLot.product_id == product_id,
                StockLot.status == LotStatus.ACTIVE,
                StockLot.quantity_remaining > Decimal("0"),
            )
            .order_by(
                StockLot.expiry_date.asc().nulls_last(),  # type: ignore[union-attr]
                StockLot.received_date.asc(),  # type: ignore[attr-defined]
                StockLot.created_at.asc(),  # type: ignore[attr-defined]
            )
        )
        lots = list(result.all())
        total = sum((lot.quantity_remaining for lot in lots), Decimal("0"))

        allocations: list[FEFOAllocation] = []
        remaining = quantity_needed
        for lot in lots:
            if remaining <= Decimal("0"):
                break
            take = min(remaining, lot.quantity_remaining)
            allocations.append(
                FEFOAllocation(
                    lot_id=lot.id,
                    expiry_date=lot.expiry_date,
                    quantity_from_lot=take,
                    unit_cost=lot.unit_cost,
                    unit=lot.unit,
                )
            )
            remaining -= take
        return allocations, total

    async def receive(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        supplier_id: UUID | None,
        quantity: Decimal,
        unit: str,
        created_by_user_id: UUID,
        unit_cost: Decimal | None = None,
        expiry_date: date | None = None,
        received_date: date | None = None,
        notes: str | None = None,
        source: MovementSource = MovementSource.MANUAL,
    ) -> StockLot:
        """Create a new stock lot and record a receive movement.

        `source` tags the movement with its origin (manual entry, OCR
        invoice confirmation, purchase list reception, etc.) so reports
        can distinguish how the stock arrived.
        """
        lot = StockLot(
            restaurant_id=restaurant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            quantity_received=quantity,
            quantity_remaining=quantity,
            unit=unit,
            unit_cost=unit_cost,
            expiry_date=expiry_date,
            received_date=received_date or date.today(),
            status=LotStatus.ACTIVE,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(lot)
        await self.session.flush()

        movement = self._create_movement(
            restaurant_id=restaurant_id,
            product_id=product_id,
            lot_id=lot.id,
            kind=MovementKind.RECEIVE,
            quantity=quantity,
            unit=unit,
            created_by_user_id=created_by_user_id,
            source=source,
        )
        self.session.add(movement)
        await self.session.flush()

        logger.info(
            "stock.receive",
            restaurant_id=str(restaurant_id),
            product_id=str(product_id),
            lot_id=str(lot.id),
            quantity=str(quantity),
        )
        return lot

    async def consume(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        unit: str,
        created_by_user_id: UUID,
        source: MovementSource = MovementSource.MANUAL,
        source_id: UUID | None = None,
        reason: str | None = None,
    ) -> list[StockMovement]:
        """Consume stock via FEFO. Raises InsufficientStockError if not enough.

        source_id (when provided) lets callers tag every movement created
        by this consumption with the entity that triggered it (e.g. a
        recipe_production.id) so audit trails can drill back from the
        movement to its origin.
        """
        lots = await self._active_lots_fefo(restaurant_id, product_id)
        available = sum((lot.quantity_remaining for lot in lots), Decimal("0"))

        if available < quantity:
            raise InsufficientStockError(
                product_id=product_id,
                requested=quantity,
                available=available,
            )

        remaining = quantity
        movements: list[StockMovement] = []

        for lot in lots:
            if remaining <= Decimal("0"):
                break
            take = min(remaining, lot.quantity_remaining)
            lot.quantity_remaining -= take
            if lot.quantity_remaining == Decimal("0"):
                lot.status = LotStatus.DEPLETED
            self.session.add(lot)

            movement = self._create_movement(
                restaurant_id=restaurant_id,
                product_id=product_id,
                lot_id=lot.id,
                kind=MovementKind.CONSUME,
                quantity=-take,
                unit=unit,
                created_by_user_id=created_by_user_id,
                source=source,
                source_id=source_id,
                reason=reason,
            )
            self.session.add(movement)
            movements.append(movement)
            remaining -= take

        await self.session.flush()
        logger.info(
            "stock.consume",
            restaurant_id=str(restaurant_id),
            product_id=str(product_id),
            quantity=str(quantity),
            lots_touched=len(movements),
        )
        return movements

    async def manual_in(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        lot_id: UUID,
        quantity: Decimal,
        unit: str,
        created_by_user_id: UUID,
        reason: str | None = None,
        notes: str | None = None,
    ) -> StockMovement:
        """Add stock to an existing lot."""
        lot = await self._get_lot_for_update(restaurant_id, lot_id)
        lot.quantity_remaining += quantity
        if lot.status == LotStatus.DEPLETED:
            lot.status = LotStatus.ACTIVE
        self.session.add(lot)

        movement = self._create_movement(
            restaurant_id=restaurant_id,
            product_id=product_id,
            lot_id=lot_id,
            kind=MovementKind.MANUAL_IN,
            quantity=quantity,
            unit=unit,
            created_by_user_id=created_by_user_id,
            reason=reason,
            notes=notes,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def manual_out(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        unit: str,
        created_by_user_id: UUID,
        lot_id: UUID | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> list[StockMovement]:
        """
        Remove stock. If lot_id provided, uses that lot.
        If lot_id is None, uses FEFO (same as consume).
        """
        if lot_id is not None:
            lot = await self._get_lot_for_update(restaurant_id, lot_id)
            if lot.quantity_remaining < quantity:
                raise InsufficientStockError(
                    product_id=product_id,
                    requested=quantity,
                    available=lot.quantity_remaining,
                )
            lot.quantity_remaining -= quantity
            if lot.quantity_remaining == Decimal("0"):
                lot.status = LotStatus.DEPLETED
            self.session.add(lot)
            movement = self._create_movement(
                restaurant_id=restaurant_id,
                product_id=product_id,
                lot_id=lot_id,
                kind=MovementKind.MANUAL_OUT,
                quantity=-quantity,
                unit=unit,
                created_by_user_id=created_by_user_id,
                reason=reason,
                notes=notes,
            )
            self.session.add(movement)
            await self.session.flush()
            return [movement]

        lots = await self._active_lots_fefo(restaurant_id, product_id)
        available = sum((lot.quantity_remaining for lot in lots), Decimal("0"))
        if available < quantity:
            raise InsufficientStockError(
                product_id=product_id,
                requested=quantity,
                available=available,
            )

        remaining = quantity
        movements: list[StockMovement] = []
        for lot in lots:
            if remaining <= Decimal("0"):
                break
            take = min(remaining, lot.quantity_remaining)
            lot.quantity_remaining -= take
            if lot.quantity_remaining == Decimal("0"):
                lot.status = LotStatus.DEPLETED
            self.session.add(lot)
            movement = self._create_movement(
                restaurant_id=restaurant_id,
                product_id=product_id,
                lot_id=lot.id,
                kind=MovementKind.MANUAL_OUT,
                quantity=-take,
                unit=unit,
                created_by_user_id=created_by_user_id,
                reason=reason,
                notes=notes,
            )
            self.session.add(movement)
            movements.append(movement)
            remaining -= take

        await self.session.flush()
        return movements

    async def adjustment(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        unit: str,
        reason: str,
        created_by_user_id: UUID,
        lot_id: UUID | None = None,
        notes: str | None = None,
    ) -> StockMovement:
        """Stock count adjustment. quantity can be positive or negative."""
        if lot_id is not None:
            lot = await self._get_lot_for_update(restaurant_id, lot_id)
            new_remaining = lot.quantity_remaining + quantity
            if new_remaining < Decimal("0"):
                raise ConflictError(f"Adjustment would result in negative stock: {new_remaining}")
            lot.quantity_remaining = new_remaining
            if lot.quantity_remaining == Decimal("0"):
                lot.status = LotStatus.DEPLETED
            elif lot.status == LotStatus.DEPLETED and lot.quantity_remaining > Decimal("0"):
                lot.status = LotStatus.ACTIVE
            self.session.add(lot)

        movement = self._create_movement(
            restaurant_id=restaurant_id,
            product_id=product_id,
            lot_id=lot_id,
            kind=MovementKind.ADJUSTMENT,
            quantity=quantity,
            unit=unit,
            created_by_user_id=created_by_user_id,
            reason=reason,
            notes=notes,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def discard(
        self,
        restaurant_id: UUID,
        product_id: UUID,
        lot_id: UUID,
        created_by_user_id: UUID,
        reason: str | None = None,
    ) -> StockMovement:
        """Mark entire lot as discarded."""
        lot = await self._get_lot_for_update(restaurant_id, lot_id)
        discarded_qty = lot.quantity_remaining
        lot.quantity_remaining = Decimal("0")
        lot.status = LotStatus.DISCARDED
        self.session.add(lot)

        movement = self._create_movement(
            restaurant_id=restaurant_id,
            product_id=product_id,
            lot_id=lot_id,
            kind=MovementKind.DISCARD,
            quantity=-discarded_qty,
            unit=lot.unit,
            created_by_user_id=created_by_user_id,
            reason=reason,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def edit_lot_expiry(
        self,
        restaurant_id: UUID,
        lot_id: UUID,
        new_expiry_date: date,
        reason: str,
        changed_by_user_id: UUID,
    ) -> StockLot:
        """Edit lot expiry date with mandatory audit log."""
        lot = await self._get_lot_for_update(restaurant_id, lot_id)
        old_expiry = lot.expiry_date

        audit = AuditLog(
            restaurant_id=restaurant_id,
            entity_type=AuditEntity.STOCK_LOT,
            entity_id=lot_id,
            action=AuditAction.EXPIRY_EDIT,
            reason=reason,
            before_value={"expiry_date": str(old_expiry) if old_expiry else None},
            after_value={"expiry_date": str(new_expiry_date)},
            changed_by_user_id=changed_by_user_id,
        )
        self.session.add(audit)

        lot.expiry_date = new_expiry_date
        self.session.add(lot)
        await self.session.flush()

        logger.info(
            "stock_lot.expiry_edit",
            lot_id=str(lot_id),
            old=str(old_expiry),
            new=str(new_expiry_date),
            reason=reason,
        )
        return lot
