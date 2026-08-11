from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PurchaseRecord:
    transaction_id: str
    type: str
    amount: float
    network: str
    status: str
    created_at: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PurchaseRecord":
        return cls(
            transaction_id=str(data.get("id") or data.get("transaction_id") or data.get("reference") or ""),
            type=str(data.get("type") or ""),
            amount=float(data.get("amount") or 0.0),
            network=str(data.get("network") or ""),
            status=str(data.get("status") or "completed"),
            created_at=str(data.get("created_at") or data.get("date") or ""),
            description=str(data.get("description") or ""),
        )


@dataclass
class DataPackage:
    package_id: str
    title: str
    description: str
    price: float
    network: str
    amount: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPackage":
        return cls(
            package_id=str(data.get("id") or data.get("package_id") or data.get("code") or ""),
            title=str(data.get("title") or data.get("name") or data.get("label") or "Package"),
            description=str(data.get("description") or data.get("summary") or ""),
            price=float(data.get("price") or data.get("amount") or 0.0),
            network=str(data.get("network") or ""),
            amount=str(data.get("amount_text") or data.get("data") or ""),
        )

