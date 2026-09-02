from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from backend.core.config import settings
from backend.models import Transaction, User, VirtualCard


def _resolve_public_base_url() -> str:
    candidates = (
        getattr(settings, "BACKEND_URL", ""),
        os.getenv("BACKEND_URL", ""),
        os.getenv("PUBLIC_BACKEND_URL", ""),
    )
    for value in candidates:
        cleaned = str(value or "").strip().rstrip("/")
        if cleaned:
            if "://" not in cleaned:
                cleaned = f"https://{cleaned}"
            return cleaned
    env = str(getattr(settings, "ENV", "development") or "development").strip().lower()
    if env in {"prod", "production", "live"}:
        return "https://api.cybercash.space"
    if env in {"stage", "staging"}:
        return "https://staging-api.cybercash.space"
    return "http://localhost:8000"


class StatementService:
    """Generate PDF statements for virtual cards."""

    def __init__(self, static_dir: str | None = None, base_url: str | None = None):
        project_root = Path(__file__).resolve().parents[2]
        self.static_dir = str(static_dir or (project_root / "static" / "statements"))
        self.base_url = str(base_url or _resolve_public_base_url()).rstrip("/")

        Path(self.static_dir).mkdir(parents=True, exist_ok=True)

    def cleanup_old_statements(self, max_age_hours: int = 48):
        now = time.time()
        for filename in os.listdir(self.static_dir):
            file_path = os.path.join(self.static_dir, filename)
            if not os.path.isfile(file_path):
                continue
            file_age = now - os.path.getmtime(file_path)
            if file_age > (max_age_hours * 3600):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def generate_pdf(self, user: User, card: VirtualCard, transactions: list[Transaction]) -> str:
        self.cleanup_old_statements(max_age_hours=48)
        pdf = FPDF()
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(7, 19, 42)
        pdf.cell(0, 15, "CYBER CASH", ln=True, align="L")

        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "Virtual Card Transaction Statement", ln=True, align="L")
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(100, 7, f"Account Holder: {user.full_name or 'Valued Customer'}", ln=False)
        pdf.cell(0, 7, "Period: Last 30 Days", ln=True, align="R")

        card_num = getattr(card, "card_number", "0000000000000000")
        masked_num = f"XXXX XXXX XXXX {card_num[-4:]}" if len(card_num) >= 4 else "N/A"
        pdf.cell(100, 7, f"Card Number: {masked_num}", ln=False)
        pdf.cell(0, 7, f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", ln=True, align="R")
        pdf.ln(10)

        pdf.set_fill_color(231, 201, 110)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 10, "Date", 1, 0, "C", True)
        pdf.cell(90, 10, "Merchant / Description", 1, 0, "C", True)
        pdf.cell(30, 10, "Status", 1, 0, "C", True)
        pdf.cell(35, 10, "Amount (USD)", 1, 1, "C", True)

        pdf.set_font("Helvetica", "", 9)
        for tx in transactions:
            date_str = tx.timestamp.strftime("%Y-%m-%d") if getattr(tx, "timestamp", None) else "N/A"
            meta = {}
            if getattr(tx, "metadata_json", ""):
                try:
                    meta = json.loads(tx.metadata_json)
                except Exception:
                    meta = {}
            desc = meta.get("merchant", tx.type.replace("card_", "").title() if tx.type else "Transaction")
            status = (tx.status or "Completed").title()

            pdf.cell(35, 8, date_str, 1, 0, "C")
            pdf.cell(90, 8, f" {str(desc)[:45]}", 1, 0, "L")
            pdf.cell(30, 8, status, 1, 0, "C")

            amount = float(tx.amount or 0.0)
            pdf.cell(35, 8, f"{amount:,.2f} ", 1, 1, "R")

        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 10, "Cyber Cash Technologies Ltd - Enterprise Fintech Solutions", ln=True, align="C")

        file_name = f"stmt_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        file_path = os.path.join(self.static_dir, file_name)
        pdf.output(file_path)

        return f"{self.base_url}/static/statements/{file_name}"
