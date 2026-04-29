from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    momo_number: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    is_verified: bool = True
    is_agent: bool = False # New field
    role: Optional[str] = None
    status: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
