from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import utcnow
from app.models.enums import MovementSource


class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"
    # Mirror the CHECK constraints from migrations so the test fixture
    # (which builds tables via SQLModel.metadata.create_all instead of
    # running alembic) also enforces them. Keep the value lists in sync
    # with the latest migration:
    #   - kind: migration 003 (untouched since)
    #   - source: migration 003 -> 011 (added 'recipe')
    #   - unit: migration 003 (untouched since)
    __table_args__ = (
        sa.CheckConstraint(
            "kind IN ('receive','manual_in','manual_out','adjustment','discard','consume')",
            name="ck_stock_movements_kind",
        ),
        sa.CheckConstraint(
            "source IN ('manual','purchase_list','pos','ocr','recipe')",
            name="ck_stock_movements_source",
        ),
        sa.CheckConstraint(
            "unit IN ('kg','g','l','ml','unit')",
            name="ck_stock_movements_unit",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    restaurant_id: UUID = Field(foreign_key="restaurants.id", nullable=False, index=True)
    product_id: UUID = Field(foreign_key="products.id", nullable=False, index=True)
    lot_id: UUID | None = Field(default=None, foreign_key="stock_lots.id", nullable=True)
    kind: str = Field(nullable=False)
    source: str = Field(default=MovementSource.MANUAL, nullable=False)
    # Polymorphic pointer at the entity that caused this movement —
    # interpretation depends on `source` (e.g. RECIPE → recipe_productions.id,
    # OCR → invoices.id). Nullable: legacy MANUAL movements don't have one.
    source_id: UUID | None = Field(default=None, nullable=True)
    quantity: Decimal = Field(sa_column=sa.Column(sa.NUMERIC(12, 3), nullable=False))
    unit: str = Field(nullable=False)
    reason: str | None = None
    notes: str | None = None
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
