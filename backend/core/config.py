import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)

# Load the shared root .env first, then let backend/.env override backend-only secrets.
load_dotenv(os.path.join(_ROOT_DIR, ".env"))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"), override=True)

class Settings:
    ENV = os.getenv("ENV", "development")

    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-that-no-one-can-guess-and-is-long-enough")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "CyberCash")
    HUBTEL_AUTH: str = os.getenv("HUBTEL_AUTH", "")
    HUBTEL_BASE_URL: str = os.getenv("HUBTEL_BASE_URL", "https://api-otp.hubtel.com")
    HUBTEL_SENDER_ID: str = os.getenv("HUBTEL_SENDER_ID", "CyberCash")
    HUBTEL_COUNTRY_CODE: str = os.getenv("HUBTEL_COUNTRY_CODE", "GH")
    HUBTEL_TIMEOUT_SECONDS: float = float(os.getenv("HUBTEL_TIMEOUT_SECONDS", 10))

    AGENT_REGISTRATION_FEE: float = float(os.getenv("AGENT_REGISTRATION_FEE", 100.0))
    AGENT_STARTUP_LOAN_AMOUNT: float = float(os.getenv("AGENT_STARTUP_LOAN_AMOUNT", 50.0))
    AIRTIME_CASH_PAYOUT_RATE: float = float(os.getenv("AIRTIME_CASH_PAYOUT_RATE", 0.80))
    AIRTIME_CASH_MIN_AMOUNT: float = float(os.getenv("AIRTIME_CASH_MIN_AMOUNT", 1.0))
    AIRTIME_CASH_MAX_AMOUNT: float = float(os.getenv("AIRTIME_CASH_MAX_AMOUNT", 1000.0))
    AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD: float = float(os.getenv("AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD", 200.0))
    AIRTIME_CASH_MERCHANT_MTN: str = os.getenv("AIRTIME_CASH_MERCHANT_MTN", "0559000000")
    AIRTIME_CASH_MERCHANT_TELECEL: str = os.getenv("AIRTIME_CASH_MERCHANT_TELECEL", "0209000000")
    AIRTIME_CASH_MERCHANT_AIRTELTIGO: str = os.getenv("AIRTIME_CASH_MERCHANT_AIRTELTIGO", "0279000000")
    AIRTIME_CASH_MERCHANT_DEFAULT: str = os.getenv("AIRTIME_CASH_MERCHANT_DEFAULT", "0559000000")
    AIRTIME_CASH_SMS_WEBHOOK_TOKEN: str = os.getenv("AIRTIME_CASH_SMS_WEBHOOK_TOKEN", "")
    AIRTIME_CASH_MOMO_CALLBACK_URL: str = os.getenv("AIRTIME_CASH_MOMO_CALLBACK_URL", "")
    ESCROW_MIN_DEAL_AMOUNT_GHS: float = float(os.getenv("ESCROW_MIN_DEAL_AMOUNT_GHS", 20.0))
    ESCROW_CREATE_FEE_GHS: float = float(os.getenv("ESCROW_CREATE_FEE_GHS", 5.0))
    ESCROW_RELEASE_FEE_GHS: float = float(os.getenv("ESCROW_RELEASE_FEE_GHS", 5.0))
    INVESTMENT_MIN_AMOUNT_GHS: float = float(os.getenv("INVESTMENT_MIN_AMOUNT_GHS", 10.0))
    INVESTMENT_MIN_DAYS: int = int(os.getenv("INVESTMENT_MIN_DAYS", 7))
    INVESTMENT_MAX_DAYS: int = int(os.getenv("INVESTMENT_MAX_DAYS", 365))
    INVESTMENT_RISK_FREE_ANNUAL_RATE: float = float(os.getenv("INVESTMENT_RISK_FREE_ANNUAL_RATE", 12.0))
    INVESTMENT_PROFIT_FEE_RATE: float = float(os.getenv("INVESTMENT_PROFIT_FEE_RATE", 0.10))
    WITHDRAWAL_APPROVAL_THRESHOLD_GHS: float = float(os.getenv("WITHDRAWAL_APPROVAL_THRESHOLD_GHS", 1000.0))
    TRANSACTION_FEE_PERCENTAGE: float = float(os.getenv("TRANSACTION_FEE_PERCENTAGE", 0.01))
    AGENT_COMMISSION_RATE: float = float(os.getenv("AGENT_COMMISSION_RATE", 0.02)) # 2% commission rate
    AGENT_DATA_BUNDLE_DISCOUNT_GHS: float = float(os.getenv("AGENT_DATA_BUNDLE_DISCOUNT_GHS", 0.50))

    # Google OAuth Credentials
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Binance API Credentials (for BTC integration)
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    # Preferred name (matches root .env); falls back to legacy BINANCE_API_SECRET.
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "") or os.getenv("BINANCE_API_SECRET", "")
    BINANCE_BASE_URL: str = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
    BINANCE_TIMEOUT_SECONDS: float = float(os.getenv("BINANCE_TIMEOUT_SECONDS", 10.0))
    BINANCE_RECV_WINDOW: int = int(os.getenv("BINANCE_RECV_WINDOW", 5000))
    BINANCE_WITHDRAWALS_ENABLED: bool = str(os.getenv("BINANCE_WITHDRAWALS_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Paystack API Credentials
    PAYSTACK_PUBLIC_KEY: str = os.getenv("PAYSTACK_PUBLIC_KEY", "")
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY", "")

    # Flutterwave API Credentials
    FLUTTERWAVE_BASE_URL: str = os.getenv("FLUTTERWAVE_BASE_URL", "https://api.flutterwave.com/v3")
    FLUTTERWAVE_TOKEN_URL: str = os.getenv("FLUTTERWAVE_TOKEN_URL", "https://idp.flutterwave.com/oauth/token")
    FLW_CLIENT_ID: str = os.getenv("FLW_CLIENT_ID", "")
    FLW_CLIENT_SECRET: str = os.getenv("FLW_CLIENT_SECRET", "")
    FLW_ENCRYPTION_KEY: str = os.getenv("FLW_ENCRYPTION_KEY", "")
    FLUTTERWAVE_SECRET_KEY: str = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
    FLUTTERWAVE_WEBHOOK_HASH: str = os.getenv("FLUTTERWAVE_WEBHOOK_HASH", "")

    # FX Settings
    FX_SPREAD_PERCENTAGE: float = float(os.getenv("FX_SPREAD_PERCENTAGE", 0.01)) # 1% spread on FX transactions

    # Virtual Card Settings
    VIRTUAL_CARD_CREATION_FEE_GHS: float = float(os.getenv("VIRTUAL_CARD_CREATION_FEE_GHS", 25.0))
    VIRTUAL_CARD_ISSUANCE_FEE_RECHARGEABLE: float = float(
        os.getenv("VIRTUAL_CARD_ISSUANCE_FEE_RECHARGEABLE", os.getenv("VIRTUAL_CARD_CREATION_FEE_GHS", 25.0))
    )
    VIRTUAL_CARD_ISSUANCE_FEE_ONETIME: float = float(
        os.getenv("VIRTUAL_CARD_ISSUANCE_FEE_ONETIME", os.getenv("VIRTUAL_CARD_CREATION_FEE_GHS", 25.0))
    )
    CARD_PROCESSOR_WEBHOOK_KEY: str = os.getenv("CARD_PROCESSOR_WEBHOOK_KEY", "dev-card-processor-key")

    # USSD Settings
    USSD_SHORTCODE: str = os.getenv("USSD_SHORTCODE", "*360#")


    # Loan Settings
    LOAN_REPAYMENT_PERCENTAGE: float = float(os.getenv("LOAN_REPAYMENT_PERCENTAGE", 0.20)) # 20% of commissions/fees for repayment
    MAX_FLOAT_WITHDRAWAL_PERCENTAGE: float = float(os.getenv("MAX_FLOAT_WITHDRAWAL_PERCENTAGE", 0.50)) # Max 50% of float can be withdrawn
    MAX_LOAN_AMOUNT_PER_AGENT: float = float(os.getenv("MAX_LOAN_AMOUNT_PER_AGENT", 5000.0)) # Max loan an agent can get
    DEFAULT_PENALTY_FEE_PERCENTAGE: float = float(os.getenv("DEFAULT_PENALTY_FEE_PERCENTAGE", 0.05)) # 5% penalty fee for overdue loans
    RISK_SCORE_APPROVAL_THRESHOLD: int = int(os.getenv("RISK_SCORE_APPROVAL_THRESHOLD", 50)) # Min risk score for loan approval

    # Crypto confirmations
    BTC_DEPOSIT_REQUIRED_CONFIRMATIONS: int = int(os.getenv("BTC_DEPOSIT_REQUIRED_CONFIRMATIONS", 3))

    # iData (Data bundles)
    IDATA_API_KEY: str = os.getenv("IDATA_API_KEY", "")
    IDATA_BASE_URL: str = os.getenv("IDATA_BASE_URL", "https://idatagh.com/wp-json/custom/v1")
    IDATA_TIMEOUT_SECONDS: float = float(os.getenv("IDATA_TIMEOUT_SECONDS", 12.0))
    IDATA_SEND_SMS: bool = str(os.getenv("IDATA_SEND_SMS", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

settings = Settings()
