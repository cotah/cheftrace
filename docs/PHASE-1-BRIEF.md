# Phase 1 Brief — ChefTrace

> Version: 1.0
> Date: 2026-05-06
> Owner: Henrique
> Status: Ready for execution
> Estimated duration: 4-5 weeks (Sprint 1 extended for permissions)

## Context

Phase 0 delivered: monorepo skeleton, FastAPI health endpoint,
Next.js landing, CI green, Railway + Vercel deployed.

Phase 1 delivers the sellable core: a restaurant owner can control
food expiry, run HACCP digitally, manage stock manually, and create
purchase lists. By end of Phase 1, a real paying customer can use
the system unsupervised.

Phase 1 does NOT include: invoice OCR (Phase 2), recipes/auto
stock deduction (Phase 3), POS integration (Phase 4).

## Permission Matrix (implement exactly as specified)

### Roles: owner / manager / chef

**Principle:** manager and chef are operationally identical.
Single difference: manager sees money (€), chef does not.

**OWNER — can do everything without exception.**

**MANAGER and CHEF — identical on all of these:**
- Create/edit/complete purchase lists (any type)
- Receive delivery (manually — no OCR in Phase 1)
- Fill in lot expiry (mandatory per lot)
- Edit received quantity vs ordered quantity
- Create and edit products
- Create and edit suppliers
- Register all stock movements (in/out/adjustment)
- Register waste
- Edit lot expiry after creation (with mandatory audit log)
- Fill in any HACCP checklist
- Register temperature
- Create/edit HACCP templates
- Configure equipment (temperature limits)
- Resolve operational alerts
- Export HACCP operational PDFs (temperature log, daily checklist)

**MANAGER only (CHEF cannot):**
- View any € value (product cost, lot cost, waste cost,
  invoice total, dashboard €)
- Export financial reports (Stock €, Waste €, Purchase List €)
- Resolve critical alerts

**OWNER exclusive:**
- Invite/remove/edit member roles
- Edit restaurant data
- View billing
- Configure global alert thresholds
- Soft-delete templates, products, suppliers

### Automatic system protections

Audit log (immutable) triggered on:
- Lot expiry change → reason required (pre-defined list)
- HACCP template change
- Equipment limits change

Owner email notification (default ON, configurable) when:
- Manager/Chef changes HACCP template
- Manager/Chef changes equipment limits

Confirmation dialog before:
- Editing lot expiry: shows reason dropdown
  (Typo on entry / Supplier error / Inspection finding / Other)

Immutability: stock_movements never deleted by anyone.
Correction = new movement with opposite sign + reason.
Every action records created_by_user_id.

### Permission enum (backend implementation)

```python
class Permission(str, Enum):
    # Money (manager + owner)
    VIEW_COSTS = "view_costs"
    EXPORT_FINANCIAL_REPORTS = "export_financial_reports"
    RESOLVE_CRITICAL_ALERTS = "resolve_critical_alerts"
    # Operations (all roles)
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_SUPPLIERS = "manage_suppliers"
    MANAGE_STOCK = "manage_stock"
    MANAGE_HACCP = "manage_haccp"
    MANAGE_EQUIPMENT = "manage_equipment"
    MANAGE_PURCHASE_LISTS = "manage_purchase_lists"
    EXPORT_HACCP_PDF = "export_haccp_pdf"
    RESOLVE_OPERATIONAL_ALERTS = "resolve_operational_alerts"
    # Owner only
    MANAGE_MEMBERS = "manage_members"
    EDIT_RESTAURANT = "edit_restaurant"
    VIEW_BILLING = "view_billing"
    CONFIGURE_ALERTS = "configure_alerts"
    SOFT_DELETE = "soft_delete"
```

---

## Sprint 1 — Auth + Restaurants + Permissions (10 days)

### Goal
User can sign up, create a restaurant, invite team members with
roles, and the permission system is fully tested.

### New files — backend

**`app/core/security.py`**
```python
"""Supabase JWT verification."""
from typing import Any
import jwt
from fastapi import HTTPException, status
from app.core.config import settings

def verify_supabase_token(token: str) -> dict[str, Any]:
    """Verify and decode a Supabase JWT. Returns the payload."""
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
```

