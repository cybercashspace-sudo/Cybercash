from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class InitiatePaymentRequest(BaseModel):
    amount: float = Field(...)  # Amount in GHS, validated in route for user-friendly errors
    # email: str # Not needed, will use current_user's email

class InitiatePaymentResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str

class VerifyPaymentResponse(BaseModel):
    status: str
    message: str
    credited_amount: Optional[float] = None
    wallet_balance: Optional[float] = None
    # Add more fields if needed, e.g., transaction details, amount, currency
