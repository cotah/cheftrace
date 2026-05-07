"""
PDF report service — renders Jinja2 templates and converts to PDF via WeasyPrint.

WeasyPrint is imported lazily inside _render_to_pdf() because its native
GTK dependencies are not installed on Windows. The module imports cleanly
on Windows; only PDF generation requires the libs (production runs on
Linux Docker with libcairo, libpango, libgdk-pixbuf installed).
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.equipment import Equipment
from app.models.haccp_answer import HACCPChecklistAnswer
from app.models.haccp_item_template import HACCPChecklistItemTemplate
from app.models.haccp_run import HACCPChecklistRun
from app.models.haccp_template import HACCPChecklistTemplate
from app.models.restaurant import Restaurant
from app.models.temperature_log import TemperatureLog
from app.models.user import User

logger = structlog.get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)

_MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _render_to_pdf(html: str) -> bytes:
    """Render HTML to PDF bytes. Imports WeasyPrint lazily."""
    from weasyprint import HTML

    return HTML(string=html).write_pdf()  # type: ignore[no-any-return]


def _format_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


class PDFService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_restaurant(self, restaurant_id: UUID) -> Restaurant:
        result = await self.session.exec(select(Restaurant).where(Restaurant.id == restaurant_id))
        restaurant = result.first()
        if not restaurant:
            raise NotFoundError("Restaurant")
        return restaurant

    async def _user_email_map(self, user_ids: set[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        result = await self.session.exec(
            select(User).where(User.id.in_(list(user_ids)))  # type: ignore[attr-defined]
        )
        return {u.id: u.email for u in result.all()}

    def _base_context(self, restaurant: Restaurant) -> dict[str, Any]:
        return {
            "restaurant_name": restaurant.name,
            "restaurant_city": restaurant.city,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        }

    async def generate_temperature_log(
        self,
        restaurant_id: UUID,
        date_from: date,
        date_to: date,
        equipment_id: UUID | None = None,
    ) -> bytes:
        restaurant = await self._get_restaurant(restaurant_id)

        start = datetime.combine(date_from, datetime.min.time())
        end = datetime.combine(date_to, datetime.max.time())

        query = (
            select(TemperatureLog, Equipment)
            .join(Equipment, Equipment.id == TemperatureLog.equipment_id)  # type: ignore[arg-type]
            .where(
                TemperatureLog.restaurant_id == restaurant_id,
                TemperatureLog.recorded_at >= start,
                TemperatureLog.recorded_at <= end,
            )
            .order_by(TemperatureLog.recorded_at.desc())  # type: ignore[attr-defined]
        )
        if equipment_id is not None:
            query = query.where(TemperatureLog.equipment_id == equipment_id)

        result = await self.session.exec(query)
        rows = list(result.all())

        user_emails = await self._user_email_map({log.recorded_by_user_id for log, _ in rows})

        readings = [
            {
                "recorded_at_display": _format_dt(log.recorded_at),
                "equipment_name": eq.name,
                "location": eq.location,
                "temperature": float(log.temperature),
                "min_temp": float(eq.min_temp) if eq.min_temp is not None else None,
                "max_temp": float(eq.max_temp) if eq.max_temp is not None else None,
                "is_out_of_range": log.is_out_of_range,
                "recorded_by": user_emails.get(log.recorded_by_user_id, "—"),
            }
            for log, eq in rows
        ]

        equipment_filter = None
        if equipment_id is not None:
            eq_res = await self.session.exec(select(Equipment).where(Equipment.id == equipment_id))
            eq = eq_res.first()
            if eq:
                equipment_filter = eq.name

        context = {
            **self._base_context(restaurant),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "equipment_filter": equipment_filter,
            "total_readings": len(readings),
            "out_of_range_count": sum(1 for r in readings if r["is_out_of_range"]),
            "readings": readings,
        }

        template = _jinja_env.get_template("pdf/temperature_log.html")
        html = template.render(**context)
        pdf_bytes = _render_to_pdf(html)
        logger.info(
            "pdf.temperature_log",
            restaurant_id=str(restaurant_id),
            readings=len(readings),
            bytes=len(pdf_bytes),
        )
        return pdf_bytes

    async def generate_daily_checklist(self, restaurant_id: UUID, run_id: UUID) -> bytes:
        restaurant = await self._get_restaurant(restaurant_id)

        run_res = await self.session.exec(
            select(HACCPChecklistRun).where(
                HACCPChecklistRun.id == run_id,
                HACCPChecklistRun.restaurant_id == restaurant_id,
            )
        )
        run = run_res.first()
        if not run:
            raise NotFoundError("HACCPChecklistRun")

        template_res = await self.session.exec(
            select(HACCPChecklistTemplate).where(HACCPChecklistTemplate.id == run.template_id)
        )
        template_row = template_res.first()
        template_name = template_row.name if template_row else "HACCP Checklist"

        items_res = await self.session.exec(
            select(HACCPChecklistItemTemplate)
            .where(HACCPChecklistItemTemplate.template_id == run.template_id)
            .order_by(HACCPChecklistItemTemplate.order_index.asc())  # type: ignore[attr-defined]
        )
        items_by_id = {item.id: item for item in items_res.all()}

        answers_res = await self.session.exec(
            select(HACCPChecklistAnswer).where(HACCPChecklistAnswer.run_id == run_id)
        )
        answers = list(answers_res.all())

        equipment_ids = {a.equipment_id for a in answers if a.equipment_id}
        equipment_map: dict[UUID, str] = {}
        if equipment_ids:
            eq_res = await self.session.exec(
                select(Equipment).where(Equipment.id.in_(list(equipment_ids)))  # type: ignore[attr-defined]
            )
            equipment_map = {eq.id: eq.name for eq in eq_res.all()}

        user_ids: set[UUID] = {run.created_by_user_id}
        if run.completed_by_user_id:
            user_ids.add(run.completed_by_user_id)
        user_emails = await self._user_email_map(user_ids)

        entries: list[dict[str, Any]] = []
        for idx, ans in enumerate(answers, start=1):
            item = items_by_id.get(ans.item_template_id) if ans.item_template_id else None
            entries.append(
                {
                    "order": item.order_index if item else idx,
                    "question": item.question if item else "(equipment reading)",
                    "equipment_name": equipment_map.get(ans.equipment_id)
                    if ans.equipment_id
                    else None,
                    "answer_display": _format_answer(ans),
                    "is_out_of_range": ans.is_out_of_range,
                    "skip_reason": ans.skip_reason,
                    "skip_reason_text": ans.skip_reason_text,
                }
            )
        entries.sort(key=lambda e: int(e["order"]))

        context = {
            **self._base_context(restaurant),
            "template_name": template_name,
            "run_date": run.run_date.isoformat(),
            "shift_number": run.shift_number,
            "status": run.status,
            "completed_at_display": _format_dt(run.completed_at),
            "completed_by": user_emails.get(run.completed_by_user_id, "—")
            if run.completed_by_user_id
            else None,
            "created_by": user_emails.get(run.created_by_user_id, "—"),
            "run_notes": run.notes,
            "entries": entries,
        }

        template = _jinja_env.get_template("pdf/daily_checklist.html")
        html = template.render(**context)
        pdf_bytes = _render_to_pdf(html)
        logger.info(
            "pdf.daily_checklist",
            restaurant_id=str(restaurant_id),
            run_id=str(run_id),
            entries=len(entries),
            bytes=len(pdf_bytes),
        )
        return pdf_bytes

    async def generate_monthly_haccp_summary(
        self, restaurant_id: UUID, year: int, month: int
    ) -> bytes:
        restaurant = await self._get_restaurant(restaurant_id)

        month_start = date(year, month, 1)
        next_month = month_start.replace(
            year=year + (1 if month == 12 else 0), month=1 if month == 12 else month + 1
        )

        templates_res = await self.session.exec(
            select(HACCPChecklistTemplate).where(
                HACCPChecklistTemplate.restaurant_id == restaurant_id,
                HACCPChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
        templates = list(templates_res.all())

        runs_res = await self.session.exec(
            select(HACCPChecklistRun)
            .where(
                HACCPChecklistRun.restaurant_id == restaurant_id,
                HACCPChecklistRun.run_date >= month_start,
                HACCPChecklistRun.run_date < next_month,
            )
            .order_by(HACCPChecklistRun.run_date.asc())  # type: ignore[attr-defined]
        )
        runs = list(runs_res.all())

        answers_res = await self.session.exec(
            select(HACCPChecklistAnswer).where(
                HACCPChecklistAnswer.restaurant_id == restaurant_id,
                HACCPChecklistAnswer.created_at
                >= datetime.combine(month_start, datetime.min.time()),
                HACCPChecklistAnswer.created_at < datetime.combine(next_month, datetime.min.time()),
            )
        )
        answers = list(answers_res.all())
        out_of_range_runs = {a.run_id for a in answers if a.is_out_of_range}

        days_in_month = (next_month - month_start).days
        completed_by_template: dict[UUID, int] = {}
        for r in runs:
            if r.status == "completed":
                completed_by_template[r.template_id] = (
                    completed_by_template.get(r.template_id, 0) + 1
                )

        templates_data = []
        for t in templates:
            expected = _expected_runs(t.frequency, t.shifts_per_day, days_in_month)
            completed = completed_by_template.get(t.id, 0)
            pct = round(min(100.0, (completed / expected * 100.0) if expected else 100.0), 1)
            templates_data.append(
                {
                    "name": t.name,
                    "frequency": t.frequency,
                    "expected": expected,
                    "completed": completed,
                    "compliance_pct": pct,
                }
            )

        templates_by_id = {t.id: t for t in templates}
        runs_data = [
            {
                "run_date": r.run_date.isoformat(),
                "template_name": templates_by_id[r.template_id].name
                if r.template_id in templates_by_id
                else "—",
                "shift_number": r.shift_number,
                "status": r.status,
                "completed_at_display": _format_dt(r.completed_at) if r.completed_at else None,
                "has_out_of_range": r.id in out_of_range_runs,
            }
            for r in runs
        ]

        context = {
            **self._base_context(restaurant),
            "year": year,
            "month_name": _MONTH_NAMES[month - 1],
            "total_runs": len(runs),
            "completed_runs": sum(1 for r in runs if r.status == "completed"),
            "out_of_range_total": len(out_of_range_runs),
            "templates": templates_data,
            "runs": runs_data,
        }

        template = _jinja_env.get_template("pdf/monthly_haccp_summary.html")
        html = template.render(**context)
        pdf_bytes = _render_to_pdf(html)
        logger.info(
            "pdf.monthly_haccp_summary",
            restaurant_id=str(restaurant_id),
            year=year,
            month=month,
            runs=len(runs),
            bytes=len(pdf_bytes),
        )
        return pdf_bytes


def _format_answer(ans: HACCPChecklistAnswer) -> str:
    if ans.skip_reason:
        return "—"
    if ans.answer_bool is not None:
        return "YES" if ans.answer_bool else "NO"
    if ans.answer_numeric is not None:
        return f"{ans.answer_numeric}"
    if ans.answer_options:
        return ", ".join(ans.answer_options)
    if ans.answer_text:
        return ans.answer_text
    return "—"


def _expected_runs(frequency: str, shifts_per_day: int | None, days_in_month: int) -> int:
    if frequency == "daily":
        return days_in_month
    if frequency == "shift":
        return days_in_month * (shifts_per_day or 1)
    if frequency == "weekly":
        return max(1, days_in_month // 7)
    if frequency == "monthly":
        return 1
    if frequency == "on_delivery":
        return 0  # not applicable for compliance %
    return 0
