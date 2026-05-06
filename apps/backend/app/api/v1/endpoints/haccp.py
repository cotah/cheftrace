"""HACCP checklist endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.haccp_answer import HACCPChecklistAnswer
from app.models.haccp_item_template import HACCPChecklistItemTemplate
from app.models.haccp_run import HACCPChecklistRun
from app.models.haccp_template import HACCPChecklistTemplate
from app.models.membership import RestaurantMembership
from app.schemas.haccp import (
    HACCPAnswerCreate,
    HACCPAnswerRead,
    HACCPItemCreate,
    HACCPItemRead,
    HACCPRunCreate,
    HACCPRunRead,
    HACCPTemplateCreate,
    HACCPTemplateRead,
)
from app.services.haccp_service import HACCPService

router = APIRouter(prefix="/restaurants/{restaurant_id}/haccp", tags=["haccp"])


@router.get("/templates", response_model=list[HACCPTemplateRead])
async def list_templates(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[HACCPChecklistTemplate]:
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.restaurant_id == membership.restaurant_id,
            HACCPChecklistTemplate.is_active == True,  # noqa: E712
        )
    )
    return list(result.all())


@router.post("/templates", response_model=HACCPTemplateRead, status_code=201)
async def create_template(
    data: HACCPTemplateCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistTemplate:
    template = HACCPChecklistTemplate(
        restaurant_id=membership.restaurant_id,
        created_by_user_id=membership.user_id,
        **data.model_dump(),
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.put("/templates/{template_id}", response_model=HACCPTemplateRead)
async def update_template(
    template_id: UUID,
    data: HACCPTemplateCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistTemplate:
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.id == template_id,
            HACCPChecklistTemplate.restaurant_id == membership.restaurant_id,
        )
    )
    template = result.first()
    if not template:
        raise NotFoundError("HACCPChecklistTemplate")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.SOFT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.id == template_id,
            HACCPChecklistTemplate.restaurant_id == membership.restaurant_id,
        )
    )
    template = result.first()
    if not template:
        raise NotFoundError("HACCPChecklistTemplate")
    template.is_active = False
    session.add(template)
    await session.commit()


@router.get("/templates/{template_id}/items", response_model=list[HACCPItemRead])
async def list_items(
    template_id: UUID,
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[HACCPChecklistItemTemplate]:
    result = await session.exec(
        select(HACCPChecklistItemTemplate)
        .where(
            HACCPChecklistItemTemplate.template_id == template_id,
            HACCPChecklistItemTemplate.restaurant_id == membership.restaurant_id,
            HACCPChecklistItemTemplate.is_active == True,  # noqa: E712
        )
        .order_by(HACCPChecklistItemTemplate.order_index.asc())  # type: ignore[attr-defined]
    )
    return list(result.all())


@router.post(
    "/templates/{template_id}/items",
    response_model=HACCPItemRead,
    status_code=201,
)
async def create_item(
    template_id: UUID,
    data: HACCPItemCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistItemTemplate:
    item = HACCPChecklistItemTemplate(
        restaurant_id=membership.restaurant_id,
        template_id=template_id,
        **data.model_dump(),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/runs", response_model=list[HACCPRunRead])
async def list_runs(
    membership: CurrentMembership,
    run_date: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[HACCPChecklistRun]:
    query = select(HACCPChecklistRun).where(
        HACCPChecklistRun.restaurant_id == membership.restaurant_id,
    )
    if run_date:
        query = query.where(HACCPChecklistRun.run_date == run_date)
    query = query.order_by(HACCPChecklistRun.run_date.desc()).limit(100)  # type: ignore[attr-defined]
    result = await session.exec(query)
    return list(result.all())


@router.post("/runs", response_model=HACCPRunRead, status_code=201)
async def start_run(
    data: HACCPRunCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistRun:
    svc = HACCPService(session)
    run = await svc.start_run(
        restaurant_id=membership.restaurant_id,
        template_id=data.template_id,
        run_date=data.run_date,
        created_by_user_id=membership.user_id,
        shift_number=data.shift_number,
        notes=data.notes,
    )
    await session.commit()
    await session.refresh(run)
    return run


@router.put("/runs/{run_id}/complete", response_model=HACCPRunRead)
async def complete_run(
    run_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistRun:
    svc = HACCPService(session)
    run = await svc.complete_run(
        restaurant_id=membership.restaurant_id,
        run_id=run_id,
        completed_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(run)
    return run


@router.post(
    "/runs/{run_id}/answers",
    response_model=HACCPAnswerRead,
    status_code=201,
)
async def submit_answer(
    run_id: UUID,
    data: HACCPAnswerCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> HACCPChecklistAnswer:
    svc = HACCPService(session)
    answer = await svc.submit_answer(
        restaurant_id=membership.restaurant_id,
        run_id=run_id,
        data=data,
        answered_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(answer)
    return answer


@router.get("/runs/{run_id}/answers", response_model=list[HACCPAnswerRead])
async def list_answers(
    run_id: UUID,
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[HACCPChecklistAnswer]:
    result = await session.exec(
        select(HACCPChecklistAnswer).where(
            HACCPChecklistAnswer.run_id == run_id,
            HACCPChecklistAnswer.restaurant_id == membership.restaurant_id,
        )
    )
    return list(result.all())
