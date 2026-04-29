from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import User
from backend.schemas.settings import (
    PlatformSettingsRead,
    PlatformSettingsUpdate,
    UserSettingsRead,
    UserSettingsUpdate,
)
from backend.services.settings_service import (
    get_or_create_platform_settings,
    get_or_create_user_settings,
    normalize_currency,
    normalize_payout_method,
)


router = APIRouter(prefix="/settings", tags=["Settings"])


def _require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if not bool(getattr(current_user, "is_admin", False)) and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action.",
        )
    return current_user


@router.get("/me", response_model=UserSettingsRead)
async def get_my_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_or_create_user_settings(db, current_user.id)


@router.put("/me", response_model=UserSettingsRead)
async def update_my_settings(
    payload: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = await get_or_create_user_settings(db, current_user.id)
    updates = payload.model_dump(exclude_unset=True)

    if "default_payout_method" in updates:
        updates["default_payout_method"] = normalize_payout_method(updates["default_payout_method"])
    if "preferred_currency" in updates:
        updates["preferred_currency"] = normalize_currency(updates["preferred_currency"])

    for key, value in updates.items():
        setattr(settings_row, key, value)

    db.add(settings_row)
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


@router.get("/platform", response_model=PlatformSettingsRead)
async def get_platform_settings(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(_require_admin_user),
):
    return await get_or_create_platform_settings(db)


@router.put("/platform", response_model=PlatformSettingsRead)
async def update_platform_settings(
    payload: PlatformSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(_require_admin_user),
):
    settings_row = await get_or_create_platform_settings(db)
    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(settings_row, key, value)

    settings_row.updated_by_user_id = admin_user.id
    db.add(settings_row)
    await db.commit()
    await db.refresh(settings_row)
    return settings_row
