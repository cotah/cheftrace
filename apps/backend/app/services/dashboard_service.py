"""
Dashboard service — computed alerts, no storage.
Role-based: chef gets no financial data.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions import Permission, has_permission
from app.models.equipment import Equipment
from app.models.haccp_run import HACCPChecklistRun
from app.models.haccp_template import HACCPChecklistTemplate
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.models.temperature_log import TemperatureLog
from app.schemas.dashboard import (
    DashboardResponseChef,
    DashboardResponseManager,
    ExpiryAlert,
    HACCPPendingAlert,
    LowStockAlert,
    TemperatureAlert,
)

logger = structlog.get_logger(__name__)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_dashboard(
        self,
        restaurant_id: UUID,
        role: str,
        expiry_warning_days: int = 3,
        critical_expiry_days: int = 1,
    ) -> DashboardResponseChef | DashboardResponseManager:
        today = date.today()

        expiry_alerts = await self._expiry_alerts(
            restaurant_id, today, expiry_warning_days, critical_expiry_days
        )
        critical_expiry = await self._critical_expiry_alerts(
            restaurant_id, today, critical_expiry_days
        )
        low_stock = await self._low_stock_alerts(restaurant_id)
        haccp_pending = await self._haccp_pending(restaurant_id, today)
        temp_alerts = await self._temperature_alerts(restaurant_id)
        total_active = await self._total_active_lots(restaurant_id)

        chef_data = DashboardResponseChef(
            expiry_alerts=expiry_alerts,
            critical_expiry=critical_expiry,
            low_stock=low_stock,
            haccp_pending=haccp_pending,
            temperature_out_of_range=temp_alerts,
            total_active_lots=total_active,
        )

        if not has_permission(role, Permission.VIEW_COSTS):
            return chef_data

        stock_value, partial, without_cost = await self._stock_value(restaurant_id)
        return DashboardResponseManager(
            **chef_data.model_dump(),
            stock_value_eur=stock_value,
            stock_value_partial=partial,
            lots_without_cost=without_cost,
        )

    async def _expiry_alerts(
        self,
        restaurant_id: UUID,
        today: date,
        warning_days: int,
        critical_days: int,
    ) -> list[ExpiryAlert]:
        cutoff = today + timedelta(days=warning_days)
        result = await self.session.exec(
            select(StockLot, Product)
            .join(Product, Product.id == StockLot.product_id)  # type: ignore[arg-type]
            .where(
                StockLot.restaurant_id == restaurant_id,
                StockLot.status == "active",
                StockLot.expiry_date != None,  # noqa: E711
                StockLot.expiry_date >= today,  # type: ignore[operator]
                StockLot.expiry_date <= cutoff,  # type: ignore[operator]
            )
            .order_by(StockLot.expiry_date.asc())  # type: ignore[union-attr]
        )
        alerts = []
        for lot, product in result.all():
            if lot.expiry_date is None:
                continue
            days_left = (lot.expiry_date - today).days
            if days_left > critical_days:
                alerts.append(
                    ExpiryAlert(
                        lot_id=str(lot.id),
                        product_id=str(lot.product_id),
                        product_name=product.name,
                        expiry_date=str(lot.expiry_date),
                        days_left=days_left,
                        quantity_remaining=float(lot.quantity_remaining),
                        unit=lot.unit,
                    )
                )
        return alerts

    async def _critical_expiry_alerts(
        self, restaurant_id: UUID, today: date, critical_days: int
    ) -> list[ExpiryAlert]:
        cutoff = today + timedelta(days=critical_days)
        result = await self.session.exec(
            select(StockLot, Product)
            .join(Product, Product.id == StockLot.product_id)  # type: ignore[arg-type]
            .where(
                StockLot.restaurant_id == restaurant_id,
                StockLot.status == "active",
                StockLot.expiry_date != None,  # noqa: E711
                StockLot.expiry_date <= cutoff,  # type: ignore[operator]
            )
            .order_by(StockLot.expiry_date.asc())  # type: ignore[union-attr]
        )
        alerts = []
        for lot, product in result.all():
            if lot.expiry_date is None:
                continue
            days_left = (lot.expiry_date - today).days
            alerts.append(
                ExpiryAlert(
                    lot_id=str(lot.id),
                    product_id=str(lot.product_id),
                    product_name=product.name,
                    expiry_date=str(lot.expiry_date),
                    days_left=days_left,
                    quantity_remaining=float(lot.quantity_remaining),
                    unit=lot.unit,
                )
            )
        return alerts

    async def _low_stock_alerts(self, restaurant_id: UUID) -> list[LowStockAlert]:
        result = await self.session.exec(
            select(Product).where(
                Product.restaurant_id == restaurant_id,
                Product.is_active == True,  # noqa: E712
                Product.minimum_stock_quantity != None,  # noqa: E711
            )
        )
        products = list(result.all())
        alerts = []
        for product in products:
            if product.minimum_stock_quantity is None:
                continue
            lots_result = await self.session.exec(
                select(StockLot).where(
                    StockLot.product_id == product.id,
                    StockLot.restaurant_id == restaurant_id,
                    StockLot.status == "active",
                )
            )
            lots = list(lots_result.all())
            total: Decimal = sum((lot.quantity_remaining for lot in lots), Decimal("0"))
            if total < product.minimum_stock_quantity:
                alerts.append(
                    LowStockAlert(
                        product_id=str(product.id),
                        product_name=product.name,
                        quantity_remaining=float(total),
                        minimum_stock_quantity=float(product.minimum_stock_quantity),
                        unit=product.unit,
                    )
                )
        return alerts

    async def _haccp_pending(self, restaurant_id: UUID, today: date) -> list[HACCPPendingAlert]:
        templates_result = await self.session.exec(
            select(HACCPChecklistTemplate).where(
                HACCPChecklistTemplate.restaurant_id == restaurant_id,
                HACCPChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
        templates = list(templates_result.all())
        pending = []

        for template in templates:
            if template.frequency == "daily":
                exists = await self._run_exists(restaurant_id, template.id, today, "completed")
                if not exists:
                    pending.append(
                        HACCPPendingAlert(
                            template_id=str(template.id),
                            template_name=template.name,
                            frequency=template.frequency,
                        )
                    )
            elif template.frequency == "shift" and template.shifts_per_day:
                count = await self._completed_runs_today(restaurant_id, template.id, today)
                for shift_num in range(count + 1, template.shifts_per_day + 1):
                    pending.append(
                        HACCPPendingAlert(
                            template_id=str(template.id),
                            template_name=template.name,
                            frequency=template.frequency,
                            shift_number=shift_num,
                        )
                    )
            elif template.frequency == "weekly":
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)
                exists = await self._run_exists_in_range(
                    restaurant_id, template.id, week_start, week_end
                )
                if not exists:
                    pending.append(
                        HACCPPendingAlert(
                            template_id=str(template.id),
                            template_name=template.name,
                            frequency=template.frequency,
                        )
                    )
            elif template.frequency == "monthly":
                month_start = today.replace(day=1)
                if today.month == 12:
                    month_end = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    month_end = today.replace(month=today.month + 1, day=1)
                exists = await self._run_exists_in_range(
                    restaurant_id, template.id, month_start, month_end
                )
                if not exists:
                    pending.append(
                        HACCPPendingAlert(
                            template_id=str(template.id),
                            template_name=template.name,
                            frequency=template.frequency,
                        )
                    )

        return pending

    async def _temperature_alerts(self, restaurant_id: UUID) -> list[TemperatureAlert]:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
        result = await self.session.exec(
            select(TemperatureLog, Equipment)
            .join(Equipment, Equipment.id == TemperatureLog.equipment_id)  # type: ignore[arg-type]
            .where(
                TemperatureLog.restaurant_id == restaurant_id,
                TemperatureLog.is_out_of_range == True,  # noqa: E712
                TemperatureLog.created_at >= cutoff,
            )
            .order_by(TemperatureLog.created_at.desc())  # type: ignore[attr-defined]
        )
        return [
            TemperatureAlert(
                log_id=str(log.id),
                equipment_id=str(log.equipment_id),
                equipment_name=eq.name,
                temperature=float(log.temperature),
                min_temp=float(eq.min_temp) if eq.min_temp is not None else None,
                max_temp=float(eq.max_temp) if eq.max_temp is not None else None,
                recorded_at=str(log.recorded_at),
            )
            for log, eq in result.all()
        ]

    async def _total_active_lots(self, restaurant_id: UUID) -> int:
        result = await self.session.exec(
            select(func.count(StockLot.id)).where(  # type: ignore[arg-type]
                StockLot.restaurant_id == restaurant_id,
                StockLot.status == "active",
            )
        )
        value = result.one()
        return int(value) if value is not None else 0

    async def _stock_value(self, restaurant_id: UUID) -> tuple[float | None, bool, int]:
        result = await self.session.exec(
            select(StockLot).where(
                StockLot.restaurant_id == restaurant_id,
                StockLot.status == "active",
            )
        )
        lots = list(result.all())
        total_lots = len(lots)
        lots_with_cost = [lot for lot in lots if lot.unit_cost is not None]
        without_cost = total_lots - len(lots_with_cost)
        if not lots_with_cost:
            return None, total_lots > 0, without_cost
        value = sum(
            float(lot.quantity_remaining) * float(lot.unit_cost)
            for lot in lots_with_cost
            if lot.unit_cost is not None
        )
        return round(value, 2), without_cost > 0, without_cost

    async def _run_exists(
        self,
        restaurant_id: UUID,
        template_id: UUID,
        run_date: date,
        status: str,
    ) -> bool:
        result = await self.session.exec(
            select(HACCPChecklistRun).where(
                HACCPChecklistRun.restaurant_id == restaurant_id,
                HACCPChecklistRun.template_id == template_id,
                HACCPChecklistRun.run_date == run_date,
                HACCPChecklistRun.status == status,
            )
        )
        return result.first() is not None

    async def _completed_runs_today(
        self, restaurant_id: UUID, template_id: UUID, run_date: date
    ) -> int:
        result = await self.session.exec(
            select(func.count(HACCPChecklistRun.id)).where(  # type: ignore[arg-type]
                HACCPChecklistRun.restaurant_id == restaurant_id,
                HACCPChecklistRun.template_id == template_id,
                HACCPChecklistRun.run_date == run_date,
                HACCPChecklistRun.status == "completed",
            )
        )
        value = result.one()
        return int(value) if value is not None else 0

    async def _run_exists_in_range(
        self,
        restaurant_id: UUID,
        template_id: UUID,
        start: date,
        end: date,
    ) -> bool:
        result = await self.session.exec(
            select(HACCPChecklistRun).where(
                HACCPChecklistRun.restaurant_id == restaurant_id,
                HACCPChecklistRun.template_id == template_id,
                HACCPChecklistRun.run_date >= start,
                HACCPChecklistRun.run_date < end,
                HACCPChecklistRun.status == "completed",
            )
        )
        return result.first() is not None
