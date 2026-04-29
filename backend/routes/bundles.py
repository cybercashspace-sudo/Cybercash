import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.transaction_types import TransactionType
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import BundleCatalog, Transaction, User, Wallet
from backend.schemas.bundle import BundleCatalogResponse, DataBundlePurchaseRequest
from backend.schemas.transaction import TransactionResponse
from backend.services.idata_service import IDataApiError, IDataService
from backend.services.momo import MomoService
from backend.services.notification import NotificationService
from utils.network import normalize_ghana_number


router = APIRouter(prefix="/api/bundles", tags=["Bundles"])
momo_service = MomoService()
idata_service = IDataService()
notification_service = NotificationService()


SUPPORTED_NETWORKS_IDATA = {"mtn", "telecel", "airteltigo"}
NETWORK_LABEL_TO_IDATA = {
    "MTN": "mtn",
    "TELECEL": "telecel",
    "VODAFONE": "telecel",
    "AIRTELTIGO": "airteltigo",
}


def _safe_json_load(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_idata_package_id(bundle: BundleCatalog) -> int | None:
    metadata = _safe_json_load(getattr(bundle, "metadata_json", None))
    for key in (
        "idata_package_id",
        "idata_bundle_id",
        "idata_bundle_package_id",
        "provider_package_id",
    ):
        if key in metadata and metadata[key] is not None:
            try:
                return int(str(metadata[key]).strip())
            except Exception:
                continue

    bundle_code = str(getattr(bundle, "bundle_code", "") or "").strip()
    if bundle_code.isdigit():
        try:
            return int(bundle_code)
        except Exception:
            return None

    return None


def _normalize_idata_network(network: str) -> str:
    raw = str(network or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in SUPPORTED_NETWORKS_IDATA:
        return lowered
    upper = raw.upper()
    return NETWORK_LABEL_TO_IDATA.get(upper, "")


def _bundle_network_filters(network: str) -> list[str]:
    net = str(network or "").strip().upper()
    if not net:
        return []
    if net in {"VODAFONE", "TELECEL"}:
        return ["VODAFONE", "TELECEL"]
    return [net]


@router.get("/catalog", response_model=List[BundleCatalogResponse])
async def list_active_bundle_catalog(
    network: Optional[str] = Query(default=None, min_length=2, max_length=20),
    provider: Optional[str] = Query(default=None, min_length=2, max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(BundleCatalog).filter(BundleCatalog.is_active.is_(True))
        if network:
            network_filters = _bundle_network_filters(network)
            if network_filters:
                query = query.filter(BundleCatalog.network.in_(network_filters))
        if provider:
            provider_value = str(provider or "").strip().lower()
            if provider_value:
                query = query.filter(BundleCatalog.provider == provider_value)
        query = query.order_by(BundleCatalog.network, BundleCatalog.amount, BundleCatalog.bundle_code)

        result = await db.execute(query)
        return result.scalars().all()
    finally:
        await db.close()


@router.post("/purchase", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def purchase_data_bundle(
    request: DataBundlePurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        phone = normalize_ghana_number(request.phone)
        if not phone or len(phone) != 10 or not phone.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")

        # Resolve bundle pricing from admin-managed catalog.
        network_filters = _bundle_network_filters(request.network)
        if not network_filters:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a valid network.")
        result = await db.execute(
            select(BundleCatalog).filter(
                BundleCatalog.network.in_(network_filters),
                BundleCatalog.bundle_code == request.bundle_code.upper(),
                BundleCatalog.is_active.is_(True),
            )
        )
        bundle = result.scalars().first()
        if not bundle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found or inactive.")
        amount = bundle.amount
        provider = str(getattr(bundle, "provider", "") or "").strip().lower() or "momo"

        idata_network = ""
        idata_package_id: int | None = None
        if provider == "idata":
            if not idata_service.is_configured():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="iData provider is not configured. Set IDATA_API_KEY and IDATA_BASE_URL.",
                )
            idata_network = _normalize_idata_network(getattr(bundle, "network", "") or request.network)
            if not idata_network:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported network for iData bundles. Use MTN, Telecel, or AirtelTigo.",
                )
            idata_package_id = _extract_idata_package_id(bundle)
            if idata_package_id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Bundle is missing iData package id. Update BundleCatalog.metadata_json with idata_package_id.",
                )

        # Validate wallet and deduct balance before provider API call.
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found.")
        if wallet.balance < amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance.")

        wallet.balance -= amount

        transaction = Transaction(
            user_id=current_user.id,
            wallet_id=wallet.id,
            type=TransactionType.DATA,
            amount=amount,
            currency=bundle.currency,
            status="pending",
            provider=provider,
            metadata_json=json.dumps(
                {
                    "network": bundle.network,
                    "bundle_code": bundle.bundle_code,
                    "phone": phone,
                    "bundle_catalog_id": bundle.id,
                    "provider": provider,
                    "idata_network": idata_network if provider == "idata" else None,
                    "idata_package_id": int(idata_package_id) if idata_package_id is not None else None,
                }
            ),
        )
        db.add(wallet)
        db.add(transaction)
        await db.flush()

        provider_response: dict = {}
        provider_status = ""
        provider_ref = ""

        if provider == "idata":
            try:
                provider_response = await idata_service.place_order(
                    network=idata_network,
                    beneficiary=phone,
                    bundle_package_id=int(idata_package_id),
                )
            except IDataApiError as exc:
                wallet.balance += amount
                db.add(wallet)

                transaction.status = "failed"
                transaction.provider_reference = f"IDATA_{uuid.uuid4().hex}"
                transaction.metadata_json = json.dumps(
                    {
                        "network": bundle.network,
                        "bundle_code": bundle.bundle_code,
                        "phone": phone,
                        "bundle_catalog_id": bundle.id,
                        "provider": provider,
                        "idata_network": idata_network,
                        "idata_package_id": int(idata_package_id),
                        "provider_error": str(exc),
                        "provider_response": getattr(exc, "response", None),
                    }
                )
                db.add(transaction)
                await db.commit()
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

            provider_status = str(provider_response.get("status", "") or "").strip().lower()
            for key in ("transaction_id", "order_id", "reference", "id"):
                value = provider_response.get(key) if isinstance(provider_response, dict) else None
                if value:
                    provider_ref = str(value)
                    break
            if not provider_ref:
                provider_ref = f"IDATA_{uuid.uuid4().hex}"

            if provider_status and provider_status not in {"success", "successful", "completed", "ok"}:
                wallet.balance += amount
                db.add(wallet)
                transaction.status = "failed"
                transaction.provider_reference = provider_ref
                transaction.metadata_json = json.dumps(
                    {
                        "network": bundle.network,
                        "bundle_code": bundle.bundle_code,
                        "phone": phone,
                        "bundle_catalog_id": bundle.id,
                        "provider": provider,
                        "idata_network": idata_network,
                        "idata_package_id": int(idata_package_id),
                        "provider_response": provider_response,
                    }
                )
                db.add(transaction)
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(provider_response.get("message") or "iData bundle delivery failed."),
                )
        else:
            # Call provider API (simulated MoMo fallback).
            provider_response = await momo_service.initiate_data_bundle_payment(
                phone_number=phone,
                amount=amount,
                currency=bundle.currency,
                network_provider=bundle.network,
                user_id=current_user.id,
            )

            provider_status = (provider_response.get("status") or "").lower()
            provider_ref = provider_response.get("processor_transaction_id") or f"MOMO_{uuid.uuid4().hex}"

        # Confirm and finalize transaction.
        transaction.provider_reference = provider_ref
        transaction.metadata_json = json.dumps(
            {
                "network": bundle.network,
                "bundle_code": bundle.bundle_code,
                "phone": phone,
                "bundle_catalog_id": bundle.id,
                "provider": provider,
                "idata_network": idata_network if provider == "idata" else None,
                "idata_package_id": int(idata_package_id) if idata_package_id is not None else None,
                "provider_response": provider_response,
            }
        )

        if provider == "idata" or provider_status in {"successful", "success", "completed", "ok"}:
            transaction.status = "completed"
            await db.commit()
            await db.refresh(transaction)

            if provider == "idata":
                if bool(getattr(settings, "IDATA_SEND_SMS", False)):
                    await notification_service.send_sms(
                        phone,
                        "CyberCash: Your data bundle has been delivered successfully.",
                    )
            else:
                await notification_service.send_sms(
                    phone,
                    f"CyberCash: Data bundle purchase successful. {transaction.currency} {amount:.2f} on {bundle.network}.",
                )

            return transaction

        # Provider failure -> refund wallet and persist failed transaction.
        wallet.balance += amount
        db.add(wallet)
        transaction.status = "failed"
        db.add(transaction)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(provider_response.get("message") or "Data bundle provider request failed."),
        )
    finally:
        await db.close()
