from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies.auth import get_current_user
from backend.database import get_db
from backend.models import User


router = APIRouter(prefix="/api/sms", tags=["SMS"])


@router.post("/send", status_code=status.HTTP_200_OK)
async def send_sms_api(
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="SMS notifications are disabled. Notifications are sent to account email only.",
    )
