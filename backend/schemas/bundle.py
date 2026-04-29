from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DataBundlePurchaseRequest(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)
    bundle_code: str = Field(..., min_length=1, max_length=64)
    phone: str = Field(..., min_length=6, max_length=20)


class BundleCatalogBase(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)
    bundle_code: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    provider: str = Field(default="momo", min_length=2, max_length=20)
    is_active: bool = True
    metadata_json: Optional[str] = None


class BundleCatalogCreate(BundleCatalogBase):
    pass


class BundleCatalogUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=10)
    provider: Optional[str] = Field(default=None, min_length=2, max_length=20)
    is_active: Optional[bool] = None
    metadata_json: Optional[str] = None


class BundleCatalogResponse(BundleCatalogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