**`app/core/permissions.py`**
```python
"""Role-based permission system."""
from enum import Enum
from functools import lru_cache

class Permission(str, Enum):
    VIEW_COSTS = "view_costs"
    EXPORT_FINANCIAL_REPORTS = "export_financial_reports"
    RESOLVE_CRITICAL_ALERTS = "resolve_critical_alerts"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_SUPPLIERS = "manage_suppliers"
    MANAGE_STOCK = "manage_stock"
    MANAGE_HACCP = "manage_haccp"
    MANAGE_EQUIPMENT = "manage_equipment"
    MANAGE_PURCHASE_LISTS = "manage_purchase_lists"
    EXPORT_HACCP_PDF = "export_haccp_pdf"
    RESOLVE_OPERATIONAL_ALERTS = "resolve_operational_alerts"
    MANAGE_MEMBERS = "manage_members"
    EDIT_RESTAURANT = "edit_restaurant"
    VIEW_BILLING = "view_billing"
    CONFIGURE_ALERTS = "configure_alerts"
    SOFT_DELETE = "soft_delete"

_OPERATIONAL: frozenset[Permission] = frozenset({
    Permission.MANAGE_PRODUCTS,
    Permission.MANAGE_SUPPLIERS,
    Permission.MANAGE_STOCK,
    Permission.MANAGE_HACCP,
    Permission.MANAGE_EQUIPMENT,
    Permission.MANAGE_PURCHASE_LISTS,
    Permission.EXPORT_HACCP_PDF,
    Permission.RESOLVE_OPERATIONAL_ALERTS,
})

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "manager": frozenset({
        Permission.VIEW_COSTS,
        Permission.EXPORT_FINANCIAL_REPORTS,
        Permission.RESOLVE_CRITICAL_ALERTS,
    }) | _OPERATIONAL,
    "chef": _OPERATIONAL,
}

@lru_cache(maxsize=None)
def get_permissions(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())

def has_permission(role: str, permission: Permission) -> bool:
    return permission in get_permissions(role)
```

**`app/core/exceptions.py`**
```python
"""Custom exceptions and FastAPI exception handlers."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class ChefTraceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundError(ChefTraceError):
    def __init__(self, entity: str):
        super().__init__(f"{entity} not found", status_code=404)

class ForbiddenError(ChefTraceError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)

class ConflictError(ChefTraceError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ChefTraceError)
    async def cheftrace_error_handler(
        request: Request, exc: ChefTraceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
```

**`app/models/base.py`**
```python
"""Base SQLModel with timestamps."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel

class TimestampedBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )
```

**`app/models/user.py`**
```python
from sqlmodel import Field, SQLModel
from app.models.base import TimestampedBase

class User(TimestampedBase, table=True):
    __tablename__ = "users"
    email: str = Field(unique=True, nullable=False, index=True)
    full_name: str | None = None
    preferred_lang: str = Field(default="pt-BR")
```

**`app/models/restaurant.py`**
```python
from sqlmodel import Field
from app.models.base import TimestampedBase

class Restaurant(TimestampedBase, table=True):
    __tablename__ = "restaurants"
    name: str = Field(nullable=False)
    legal_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str = Field(default="IE")
    postal_code: str | None = None
    timezone: str = Field(default="Europe/Dublin")
    currency: str = Field(default="EUR")
    vat_number: str | None = None
    expiry_warning_days: int = Field(default=3)
    critical_expiry_days: int = Field(default=1)
    low_stock_alert_enabled: bool = Field(default=True)
    haccp_alert_enabled: bool = Field(default=True)
    is_active: bool = Field(default=True)
```

**`app/models/membership.py`**
```python
from uuid import UUID
from sqlmodel import Field, UniqueConstraint
from app.models.base import TimestampedBase

class RestaurantMembership(TimestampedBase, table=True):
    __tablename__ = "restaurant_memberships"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "user_id"),
    )
    restaurant_id: UUID = Field(foreign_key="restaurants.id",
                                 nullable=False, index=True)
    user_id: UUID = Field(foreign_key="users.id",
                           nullable=False, index=True)
    role: str = Field(nullable=False)  # owner / manager / chef
    is_active: bool = Field(default=True)
```

