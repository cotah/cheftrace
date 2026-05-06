"""
HACCP service — seed templates, run management, answer recording.

Rules:
- Seed templates created atomically with restaurant creation
- Dynamic temperature runs snapshot active equipment at start time
- complete_run validates all items have answer OR skip_reason
- haccp_checklist_answers are immutable (trigger in DB + no PUT/DELETE endpoints)
"""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.equipment import Equipment
from app.models.haccp_answer import HACCPChecklistAnswer
from app.models.haccp_item_template import HACCPChecklistItemTemplate
from app.models.haccp_run import HACCPChecklistRun
from app.models.haccp_template import HACCPChecklistTemplate
from app.schemas.haccp import HACCPAnswerCreate

logger = structlog.get_logger(__name__)


SEED_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Opening Check",
        "frequency": "daily",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "All fridges within temperature range (0-5°C)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "All freezers within temperature range (-18°C or below)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Hot hold equipment pre-heated to 63°C or above?",
                "item_type": "yes_no",
                "is_required": False,
            },
            {
                "order_index": 4,
                "question": "Hand wash stations stocked — soap, paper towels, sanitiser?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Staff wearing clean uniforms and correct PPE?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "All products correctly date-labelled?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "Prep area and surfaces clean from previous session?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Pest activity status",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "None observed",
                        "Suspected — action taken",
                        "Confirmed — pest control notified",
                    ]
                },
            },
        ],
    },
    {
        "name": "Closing Check",
        "frequency": "daily",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "All food products stored correctly and covered?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "All date labels checked and updated for carry-over items?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Fridge and freezer doors closed securely?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Final temperature check completed — all within range?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "All surfaces, equipment, and floors cleaned?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Food waste disposed of and bins cleaned?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "All non-essential gas and electrical equipment switched off?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Building secured — doors locked, alarms set?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 9,
                "question": "Any issues to report for next shift?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    {
        "name": "Temperature Log",
        "frequency": "shift",
        "shifts_per_day": 2,
        "is_equipment_dynamic": True,
        "items": [],
    },
    {
        "name": "Delivery Check",
        "frequency": "on_delivery",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Supplier / delivery company name",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "Delivery vehicle temperature within safe range?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "All product packaging intact — no damage or contamination?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "All products within use-by / best-before dates?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Chilled products received at 5°C or below?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Frozen products received at -15°C or below?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "Allergen documentation received and checked?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Products stored immediately after receipt?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 9,
                "question": "Any items rejected — details",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 10,
                "question": "Overall delivery decision",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "Accepted",
                        "Partially accepted — see notes",
                        "Rejected",
                    ]
                },
            },
        ],
    },
    {
        "name": "Cleaning Log",
        "frequency": "daily",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Areas cleaned",
                "item_type": "multi_select",
                "is_required": True,
                "min_selections": 1,
                "options_json": {
                    "options": [
                        "Prep surfaces/worktops",
                        "Chopping boards",
                        "Sinks and taps",
                        "Fridge interiors",
                        "Freezer exteriors",
                        "Oven/grill/range",
                        "Fryer",
                        "Floors",
                        "Bins and surrounds",
                        "Walls and splash backs",
                    ]
                },
            },
            {
                "order_index": 2,
                "question": "Cleaning chemicals used at correct dilution?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Colour-coded cloths and equipment used correctly?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "All cleaning completed to required standard?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Any areas requiring follow-up?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    {
        "name": "Weekly Deep Clean",
        "frequency": "weekly",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Areas deep cleaned",
                "item_type": "multi_select",
                "is_required": True,
                "min_selections": 1,
                "options_json": {
                    "options": [
                        "Behind and under fridges/freezers",
                        "Extractor hood and filters",
                        "Drains and drain covers",
                        "Wall tiles and grouting",
                        "Ceiling vents",
                        "Light fittings",
                        "Storage shelving",
                        "Walk-in fridge walls and floor",
                    ]
                },
            },
            {
                "order_index": 2,
                "question": "All cleaning chemicals recorded in COSHH log?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "No signs of pest activity found?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Deep clean completed to required standard?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Any maintenance issues identified?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
]


class HACCPService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_seed_templates(self, restaurant_id: UUID, created_by_user_id: UUID) -> None:
        """Create 6 default Irish HACCP templates on restaurant creation."""
        for tpl_data in SEED_TEMPLATES:
            items = tpl_data.get("items", [])
            tpl_fields = {k: v for k, v in tpl_data.items() if k != "items"}
            template = HACCPChecklistTemplate(
                restaurant_id=restaurant_id,
                created_by_user_id=created_by_user_id,
                is_seed=True,
                **tpl_fields,
            )
            self.session.add(template)
            await self.session.flush()

            for item_data in items:
                item = HACCPChecklistItemTemplate(
                    restaurant_id=restaurant_id,
                    template_id=template.id,
                    **item_data,
                )
                self.session.add(item)

        await self.session.flush()
        logger.info(
            "haccp.seed_templates_created",
            restaurant_id=str(restaurant_id),
            count=len(SEED_TEMPLATES),
        )

    async def start_run(
        self,
        restaurant_id: UUID,
        template_id: UUID,
        run_date: date,
        created_by_user_id: UUID,
        shift_number: int | None = None,
        notes: str | None = None,
    ) -> HACCPChecklistRun:
        """Start a checklist run. For dynamic templates, snapshots equipment."""
        result = await self.session.exec(
            select(HACCPChecklistTemplate).where(
                HACCPChecklistTemplate.id == template_id,
                HACCPChecklistTemplate.restaurant_id == restaurant_id,
                HACCPChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
        template = result.first()
        if not template:
            raise NotFoundError("HACCPChecklistTemplate")

        equipment_snapshot: list[dict[str, Any]] | None = None
        if template.is_equipment_dynamic:
            eq_result = await self.session.exec(
                select(Equipment).where(
                    Equipment.restaurant_id == restaurant_id,
                    Equipment.is_active == True,  # noqa: E712
                )
            )
            active_equipment = list(eq_result.all())
            equipment_snapshot = [
                {
                    "id": str(eq.id),
                    "name": eq.name,
                    "equipment_type": eq.equipment_type,
                    "min_temp": float(eq.min_temp) if eq.min_temp is not None else None,
                    "max_temp": float(eq.max_temp) if eq.max_temp is not None else None,
                }
                for eq in active_equipment
            ]

        run = HACCPChecklistRun(
            restaurant_id=restaurant_id,
            template_id=template_id,
            status="in_progress",
            run_date=run_date,
            shift_number=shift_number,
            equipment_snapshot_json=equipment_snapshot,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def submit_answer(
        self,
        restaurant_id: UUID,
        run_id: UUID,
        data: HACCPAnswerCreate,
        answered_by_user_id: UUID,
    ) -> HACCPChecklistAnswer:
        """Record a single answer for a run item."""
        result = await self.session.exec(
            select(HACCPChecklistRun).where(
                HACCPChecklistRun.id == run_id,
                HACCPChecklistRun.restaurant_id == restaurant_id,
            )
        )
        run = result.first()
        if not run:
            raise NotFoundError("HACCPChecklistRun")
        if run.status == "completed":
            raise ConflictError("Run is already completed")

        is_out_of_range = False
        if data.answer_numeric is not None and data.equipment_id:
            eq_result = await self.session.exec(
                select(Equipment).where(Equipment.id == data.equipment_id)
            )
            equipment = eq_result.first()
            if equipment:
                if equipment.min_temp is not None and data.answer_numeric < float(
                    equipment.min_temp
                ):
                    is_out_of_range = True
                if equipment.max_temp is not None and data.answer_numeric > float(
                    equipment.max_temp
                ):
                    is_out_of_range = True

        answer = HACCPChecklistAnswer(
            restaurant_id=restaurant_id,
            run_id=run_id,
            item_template_id=data.item_template_id,
            equipment_id=data.equipment_id,
            answer_bool=data.answer_bool,
            answer_numeric=data.answer_numeric,
            answer_text=data.answer_text,
            answer_options=data.answer_options,
            is_out_of_range=is_out_of_range,
            skip_reason=data.skip_reason,
            skip_reason_text=data.skip_reason_text,
            answered_by_user_id=answered_by_user_id,
        )
        self.session.add(answer)
        await self.session.flush()
        return answer

    async def complete_run(
        self,
        restaurant_id: UUID,
        run_id: UUID,
        completed_by_user_id: UUID,
    ) -> HACCPChecklistRun:
        """
        Mark run as completed.
        Validates all required items have answer OR skip_reason.
        """
        result = await self.session.exec(
            select(HACCPChecklistRun).where(
                HACCPChecklistRun.id == run_id,
                HACCPChecklistRun.restaurant_id == restaurant_id,
            )
        )
        run = result.first()
        if not run:
            raise NotFoundError("HACCPChecklistRun")
        if run.status == "completed":
            raise ConflictError("Run is already completed")

        answers_result = await self.session.exec(
            select(HACCPChecklistAnswer).where(HACCPChecklistAnswer.run_id == run_id)
        )
        answers = list(answers_result.all())
        answered_item_ids = {str(a.item_template_id) for a in answers if a.item_template_id}
        answered_equipment_ids = {str(a.equipment_id) for a in answers if a.equipment_id}

        if not run.equipment_snapshot_json:
            items_result = await self.session.exec(
                select(HACCPChecklistItemTemplate).where(
                    HACCPChecklistItemTemplate.template_id == run.template_id,
                    HACCPChecklistItemTemplate.is_required == True,  # noqa: E712
                    HACCPChecklistItemTemplate.is_active == True,  # noqa: E712
                )
            )
            required_items = list(items_result.all())
            missing = [
                item.question for item in required_items if str(item.id) not in answered_item_ids
            ]
            if missing:
                raise ConflictError(f"Missing answers for required items: {', '.join(missing)}")
        else:
            snapshot_ids = {eq["id"] for eq in run.equipment_snapshot_json}
            missing_eq = snapshot_ids - answered_equipment_ids
            if missing_eq:
                raise ConflictError(
                    f"Missing temperature answers for {len(missing_eq)} equipment item(s)"
                )

        run.status = "completed"
        run.completed_by_user_id = completed_by_user_id
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(run)
        await self.session.flush()

        logger.info(
            "haccp.run_completed",
            run_id=str(run_id),
            restaurant_id=str(restaurant_id),
        )
        return run
