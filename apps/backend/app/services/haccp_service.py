"""
HACCP service — seed templates, run management, answer recording.

Rules:
- Seed templates created atomically with restaurant creation.
- Dynamic templates snapshot equipment at start_run time. When the template
  has equipment_type_filter set, the snapshot is restricted to active
  equipment of that type only (e.g. SC4 Hot Hold/Display captures only
  hot_hold units).
- complete_run validates all required items have answer OR skip_reason.
- haccp_checklist_answers are immutable (trigger in DB + no PUT/DELETE).

The seed templates implement the FSAI Safe Catering Pack records SC1-SC8.
Mapping is documented in the SEED_TEMPLATES list below.
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


# ----------------------------------------------------------------------
# FSAI Safe Catering Pack — seed templates
#
# Critical limits (FSAI Food Safety Authority of Ireland):
#   - Chilled food:       0-5 °C
#   - Frozen food:        <= -18 °C
#   - Hot holding:        >= 63 °C
#   - Cooking core temp:  >= 75 °C
#   - Reheating core temp: >= 70 °C
#   - Cooling:            63 °C to chilled within 2 hours
#   - Danger zone:        5 °C - 63 °C
# ----------------------------------------------------------------------

SEED_TEMPLATES: list[dict[str, Any]] = [
    # ------------------------------------------------------------------
    # SC5 — Hygiene Inspection (opening leg)
    # ------------------------------------------------------------------
    {
        "name": "Opening Check",
        "frequency": "daily",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "All fridges within critical limit (0-5°C, chilled CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "All freezers within critical limit (<= -18°C, frozen CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Hot hold equipment pre-heated to >= 63°C (hot hold CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Cold chain intact overnight (no equipment failure alarms)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Hand wash stations stocked — soap, paper towels, sanitiser?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Staff wearing clean uniforms and correct PPE?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "Ready-to-eat / high-risk foods stored above raw foods?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "All products correctly date-labelled?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 9,
                "question": "Prep area and surfaces clean from previous session?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 10,
                "question": "Cleaning chemicals stored away from food (separate area)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 11,
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
            {
                "order_index": 12,
                "question": "First aid kit accessible and stocked?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 13,
                "question": "Corrective action taken (if any CCP failed above)",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC5 — Hygiene Inspection (closing leg)
    # ------------------------------------------------------------------
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
                "question": "Raw and ready-to-eat foods physically separated?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "All date labels checked and updated for carry-over items?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Fridge and freezer doors closed securely?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Final fridge/freezer/hot hold temperature check completed within critical limits?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Equipment running normally overnight (no failure indicators)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "All surfaces, equipment, and floors cleaned?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Food waste disposed of and bins cleaned?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 9,
                "question": "Cleaning chemicals stored away from food after use?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 10,
                "question": "All non-essential gas and electrical equipment switched off?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 11,
                "question": "Building secured — doors locked, alarms set?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 12,
                "question": "Corrective action taken (if any CCP failed above)",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 13,
                "question": "Any issues to report for next shift?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC2 — Temperature Records (cold chain monitoring, all equipment)
    # ------------------------------------------------------------------
    {
        "name": "Temperature Log",
        "frequency": "shift",
        "shifts_per_day": 2,
        "is_equipment_dynamic": True,
        "items": [],
    },
    # ------------------------------------------------------------------
    # SC1 — Delivery / Goods Inwards Acceptance
    # ------------------------------------------------------------------
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
                "question": "Supplier invoice / reference number",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Delivery vehicle temperature within critical limit (chilled <= 5°C, frozen <= -15°C)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "All product packaging intact — no damage or contamination?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Batch codes / lot numbers recorded for traceability",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Use-by / best-before dates checked per product",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "Chilled products received at 0-5°C (cold chain CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Frozen products received at <= -15°C (cold chain CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 9,
                "question": "Allergen documentation received and checked?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 10,
                "question": "Products stored immediately after receipt (no time in danger zone)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 11,
                "question": "Overall delivery decision",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "Accepted",
                        "Conditionally accepted — see corrective action",
                        "Rejected — see corrective action",
                    ]
                },
            },
            {
                "order_index": 12,
                "question": "Items rejected / conditionally accepted — detail with reason",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 13,
                "question": "Corrective action taken (rejected items, supplier notification)",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC8 — Cleaning Schedule
    # ------------------------------------------------------------------
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
                        "Prep surfaces / worktops",
                        "Chopping boards (colour-coded)",
                        "Sinks and taps",
                        "Fridge interiors",
                        "Freezer exteriors",
                        "Oven / grill / range",
                        "Fryer",
                        "Floors",
                        "Bins and surrounds",
                        "Walls and splashbacks",
                    ]
                },
            },
            {
                "order_index": 2,
                "question": "Cleaning chemicals used at correct dilution (chemical CCP)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Sanitiser concentration verified",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "Visual check only",
                        "Test strip used",
                        "Surface swab taken",
                        "Not verified",
                    ]
                },
            },
            {
                "order_index": 4,
                "question": "Sanitiser strength in ppm (if measured)",
                "item_type": "numeric",
                "is_required": False,
            },
            {
                "order_index": 5,
                "question": "Colour-coded cloths and equipment used correctly per food zone?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Two-stage clean applied where required (clean then sanitise)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 7,
                "question": "All cleaning completed to required standard?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 8,
                "question": "Corrective action (if any answer above is No)",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 9,
                "question": "Any areas requiring follow-up?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC5 — Hygiene Inspection (weekly deep-clean leg)
    # ------------------------------------------------------------------
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
                        "Behind and under fridges / freezers",
                        "Extractor hood and filters",
                        "Drains and drain covers",
                        "Wall tiles and grouting",
                        "Ceiling vents",
                        "Light fittings",
                        "Storage shelving",
                        "Walk-in fridge walls and floor",
                        "Storeroom floors and corners",
                        "Outside bin areas",
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
                "question": "No signs of pest activity (droppings, grease tracks, gnaw marks)?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Ventilation and extraction filters cleaned or replaced?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Deep clean completed to required standard?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Corrective action (if any answer above is No)",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 7,
                "question": "Any maintenance issues identified?",
                "item_type": "text",
                "is_required": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC3 — Cooking / Cooling / Reheating Record
    # ------------------------------------------------------------------
    {
        "name": "SC3 — Cooking/Cooling/Reheating Record",
        "frequency": "on_delivery",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Food item / dish name",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "Process type (CCP)",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "Cooking",
                        "Cooling",
                        "Reheating",
                    ]
                },
            },
            {
                "order_index": 3,
                "question": "Core temperature reached (°C)",
                "item_type": "numeric",
                "is_required": True,
            },
            {
                "order_index": 4,
                "question": "Time temperature recorded (HH:MM)",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": (
                    "Critical limit met? "
                    "Cooking >= 75°C · Reheating >= 70°C · "
                    "Cooling 63°C -> chilled within 2 hours"
                ),
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 6,
                "question": "Corrective action if critical limit not met (re-cook, discard, etc.)",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 7,
                "question": "Person responsible",
                "item_type": "text",
                "is_required": True,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC4 — Hot Hold / Display Record (dynamic, hot_hold equipment only)
    # ------------------------------------------------------------------
    {
        "name": "SC4 — Hot Hold/Display Record",
        "frequency": "shift",
        "shifts_per_day": 3,
        "is_equipment_dynamic": True,
        "equipment_type_filter": "hot_hold",
        "items": [],
    },
    # ------------------------------------------------------------------
    # SC6 — Staff Hygiene Training Record
    # ------------------------------------------------------------------
    {
        "name": "SC6 — Staff Hygiene Training Record",
        "frequency": "on_delivery",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Staff member name",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "Training date (YYYY-MM-DD)",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Topics covered",
                "item_type": "multi_select",
                "is_required": True,
                "min_selections": 1,
                "options_json": {
                    "options": [
                        "Personal hygiene",
                        "Food handling",
                        "Allergen awareness",
                        "Temperature control (CCPs)",
                        "Cold chain and danger zone",
                        "Ready-to-eat / high-risk foods",
                        "Pest awareness",
                        "Cleaning and sanitisation procedures",
                        "Fitness to work",
                    ]
                },
            },
            {
                "order_index": 4,
                "question": "Trainer name",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Training material / certificate reference",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 6,
                "question": "Staff member acknowledged training and understood content?",
                "item_type": "yes_no",
                "is_required": True,
            },
        ],
    },
    # ------------------------------------------------------------------
    # SC7 — Fitness to Work Assessment
    # ------------------------------------------------------------------
    {
        "name": "SC7 — Fitness to Work Assessment",
        "frequency": "on_delivery",
        "is_equipment_dynamic": False,
        "items": [
            {
                "order_index": 1,
                "question": "Staff member name",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 2,
                "question": "Assessment date (YYYY-MM-DD)",
                "item_type": "text",
                "is_required": True,
            },
            {
                "order_index": 3,
                "question": "Symptoms reported in last 48 hours",
                "item_type": "multi_select",
                "is_required": True,
                "min_selections": 1,
                "options_json": {
                    "options": [
                        "None",
                        "Diarrhoea",
                        "Vomiting",
                        "Sore throat with fever",
                        "Skin infection (cuts, boils, septic spots)",
                        "Eye / ear / mouth infection",
                        "Jaundice",
                    ]
                },
            },
            {
                "order_index": 4,
                "question": "Symptoms cleared for >= 48 hours before return?",
                "item_type": "yes_no",
                "is_required": True,
            },
            {
                "order_index": 5,
                "question": "Manager assessment",
                "item_type": "single_select",
                "is_required": True,
                "options_json": {
                    "options": [
                        "Fit to work — full duties",
                        "Fit to work — restricted duties (no ready-to-eat food handling)",
                        "Excluded from food handling",
                    ]
                },
            },
            {
                "order_index": 6,
                "question": "Restrictions / notes (if applicable)",
                "item_type": "text",
                "is_required": False,
            },
            {
                "order_index": 7,
                "question": "Staff member acknowledged assessment?",
                "item_type": "yes_no",
                "is_required": True,
            },
        ],
    },
]


class HACCPService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _create_single_template(
        self,
        restaurant_id: UUID,
        created_by_user_id: UUID,
        tpl_data: dict[str, Any],
    ) -> HACCPChecklistTemplate:
        """Build one template + its items. Caller is responsible for commit."""
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
        return template

    async def create_seed_templates(self, restaurant_id: UUID, created_by_user_id: UUID) -> None:
        """Create all FSAI seed templates on restaurant creation."""
        for tpl_data in SEED_TEMPLATES:
            await self._create_single_template(restaurant_id, created_by_user_id, tpl_data)

        await self.session.flush()
        logger.info(
            "haccp.seed_templates_created",
            restaurant_id=str(restaurant_id),
            count=len(SEED_TEMPLATES),
        )

    async def reseed_missing_templates(
        self, restaurant_id: UUID, created_by_user_id: UUID
    ) -> tuple[list[str], list[str]]:
        """
        Add seed templates whose name does not yet exist for this restaurant.

        Idempotent: matches existing templates by `name` (regardless of is_seed
        flag — if the user already has a non-seed template with the same name,
        we skip it rather than create a duplicate). Existing templates are
        never modified.

        Returns (created_names, skipped_names).
        """
        existing_result = await self.session.exec(
            select(HACCPChecklistTemplate).where(
                HACCPChecklistTemplate.restaurant_id == restaurant_id,
            )
        )
        existing_names = {t.name for t in existing_result.all()}

        created: list[str] = []
        skipped: list[str] = []

        for tpl_data in SEED_TEMPLATES:
            name = tpl_data["name"]
            if name in existing_names:
                skipped.append(name)
                continue
            await self._create_single_template(restaurant_id, created_by_user_id, tpl_data)
            created.append(name)

        await self.session.flush()
        logger.info(
            "haccp.reseed",
            restaurant_id=str(restaurant_id),
            created=len(created),
            skipped=len(skipped),
        )
        return created, skipped

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
            eq_query = select(Equipment).where(
                Equipment.restaurant_id == restaurant_id,
                Equipment.is_active == True,  # noqa: E712
            )
            if template.equipment_type_filter:
                eq_query = eq_query.where(
                    Equipment.equipment_type == template.equipment_type_filter
                )
            eq_result = await self.session.exec(eq_query)
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