**`app/api/deps.py`**
```python
"""FastAPI dependencies for auth and multi-tenant access."""
from typing import Annotated
from uuid import UUID
import structlog
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.database import get_session
from app.core.permissions import Permission, has_permission
from app.core.security import verify_supabase_token
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.membership import RestaurantMembership
from app.models.user import User

logger = structlog.get_logger(__name__)

async def get_current_user(
    authorization: Annotated[str, Header()],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Verify JWT and return or create the user record."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.removeprefix("Bearer ")
    payload = verify_supabase_token(token)
    user_id = UUID(payload["sub"])
    email = payload.get("email", "")
    result = await session.exec(select(User).where(User.id == user_id))
    user = result.first()
    if not user:
        user = User(id=user_id, email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

async def get_current_membership(
    restaurant_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RestaurantMembership:
    """Return active membership or 404 (never 403 — do not reveal existence)."""
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == restaurant_id,
            RestaurantMembership.user_id == current_user.id,
            RestaurantMembership.is_active == True,
        )
    )
    membership = result.first()
    if not membership:
        raise NotFoundError("Restaurant")
    return membership

CurrentMembership = Annotated[
    RestaurantMembership, Depends(get_current_membership)
]

def require_permission(permission: Permission):
    """Dependency factory. Usage: Depends(require_permission(Permission.X))"""
    async def check(
        membership: CurrentMembership,
    ) -> RestaurantMembership:
        if not has_permission(membership.role, permission):
            raise ForbiddenError()
        return membership
    return check
```

**`app/schemas/restaurant.py`**
```python
from uuid import UUID
from pydantic import BaseModel

class RestaurantCreate(BaseModel):
    name: str
    legal_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str = "IE"
    postal_code: str | None = None
    timezone: str = "Europe/Dublin"
    currency: str = "EUR"
    vat_number: str | None = None

class RestaurantRead(BaseModel):
    id: UUID
    name: str
    legal_name: str | None
    city: str | None
    country: str
    timezone: str
    currency: str
    expiry_warning_days: int
    critical_expiry_days: int

class MemberRead(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool

class MemberInvite(BaseModel):
    email: str
    role: str  # manager / chef only — owner is assigned on create

class MemberRoleUpdate(BaseModel):
    role: str
```

**`app/api/v1/endpoints/auth.py`**
```python
"""Auth endpoints — thin proxy to Supabase, user sync."""
from fastapi import APIRouter
from app.api.deps import CurrentUser
from app.schemas.auth import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> UserRead:
    """Return current authenticated user."""
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
```

