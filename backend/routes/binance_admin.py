from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.dependencies.auth import require_admin
from backend.models import User
from backend.services.binance_service import BinanceApiError, BinanceService


router = APIRouter(prefix="/admin/binance", tags=["Admin Binance"])
binance_service = BinanceService()
_BTC_DASHBOARD_CACHE: dict = {"ts": 0.0, "payload": None}
_BTC_DASHBOARD_TTL_SECONDS = 8.0


class BinanceWithdrawRequest(BaseModel):
    coin: str = Field(default="BTC", min_length=2, max_length=20)
    address: str = Field(..., min_length=6, max_length=256)
    amount: float = Field(..., gt=0)
    network: str | None = Field(default=None, min_length=2, max_length=64)
    address_tag: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=64)


@router.get("/health")
async def binance_health(admin_user: User = Depends(require_admin)):
    return {
        "configured": binance_service.is_configured(),
        "base_url": binance_service.base_url,
        "withdrawals_enabled": bool(getattr(settings, "BINANCE_WITHDRAWALS_ENABLED", False)),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/price/{symbol}")
async def get_symbol_price(symbol: str, admin_user: User = Depends(require_admin)):
    try:
        price = await binance_service.get_symbol_price(symbol.upper())
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"symbol": symbol.upper(), "price": price, "source": "binance", "updated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/balance/{asset}")
async def get_asset_balance(asset: str, admin_user: User = Depends(require_admin)):
    if not binance_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binance credentials are not configured. Set BINANCE_API_KEY and BINANCE_SECRET_KEY.",
        )
    try:
        balance = await binance_service.get_asset_balance(asset.upper())
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {
        "asset": str(balance.get("asset") or asset.upper()),
        "free": float(balance.get("free") or 0.0),
        "locked": float(balance.get("locked") or 0.0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "binance",
    }


@router.get("/deposit-address/{coin}")
async def get_deposit_address(coin: str, network: str | None = None, admin_user: User = Depends(require_admin)):
    if not binance_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binance credentials are not configured. Set BINANCE_API_KEY and BINANCE_SECRET_KEY.",
        )
    try:
        payload = await binance_service.get_deposit_address(coin=coin, network=network)
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {
        "coin": coin.upper(),
        "network": payload.get("network"),
        "address": payload.get("address"),
        "tag": payload.get("tag"),
        "url": payload.get("url"),
        "source": "binance",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deposits/{coin}")
async def list_deposits(coin: str, limit: int = 50, admin_user: User = Depends(require_admin)):
    if not binance_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binance credentials are not configured. Set BINANCE_API_KEY and BINANCE_SECRET_KEY.",
        )
    limit = max(1, min(int(limit), 200))
    try:
        rows = await binance_service.get_deposit_history(coin=coin, limit=limit)
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"coin": coin.upper(), "count": len(rows), "items": rows, "source": "binance"}


@router.post("/withdraw")
async def withdraw_crypto(payload: BinanceWithdrawRequest, admin_user: User = Depends(require_admin)):
    if not bool(getattr(settings, "BINANCE_WITHDRAWALS_ENABLED", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Withdrawals are disabled. Set BINANCE_WITHDRAWALS_ENABLED=true only after full security review.",
        )
    if not binance_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binance credentials are not configured. Set BINANCE_API_KEY and BINANCE_SECRET_KEY.",
        )
    try:
        resp = await binance_service.withdraw(
            coin=payload.coin,
            address=payload.address,
            amount=float(payload.amount),
            network=payload.network,
            address_tag=payload.address_tag,
            name=payload.name,
        )
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"status": "submitted", "provider_response": resp, "source": "binance"}


@router.get("/btc/dashboard")
async def get_btc_dashboard(admin_user: User = Depends(require_admin)):
    now = time.time()
    cached_payload = _BTC_DASHBOARD_CACHE.get("payload")
    if cached_payload and (now - float(_BTC_DASHBOARD_CACHE.get("ts", 0.0) or 0.0)) < _BTC_DASHBOARD_TTL_SECONDS:
        return cached_payload

    usd_to_ghs_rate = 12.0
    updated_at = datetime.now(timezone.utc).isoformat()

    try:
        usd_price = await binance_service.get_symbol_price("BTCUSDT")
    except BinanceApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    configured = binance_service.is_configured()
    btc_free = 0.0
    btc_locked = 0.0
    deposit_address = None
    deposit_network = None
    deposit_tag = None

    if configured:
        try:
            balance = await binance_service.get_asset_balance("BTC")
            btc_free = float(balance.get("free") or 0.0)
            btc_locked = float(balance.get("locked") or 0.0)
        except BinanceApiError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

        try:
            address_payload = await binance_service.get_deposit_address(coin="BTC")
            deposit_address = address_payload.get("address")
            deposit_network = address_payload.get("network")
            deposit_tag = address_payload.get("tag")
        except BinanceApiError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    ghs_value = btc_free * float(usd_price or 0.0) * usd_to_ghs_rate
    payload = {
        "configured": configured,
        "asset": "BTC",
        "btc_balance": btc_free,
        "btc_locked": btc_locked,
        "usd_price": float(usd_price or 0.0),
        "usd_to_ghs_rate": usd_to_ghs_rate,
        "ghs_value": float(ghs_value or 0.0),
        "address": deposit_address,
        "network": deposit_network,
        "tag": deposit_tag,
        "updated_at": updated_at,
        "source": "binance",
    }

    _BTC_DASHBOARD_CACHE["payload"] = payload
    _BTC_DASHBOARD_CACHE["ts"] = now
    return payload
