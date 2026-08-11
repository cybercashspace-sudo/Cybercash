from __future__ import annotations


def filter_transactions(items, tx_type: str = "all", query: str = ""):
    tx_type = str(tx_type or "all").strip().lower()
    query = str(query or "").strip().lower()
    rows = [item for item in (items or []) if isinstance(item, dict)]

    if tx_type not in {"all", ""}:
        rows = [item for item in rows if str(item.get("type") or "").strip().lower() == tx_type]

    if query:
        def matches(item: dict) -> bool:
            haystack = " ".join(
                str(item.get(key, "") or "").lower()
                for key in ("title", "type", "description", "reference", "status", "created_at")
            )
            return query in haystack

        rows = [item for item in rows if matches(item)]

    return rows