**`app/api/v1/endpoints/restaurants.py`**
```python
"""Restaurant CRUD + membership management."""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.api.deps import (
    CurrentUser, CurrentMembership, get_session, require_permission
)
from app.core.permissions import Permission
from app.core.exceptions import NotFoundError
from app.models.restaurant import Restaurant
from app.models.membership import RestaurantMembership
from app.models.user import User
from app.schemas.restaurant import (
    RestaurantCreate, RestaurantRead, MemberRead,
    MemberInvite, MemberRoleUpdate
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

@router.get("", response_model=list[RestaurantRead])
async def list_my_restaurants(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[RestaurantRead]:
    result = await session.exec(
        select(Restaurant)
        .join(RestaurantMembership,
              RestaurantMembership.restaurant_id == Restaurant.id)
        .where(
            RestaurantMembership.user_id == current_user.id,
            RestaurantMembership.is_active == True,
            Restaurant.is_active == True,
        )
    )
    return result.all()

@router.post("", response_model=RestaurantRead, status_code=201)
async def create_restaurant(
    data: RestaurantCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RestaurantRead:
    restaurant = Restaurant(**data.model_dump())
    session.add(restaurant)
    await session.flush()
    membership = RestaurantMembership(
        restaurant_id=restaurant.id,
        user_id=current_user.id,
        role="owner",
    )
    session.add(membership)
    await session.commit()
    await session.refresh(restaurant)
    return restaurant

@router.get("/{restaurant_id}", response_model=RestaurantRead)
async def get_restaurant(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> RestaurantRead:
    result = await session.exec(
        select(Restaurant).where(
            Restaurant.id == membership.restaurant_id
        )
    )
    restaurant = result.first()
    if not restaurant:
        raise NotFoundError("Restaurant")
    return restaurant

@router.put("/{restaurant_id}", response_model=RestaurantRead)
async def update_restaurant(
    data: RestaurantCreate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.EDIT_RESTAURANT)
    ),
    session: AsyncSession = Depends(get_session),
) -> RestaurantRead:
    result = await session.exec(
        select(Restaurant).where(
            Restaurant.id == membership.restaurant_id
        )
    )
    restaurant = result.first()
    if not restaurant:
        raise NotFoundError("Restaurant")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    session.add(restaurant)
    await session.commit()
    await session.refresh(restaurant)
    return restaurant

@router.get("/{restaurant_id}/members", response_model=list[MemberRead])
async def list_members(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[MemberRead]:
    result = await session.exec(
        select(RestaurantMembership, User)
        .join(User, User.id == RestaurantMembership.user_id)
        .where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.is_active == True,
        )
    )
    return [
        MemberRead(
            user_id=m.user_id,
            email=u.email,
            full_name=u.full_name,
            role=m.role,
            is_active=m.is_active,
        )
        for m, u in result.all()
    ]

@router.post("/{restaurant_id}/members", status_code=201)
async def invite_member(
    data: MemberInvite,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if data.role not in ("manager", "chef"):
        raise ValueError("Role must be manager or chef")
    user_result = await session.exec(
        select(User).where(User.email == data.email)
    )
    user = user_result.first()
    if not user:
        # User hasn't signed up yet — store pending invite
        # (simplified: return instructions to share signup link)
        return {"status": "pending", "message":
                "User not found. Share the app signup link."}
    existing = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user.id,
        )
    )
    existing_membership = existing.first()
    if existing_membership:
        existing_membership.is_active = True
        existing_membership.role = data.role
        session.add(existing_membership)
    else:
        new_membership = RestaurantMembership(
            restaurant_id=membership.restaurant_id,
            user_id=user.id,
            role=data.role,
        )
        session.add(new_membership)
    await session.commit()
    return {"status": "added"}

@router.put("/{restaurant_id}/members/{user_id}")
async def update_member_role(
    user_id: UUID,
    data: MemberRoleUpdate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user_id,
        )
    )
    target = result.first()
    if not target:
        raise NotFoundError("Member")
    if target.role == "owner":
        raise ValueError("Cannot change owner role")
    target.role = data.role
    session.add(target)
    await session.commit()
    return {"status": "updated"}

@router.delete("/{restaurant_id}/members/{user_id}")
async def remove_member(
    user_id: UUID,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user_id,
        )
    )
    target = result.first()
    if not target:
        raise NotFoundError("Member")
    if target.role == "owner":
        raise ValueError("Cannot remove owner")
    target.is_active = False
    session.add(target)
    await session.commit()
    return {"status": "removed"}
```

### Alembic migration — Sprint 1

```python
# alembic/versions/001_users_restaurants_memberships.py
"""users restaurants memberships

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text()),
        sa.Column("preferred_lang", sa.Text(),
                  nullable=False, server_default="pt-BR"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table("restaurants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("legal_name", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("country", sa.Text(), nullable=False, server_default="IE"),
        sa.Column("postal_code", sa.Text()),
        sa.Column("timezone", sa.Text(), nullable=False,
                  server_default="Europe/Dublin"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("vat_number", sa.Text()),
        sa.Column("expiry_warning_days", sa.Integer(),
                  nullable=False, server_default="3"),
        sa.Column("critical_expiry_days", sa.Integer(),
                  nullable=False, server_default="1"),
        sa.Column("low_stock_alert_enabled", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("haccp_alert_enabled", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_table("restaurant_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", UUID(as_uuid=True),
                  sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "user_id"),
    )
    op.create_index("ix_memberships_user",
                    "restaurant_memberships", ["user_id", "is_active"])
    op.create_index("ix_memberships_restaurant",
                    "restaurant_memberships", ["restaurant_id", "is_active"])

def downgrade() -> None:
    op.drop_table("restaurant_memberships")
    op.drop_table("restaurants")
    op.drop_table("users")
```

### Tests — Sprint 1

