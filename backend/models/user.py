from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Enterprise identity model fields (backward-compatible rollout).
    momo_number = Column(String(15), unique=True, index=True, nullable=True)
    provider = Column(String, nullable=True)
    pin_hash = Column(String, nullable=True)

    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True) # Optional for Google users
    password_hash = Column(String, nullable=True) # Nullable for social login

    full_name = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_agent = Column(Boolean, default=False)
    role = Column(String, default="user")
    status = Column(String, default="active")

    verification_token = Column(String, nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempt_count = Column(Integer, default=0)
    reset_token = Column(String, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=True)
    bound_device_id = Column(String, nullable=True)
    first_login_fingerprint = Column(String, nullable=True)
    last_login_device_id = Column(String, nullable=True)
    last_login_ip = Column(String, nullable=True)
    failed_pin_attempts = Column(Integer, default=0)
    pin_locked_until = Column(DateTime(timezone=True), nullable=True)
    token_version = Column(Integer, default=0)

    # Compliance / KYC controls.
    kyc_tier = Column(Integer, default=1)
    daily_limit = Column(Float, default=2000.0)
    daily_spent = Column(Float, default=0.0)
    daily_spent_reset_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def first_name(self):
        raw = str(self.full_name or "").strip()
        if not raw:
            return None
        return raw.split()[0]

    agent = relationship("Agent", back_populates="user", uselist=False)
    agent_profile = relationship("AgentProfile", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    crypto_wallets = relationship("CryptoWallet", back_populates="user")
    crypto_transactions = relationship("CryptoTransaction", back_populates="user")
    virtual_cards = relationship("VirtualCard", back_populates="user") # New relationship for virtual cards
    commissions = relationship("Commission", back_populates="user")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False)
    loan_applications = relationship(
        "LoanApplication",
        back_populates="user",
        foreign_keys="LoanApplication.user_id",
    )
    loans = relationship(
        "Loan",
        back_populates="user",
        foreign_keys="Loan.user_id",
    )
