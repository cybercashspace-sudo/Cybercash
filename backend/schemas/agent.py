from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional
import re
from backend.schemas.user import UserResponse # Moved import to top

class AgentBase(BaseModel):
    status: str = "pending"
    business_name: Optional[str] = None
    agent_location: Optional[str] = None
    commission_rate: float = 0.0
    float_balance: float = 0.0
    commission_balance: float = 0.0
    is_borrowing_frozen: bool = False

class AgentCreate(AgentBase):
    user_id: int # The user this agent record is linked to

class AgentUpdate(AgentBase):
    status: Optional[str] = None
    commission_rate: Optional[float] = None
    float_balance: Optional[float] = None

class AgentCashDepositRequest(BaseModel):
    user_id: Optional[int] = None # Backward compatibility for older clients/tests
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: float
    currency: str = "GHS"
    topup_fee_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_customer_identifier(self):
        if self.customer_email:
            email = self.customer_email.strip().lower()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("customer_email must be a valid email address.")
            self.customer_email = email
        if self.customer_phone:
            self.customer_phone = self.customer_phone.strip()
        if not any([self.user_id, self.customer_email, self.customer_phone]):
            raise ValueError("Provide one of user_id, customer_email, or customer_phone.")
        return self

class AgentCashWithdrawalRequest(BaseModel):
    user_id: Optional[int] = None # Backward compatibility for older clients/tests
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: float
    currency: str = "GHS"

    @model_validator(mode="after")
    def validate_customer_identifier(self):
        if self.customer_email:
            email = self.customer_email.strip().lower()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("customer_email must be a valid email address.")
            self.customer_email = email
        if self.customer_phone:
            self.customer_phone = self.customer_phone.strip()
        if not any([self.user_id, self.customer_email, self.customer_phone]):
            raise ValueError("Provide one of user_id, customer_email, or customer_phone.")
        return self

class AgentAirtimeSaleRequest(BaseModel):
    phone_number: str
    amount: float
    currency: str = "GHS"
    network_provider: str

class AgentDataBundleSaleRequest(BaseModel):
    phone_number: str
    amount: float
    currency: str = "GHS"
    network_provider: str

class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int

    user: UserResponse

class AgentRegistrationRequest(BaseModel):
    # No direct fields needed as the user is identified by the auth token.
    pass

class AgentRegistrationResponse(BaseModel):
    authorization_url: Optional[str] = None
    reference: Optional[str] = None
    message: str