**`tests/conftest.py`** (update)
```python
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32chars-minimum!!")
os.environ.setdefault("ENVIRONMENT", "development")

from app.main import app
from app.core.database import get_session

TEST_DB_URL = os.environ["DATABASE_URL"]

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def session(engine):
    async_session = sessionmaker(engine, class_=AsyncSession,
                                  expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(session):
    app.dependency_overrides[get_session] = lambda: session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
```

**`tests/test_permissions.py`** — required regression tests
```python
"""Permission matrix regression tests. Must never regress."""
import pytest
from app.core.permissions import Permission, has_permission, get_permissions

# Owner has all permissions
def test_owner_has_all_permissions():
    for perm in Permission:
        assert has_permission("owner", perm), f"Owner missing {perm}"

# Manager has money permissions
def test_manager_sees_costs():
    assert has_permission("manager", Permission.VIEW_COSTS)
    assert has_permission("manager", Permission.EXPORT_FINANCIAL_REPORTS)

# Chef cannot see money
def test_chef_cannot_see_costs():
    assert not has_permission("chef", Permission.VIEW_COSTS)
    assert not has_permission("chef", Permission.EXPORT_FINANCIAL_REPORTS)
    assert not has_permission("chef", Permission.EXPORT_FINANCIAL_REPORTS)

# Chef can do operations
def test_chef_can_manage_stock():
    assert has_permission("chef", Permission.MANAGE_STOCK)
    assert has_permission("chef", Permission.MANAGE_PRODUCTS)
    assert has_permission("chef", Permission.MANAGE_HACCP)
    assert has_permission("chef", Permission.EXPORT_HACCP_PDF)

# Manager can do operations
def test_manager_can_manage_stock():
    assert has_permission("manager", Permission.MANAGE_STOCK)
    assert has_permission("manager", Permission.MANAGE_PRODUCTS)

# Owner-only
def test_only_owner_manages_members():
    assert has_permission("owner", Permission.MANAGE_MEMBERS)
    assert not has_permission("manager", Permission.MANAGE_MEMBERS)
    assert not has_permission("chef", Permission.MANAGE_MEMBERS)

def test_only_owner_soft_deletes():
    assert has_permission("owner", Permission.SOFT_DELETE)
    assert not has_permission("manager", Permission.SOFT_DELETE)
    assert not has_permission("chef", Permission.SOFT_DELETE)
```

**`tests/test_restaurants.py`** — multi-tenant regression
```python
"""Multi-tenant isolation regression tests."""
import pytest

@pytest.mark.asyncio
async def test_user_cannot_access_other_restaurant(client, session):
    """User A cannot see User B's restaurant — returns 404 not 403."""
    # Create restaurant A with user A
    # Try to access with user B
    # Expect 404
    pass  # implement with factories in Sprint 1

@pytest.mark.asyncio
async def test_chef_cannot_manage_members(client):
    """Chef role returns 403 on member management endpoints."""
    pass

@pytest.mark.asyncio
async def test_manager_cannot_edit_restaurant(client):
    """Manager role returns 403 on restaurant settings."""
    pass
```

### Frontend — Sprint 1

**Directory structure to create:**
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx         # auth layout (no sidebar)
│   │   ├── signin/page.tsx    # sign in form
│   │   └── signup/page.tsx    # sign up form
│   ├── (app)/
│   │   ├── layout.tsx         # app layout (sidebar + restaurant ctx)
│   │   └── [restaurantId]/
│   │       └── dashboard/
│   │           └── page.tsx   # placeholder for Sprint 3
│   └── onboarding/
│       └── page.tsx           # create first restaurant
├── lib/
│   ├── supabase/
│   │   ├── client.ts          # browser client
│   │   └── server.ts          # server client (RSC)
│   └── api/
│       └── client.ts          # fetch wrapper for FastAPI
├── middleware.ts               # route protection
├── hooks/
│   ├── use-auth.ts
│   └── use-restaurant.ts
└── components/
├── restaurant-selector.tsx
└── nav/
└── sidebar.tsx

