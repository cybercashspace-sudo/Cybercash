from datetime import datetime, timezone


KYC_TIER_LIMITS = {
    1: 2000.0,
    2: 10000.0,
    3: 50000.0,
}


def resolve_daily_limit_for_tier(kyc_tier: int) -> float:
    return float(KYC_TIER_LIMITS.get(int(kyc_tier or 1), KYC_TIER_LIMITS[1]))


def ensure_daily_window(user) -> None:
    now = datetime.now(timezone.utc)
    reset_at = user.daily_spent_reset_at
    if reset_at and reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    if not reset_at or reset_at.date() != now.date():
        user.daily_spent = 0.0
        user.daily_spent_reset_at = now
    if not user.daily_limit:
        user.daily_limit = resolve_daily_limit_for_tier(user.kyc_tier or 1)

