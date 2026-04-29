from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AgentKYCSubmitSchema(BaseModel):
    ghana_card_front_ref: str = Field(..., min_length=4, max_length=512)
    ghana_card_back_ref: str = Field(..., min_length=4, max_length=512)
    selfie_ref: str = Field(..., min_length=4, max_length=512)


class AgentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    ghana_card_number: Optional[str] = None
    kyc_status: str
    face_match_score: Optional[float] = None
    extracted_full_name: Optional[str] = None
    extracted_dob: Optional[str] = None
    extracted_expiry_date: Optional[str] = None