**`middleware.ts`**
```typescript
import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { /* cookie handlers */ } }
  );
  const { data: { session } } = await supabase.auth.getSession();
  const { pathname } = request.nextUrl;
  const isAuthRoute = pathname.startsWith("/signin") ||
                      pathname.startsWith("/signup");
  const isAppRoute = pathname.startsWith("/app") ||
                     pathname.startsWith("/onboarding");
  if (!session && isAppRoute) {
    return NextResponse.redirect(new URL("/signin", request.url));
  }
  if (session && isAuthRoute) {
    return NextResponse.redirect(new URL("/onboarding", request.url));
  }
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

### Sprint 1 acceptance criteria

- [ ] `POST /api/v1/restaurants` creates restaurant + owner membership
- [ ] `GET /api/v1/restaurants` returns only user's restaurants
- [ ] `GET /api/v1/restaurants/{id}` returns 404 for non-member
- [ ] Chef role returns 403 on member management
- [ ] Manager role returns 403 on restaurant edit and billing
- [ ] All permission matrix unit tests pass (test_permissions.py)
- [ ] `uv run pytest` all green
- [ ] User can sign up, create restaurant, see dashboard placeholder
- [ ] Middleware redirects unauthenticated user to /signin
- [ ] Migration 001 applies cleanly: `alembic upgrade head`

---

## Sprint 2 — Products + Suppliers + Stock + FEFO (7 days)

### New models
`product_categories`, `suppliers`, `products`, `stock_lots`,
`stock_movements`

### Key service
`StockService` in `app/services/stock_service.py`:
- `consume(restaurant_id, product_id, quantity, unit, source)`
  → FEFO: orders lots by `expiry_date ASC NULLS LAST`,
  then `received_date ASC`
  → Raises `InsufficientStockError` if quantity > available
  → Returns list of created movements
- `manual_in(restaurant_id, product_id, lot_id, quantity, ...)`
- `manual_out(restaurant_id, product_id, quantity, reason, ...)`
- `adjustment(restaurant_id, product_id, quantity, reason, ...)`

### Endpoints
GET/POST   /restaurants/{id}/categories
GET/POST   /restaurants/{id}/suppliers
GET/PUT    /restaurants/{id}/suppliers/{sid}
GET/POST   /restaurants/{id}/products
GET/PUT    /restaurants/{id}/products/{pid}
GET/POST   /restaurants/{id}/stock-lots
PUT        /restaurants/{id}/stock-lots/{lid}
(expiry edit → audit log required)
POST       /restaurants/{id}/stock-lots/{lid}/discard
GET        /restaurants/{id}/stock-movements
POST       /restaurants/{id}/stock/manual-in
POST       /restaurants/{id}/stock/manual-out
POST       /restaurants/{id}/stock/adjustment

### Required tests (non-negotiable)
- FEFO: 10+ unit tests covering expiry ordering, NULLS LAST,
  partial consumption across multiple lots, insufficient stock
- Multi-tenant: product from restaurant B returns 404 to user A
- Immutability: no UPDATE/DELETE endpoint exists for movements
- Audit log created on lot expiry edit

### Frontend pages
- `/app/[rid]/products` — list with search + filter by category
- `/app/[rid]/products/new` — create form
- `/app/[rid]/suppliers` — list + create
- `/app/[rid]/stock` — lots overview (expiry status colour coded)
- `/app/[rid]/stock/receive` — create lot manually
- `/app/[rid]/stock/movements` — movement log (read only)

### Sprint 2 acceptance criteria
- [ ] StockService.consume with FEFO: 10 unit tests green
- [ ] Lot expiry edit creates audit_log entry
- [ ] Manual in/out/adjustment endpoints working
- [ ] Product from another restaurant returns 404
- [ ] Stock lot with status depleted/expired correctly reflected
- [ ] Frontend: create product, create lot, register movement

---

## Sprint 3 — Equipment + HACCP + Dashboard + Alerts (7 days)

### New models
`equipment`, `temperature_logs`, `haccp_checklist_templates`,
`haccp_checklist_item_templates`, `haccp_checklist_runs`,
`haccp_checklist_answers`

### Dashboard endpoint
`GET /restaurants/{id}/dashboard`

Returns:
```json
{
  "expiry_alerts": [...lots expiring in <= warning_days...],
  "critical_expiry": [...lots expiring in <= critical_days...],
  "low_stock": [...products below minimum_stock_quantity...],
  "haccp_pending": [...runs due today not yet completed...],
  "temperature_out_of_range": [...logs flagged in last 24h...],
  "stock_value_eur": 0.00  // null for chef role
}
```

### Alert severity
Operational (any role resolves):
- Expiry warning, low stock, HACCP pending, temperature alert

Critical (manager/owner only resolves):
- Expired lot consumed in sale (Phase 4), count discrepancy > 15%,
  suspicious adjustment pattern

### Irish HACCP seed templates
Seed on first restaurant creation:
- `Opening Check` (daily) — fridge temps, equipment check,
  hand wash station, date labels checked
- `Closing Check` (daily) — surfaces clean, stock stored,
  temperatures final, waste logged
- `Delivery Check` (on delivery) — van temp, packaging intact,
  use-by dates checked, stored immediately

### Sprint 3 acceptance criteria
- [ ] Dashboard returns correct data segmented by role
  (chef gets null for stock_value_eur)
- [ ] Temperature log out-of-range flags correctly
- [ ] HACCP run completion marks run as completed
- [ ] Irish seed templates created on restaurant create
- [ ] Alert severity correctly routed by role

---

## Sprint 4 — Purchase Lists + PDFs + Onboarding (7-10 days)

### Purchase List models
`purchase_lists`, `purchase_list_items`
purchase_lists:
id UUID PK
restaurant_id UUID FK
type ENUM(food, beverage, non_food, mixed)
status ENUM(draft, sent, partially_received, received)
notes TEXT
created_by_user_id UUID FK
sent_at TIMESTAMPTZ NULL
created_at, updated_at
purchase_list_items:
id UUID PK
purchase_list_id UUID FK
product_id UUID FK
supplier_id UUID FK NULL
quantity_ordered NUMERIC(12,3)
quantity_received NUMERIC(12,3) NULL
unit ENUM unit_kind
unit_cost_estimate NUMERIC(12,4) NULL
status ENUM(pending, received, partial, not_received)
notes TEXT
created_at, updated_at

### Purchase list flow
1. Create list → add items (product + qty + supplier)
2. Mark as sent (timestamp, status → sent)
3. On delivery: open sent list → per item: set qty_received,
   set expiry → confirm → system creates stock lots + movements
4. Shortcut: receive without list (direct lot creation)

### PDF reports (WeasyPrint)
- Temperature log PDF: date range, equipment, readings,
  out-of-range highlighted
- Daily checklist PDF: run date, items, answers, signature line
- Monthly HACCP summary: all runs for month,
  compliance % per template

### Onboarding wizard (4 steps)
1. Restaurant details
2. Add first product + first equipment
3. Configure first HACCP template (or use Irish defaults)
4. Create first purchase list (or skip)

### Sprint 4 acceptance criteria
- [ ] Full purchase list flow: create → send → receive → lots created
- [ ] Lot creation from purchase list receipt uses FEFO correctly
- [ ] 3 PDF types generated and downloadable
- [ ] Onboarding wizard completable without help
- [ ] Chef role cannot access € values anywhere in UI
- [ ] 1 real customer installed and operational

---

## Alembic migrations sequence
001_users_restaurants_memberships
002_categories_suppliers_products
003_stock_lots_movements
004_equipment_temperature
005_haccp_templates_runs_answers
006_audit_logs
007_purchase_lists
008_seed_haccp_templates (data migration)

## Test coverage targets (Phase 1 exit)

- Backend global: ≥ 75%
- `stock_service.py`: ≥ 90%
- `permissions.py`: 100%
- Multi-tenant regression: must pass in every PR

## Phase 1 release criteria

Before deploying to production for first customer:

- [ ] All sprints acceptance criteria met
- [ ] Zero open Blocker/Critical issues
- [ ] `uv run pytest --cov` ≥ 75% global, 90% stock_service
- [ ] Migration 001→008 applies and rolls back cleanly
- [ ] Chef role tested end-to-end: cannot see € anywhere
- [ ] Onboarding tested by someone who has never seen the app
- [ ] HACCP PDFs validated against Irish HSE format
  (validate template with one contact in Irish food industry
  before Sprint 4 ships — do not wait until after)
- [ ] README updated with Phase 1 setup instructions
- [ ] ADR updated if any stack decision changed
