import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import Agent, BundleCatalog, DataOrder, Payment, Transaction, User, Wallet
from backend.schemas.data_order import AgentDataOrderPurchaseResponse, AgentDataOrderRequest, DataOrderResponse
from backend.services.commission_service import record_commission
from backend.services.idata_service import IDataApiError, IDataService
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.notification import NotificationService
from utils.network import detect_network, normalize_ghana_number


router = APIRouter(prefix="/agent", tags=["Agent Data"])
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


def _normalize_idata_network(network: str) -> str:
    raw = str(network or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in SUPPORTED_NETWORKS_IDATA:
        return lowered
    upper = raw.upper()
    return NETWORK_LABEL_TO_IDATA.get(upper, "")


def _normalize_system_network(network: str) -> str:
    idata_network = _normalize_idata_network(network)
    reverse = {value: key for key, value in NETWORK_LABEL_TO_IDATA.items() if key != "VODAFONE"}
    return reverse.get(idata_network, "")


def _friendly_idata_order_status(raw_status: str, fallback: str = "") -> str:
    status_value = str(raw_status or "").strip().lower()
    if not status_value:
        return str(fallback or "").strip().title()
    if status_value in {"pending", "processing", "queued"}:
        return "Pending"
    if status_value in {"ordered", "order", "submitted", "received"}:
        return "Ordered"
    if status_value in {"completed", "complete", "successful", "success", "ok", "done"}:
        return "Complete"
    if status_value in {"cancelled", "canceled", "failed", "rejected", "abandoned", "error"}:
        return "Cancelled"
    return status_value.replace("_", " ").title()


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


async def _resolve_idata_bundle_catalog(
    db: AsyncSession,
    *,
    bundle_id: int,
    network_system: str,
) -> BundleCatalog:
    result = await db.execute(select(BundleCatalog).filter(BundleCatalog.id == bundle_id))
    bundle = result.scalars().first()
    if bundle and bool(getattr(bundle, "is_active", True)) and str(getattr(bundle, "provider", "")).lower() == "idata":
        if network_system and str(bundle.network or "").upper() != network_system.upper():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bundle network mismatch.")
        return bundle

    # Backward-compatible: treat bundle_id as provider package id.
    result = await db.execute(
        select(BundleCatalog).filter(
            BundleCatalog.is_active.is_(True),
            BundleCatalog.provider == "idata",
        )
    )
    candidates = result.scalars().all()
    for candidate in candidates:
        if network_system and str(candidate.network or "").upper() != network_system.upper():
            continue
        provider_package_id = _extract_idata_package_id(candidate)
        if provider_package_id == bundle_id:
            return candidate

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found or inactive.")


@router.post("/data", response_model=AgentDataOrderPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_data_as_agent(
    request: AgentDataOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service),
):
    try:
        role = str(getattr(current_user, "role", "") or "").strip().lower()
        if not bool(getattr(current_user, "is_agent", False)) and role != "agent":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only agents allowed.")

        result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
        agent = result.scalars().first()
        if not agent or str(getattr(agent, "status", "") or "").strip().lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active agent profile required.")

        phone = normalize_ghana_number(request.phone)
        if not phone or len(phone) != 10 or not phone.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")

        idata_network = _normalize_idata_network(request.network)
        if not idata_network:
            detected = _normalize_idata_network(detect_network(phone))
            idata_network = detected
        if idata_network not in SUPPORTED_NETWORKS_IDATA:
            supported = ", ".join(sorted(SUPPORTED_NETWORKS_IDATA))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported network. Use: {supported}.",
            )

        system_network = _normalize_system_network(idata_network)
        if not system_network:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported network.")

        bundle = await _resolve_idata_bundle_catalog(db, bundle_id=request.bundle_id, network_system=system_network)
        provider_package_id = _extract_idata_package_id(bundle)
        if provider_package_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bundle is missing iData package id. Update BundleCatalog.metadata_json with idata_package_id.",
            )

        selling_price = float(bundle.amount or 0.0)
        if selling_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bundle price is not configured.")
        discount_amount = round(float(getattr(settings, "AGENT_DATA_BUNDLE_DISCOUNT_GHS", 0.50) or 0.0), 2)
        amount_to_deduct = round(max(selling_price - discount_amount, 0.0), 2)
        if amount_to_deduct <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bundle price is not configured.")

        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        user_wallet = result.scalars().first()
        if not user_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for current user.")

        commission_rate = float(getattr(agent, "commission_rate", 0.0) or 0.0)
        commission_earned = round(selling_price * commission_rate, 2)

        funding_source = "agent_float"
        if float(getattr(agent, "float_balance", 0.0) or 0.0) >= amount_to_deduct:
            agent.float_balance = float(agent.float_balance or 0.0) - amount_to_deduct
        elif float(getattr(user_wallet, "balance", 0.0) or 0.0) >= amount_to_deduct:
            funding_source = "wallet"
            user_wallet.balance = float(user_wallet.balance or 0.0) - amount_to_deduct
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance. Top up agent float or wallet to continue.",
            )

        data_order = DataOrder(
            user_id=current_user.id,
            agent_id=agent.id,
            bundle_catalog_id=bundle.id,
            network=idata_network,
            phone=phone,
            bundle_id=int(provider_package_id),
            amount=amount_to_deduct,
            currency=str(bundle.currency or "GHS").upper(),
            status="pending",
            provider="idata",
        )
        db.add(user_wallet)
        db.add(agent)
        db.add(data_order)
        await db.flush()

        if not idata_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="iData provider is not configured. Set IDATA_API_KEY and IDATA_BASE_URL.",
            )

        provider_response: dict
        try:
            provider_response = await idata_service.place_order(
                network=idata_network,
                beneficiary=phone,
                bundle_package_id=int(provider_package_id),
            )
        except IDataApiError as exc:
            data_order.status = "failed"
            try:
                data_order.provider_response_json = json.dumps(
                    {"error": str(exc), "provider_response": getattr(exc, "response", None)}
                )
            except Exception:
                data_order.provider_response_json = json.dumps({"error": str(exc)})

            if funding_source == "agent_float":
                agent.float_balance = float(agent.float_balance or 0.0) + amount_to_deduct
            else:
                user_wallet.balance = float(user_wallet.balance or 0.0) + amount_to_deduct

            db.add(agent)
            db.add(user_wallet)
            db.add(data_order)
            await db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

        provider_reference = None
        for key in ("transaction_id", "order_id", "reference", "id"):
            value = provider_response.get(key) if isinstance(provider_response, dict) else None
            if value:
                provider_reference = str(value)
                break
        provider_status = str(provider_response.get("status", "") or "").strip().lower()
        pending_statuses = {"pending", "processing", "queued", "ordered"}
        success_statuses = {"success", "successful", "completed", "ok"}
        if provider_status and provider_status not in pending_statuses and provider_status not in success_statuses:
            data_order.status = "failed"
            try:
                data_order.provider_response_json = json.dumps(
                    {"provider_response": provider_response, "provider_status": provider_status}
                )
            except Exception:
                data_order.provider_response_json = json.dumps(provider_response)

            if funding_source == "agent_float":
                agent.float_balance = float(agent.float_balance or 0.0) + amount_to_deduct
            else:
                user_wallet.balance = float(user_wallet.balance or 0.0) + amount_to_deduct

            db.add(agent)
            db.add(user_wallet)
            db.add(data_order)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(provider_response.get("message") or "iData bundle delivery failed."),
            )

        order_status = "pending" if provider_status in pending_statuses else "completed"
        payment_status = "pending" if order_status == "pending" else "successful"
        transaction_status = "pending" if order_status == "pending" else "completed"
        commission_to_accrue = commission_earned if order_status == "completed" else 0.0
        status_label = _friendly_idata_order_status(provider_status or order_status, fallback=order_status)

        data_order.status = order_status
        data_order.provider_reference = provider_reference
        data_order.provider_response_json = json.dumps(provider_response)
        db.add(data_order)
        await db.flush()

        our_ref = f"IDATA_{uuid.uuid4().hex}"
        payment = Payment(
            user_id=current_user.id,
            agent_id=agent.id,
            processor="idata",
            type="agent_data_bundle_sale",
            amount=amount_to_deduct,
            currency=str(bundle.currency or "GHS").upper(),
            status=payment_status,
            our_transaction_id=our_ref,
            processor_transaction_id=provider_reference,
            metadata_json=json.dumps(
                {
                    "phone_number": phone,
                    "network_provider": system_network,
                    "bundle_catalog_id": bundle.id,
                    "idata_package_id": int(provider_package_id),
                    "data_order_id": data_order.id,
                    "user_price": round(selling_price, 2),
                    "agent_discount": discount_amount,
                    "agent_price": amount_to_deduct,
                    "commission_earned": commission_to_accrue,
                    "funding_source": funding_source,
                    "provider_status": provider_status or order_status,
                }
            ),
        )
        db.add(payment)
        await db.flush()

        transaction = Transaction(
            user_id=current_user.id,
            wallet_id=user_wallet.id,
            agent_id=agent.id,
            type="agent_data_bundle_sale",
            amount=amount_to_deduct,
            currency=str(bundle.currency or "GHS").upper(),
            commission_earned=commission_to_accrue,
            status=transaction_status,
            provider="idata",
            provider_reference=provider_reference or our_ref,
            metadata_json=json.dumps(
                {
                    "payment_id": payment.id,
                    "data_order_id": data_order.id,
                    "bundle_catalog_id": bundle.id,
                    "idata_package_id": int(provider_package_id),
                    "user_price": round(selling_price, 2),
                    "agent_discount": discount_amount,
                    "agent_price": amount_to_deduct,
                    "funding_source": funding_source,
                    "provider_status": provider_status or order_status,
                }
            ),
        )
        db.add(transaction)
        await db.flush()

        if commission_to_accrue > 0:
            agent.commission_balance = float(getattr(agent, "commission_balance", 0.0) or 0.0) + commission_to_accrue
            db.add(agent)

            await record_commission(
                db,
                agent_id=agent.id,
                user_id=current_user.id,
                amount=commission_to_accrue,
                currency=str(bundle.currency or "GHS").upper(),
                commission_type="AGENT_DATA_SALE_COMMISSION",
                status="accrued",
                transaction=transaction,
                metadata={
                    "network_provider": system_network,
                    "phone_number": phone,
                    "bundle_catalog_id": bundle.id,
                    "idata_package_id": int(provider_package_id),
                    "data_order_id": data_order.id,
                },
            )

            await ledger_service.create_journal_entry(
                description=f"Agent {agent.id} iData bundle sale to {phone}",
                ledger_entries_data=[
                    {
                        "account_name": "Cash (Agent Float)"
                        if funding_source == "agent_float"
                        else "Customer Wallets (Liability)",
                        "debit": amount_to_deduct if funding_source == "wallet" else 0.0,
                        "credit": amount_to_deduct if funding_source == "agent_float" else 0.0,
                    },
                    {"account_name": "Revenue - Data Bundle Sales", "debit": 0.0, "credit": amount_to_deduct},
                    {"account_name": "Commission Expense (Agent)", "debit": commission_to_accrue, "credit": 0.0},
                    {"account_name": "Accounts Payable (Agent Commission)", "debit": 0.0, "credit": commission_to_accrue},
                ],
                payment=payment,
                transaction=transaction,
            )

        await db.commit()

        if bool(getattr(settings, "IDATA_SEND_SMS", False)):
            await notification_service.send_sms(phone, "CyberCash: Your data bundle has been delivered successfully.")

        # Refresh response models.
        result = await db.execute(select(DataOrder).filter(DataOrder.id == data_order.id))
        order_row = result.scalars().first()
        if not order_row:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Order persistence failed.")

        return AgentDataOrderPurchaseResponse(
            order=DataOrderResponse.model_validate(order_row).model_copy(update={"status_label": status_label}),
            transaction_id=transaction.id,
            payment_id=payment.id,
            provider_response=provider_response,
        )
    finally:
        await db.close()
