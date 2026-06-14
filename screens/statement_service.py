import os
import json
import time
from datetime import datetime
from fpdf import FPDF
from backend.models import Transaction, VirtualCard, User

class StatementService:
    """Service to handle generation of PDF statements for Virtual Cards."""
    
    def __init__(self, static_dir: str = "static/statements", base_url: str = None):
        # In production, base_url should come from your settings/env
        from backend.core.config import settings
        self.static_dir = static_dir
        self.base_url = base_url or getattr(settings, "BACKEND_URL", "http://localhost:8000")
        
        if not os.path.exists(self.static_dir):
            os.makedirs(self.static_dir, exist_ok=True)

    def cleanup_old_statements(self, max_age_hours: int = 48):
        """Deletes statement files older than the specified hours."""
        now = time.time()
        for filename in os.listdir(self.static_dir):
            file_path = os.path.join(self.static_dir, filename)
            if os.path.isfile(file_path):
                # Check file modification time
                file_age = now - os.path.getmtime(file_path)
                if file_age > (max_age_hours * 3600):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

    def generate_pdf(self, user: User, card: VirtualCard, transactions: list[Transaction]) -> str:
        """Generates a PDF and returns the reachable public URL."""
        self.cleanup_old_statements(max_age_hours=48)
        pdf = FPDF()
        pdf.add_page()
        
        # Branding & Title
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(7, 19, 42) # Card Blue: 0.07, 0.19, 0.42
        pdf.cell(0, 15, "CYBER CASH", ln=True, align="L")
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "Virtual Card Transaction Statement", ln=True, align="L")
        pdf.ln(5)
        
        # Info Header
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(100, 7, f"Account Holder: {user.full_name or 'Valued Customer'}", ln=False)
        pdf.cell(0, 7, f"Period: Last 30 Days", ln=True, align="R")
        
        card_num = getattr(card, 'card_number', "0000000000000000")
        masked_num = f"XXXX XXXX XXXX {card_num[-4:]}" if len(card_num) >= 4 else "N/A"
        pdf.cell(100, 7, f"Card Number: {masked_num}", ln=False)
        pdf.cell(0, 7, f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", ln=True, align="R")
        pdf.ln(10)
        
        # Table Header
        pdf.set_fill_color(231, 201, 110) # #E7C96E (Gold)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 10, "Date", 1, 0, "C", True)
        pdf.cell(90, 10, "Merchant / Description", 1, 0, "C", True)
        pdf.cell(30, 10, "Status", 1, 0, "C", True)
        pdf.cell(35, 10, "Amount (USD)", 1, 1, "C", True)
        
        # Table Content
        pdf.set_font("Helvetica", "", 9)
        for tx in transactions:
            date_str = tx.timestamp.strftime("%Y-%m-%d") if hasattr(tx, 'timestamp') and tx.timestamp else "N/A"
            
            meta = {}
            if tx.metadata_json:
                try:
                    meta = json.loads(tx.metadata_json)
                except:
                    pass
            desc = meta.get("merchant", tx.type.replace("card_", "").title() if tx.type else "Transaction")
            status = (tx.status or "Completed").title()
            
            pdf.cell(35, 8, date_str, 1, 0, "C")
            pdf.cell(90, 8, f" {desc[:45]}", 1, 0, "L")
            pdf.cell(30, 8, status, 1, 0, "C")
            
            amount = float(tx.amount or 0.0)
            pdf.cell(35, 8, f"{amount:,.2f} ", 1, 1, "R")

        # Footer
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 10, "Cyber Cash Technologies Ltd - Enterprise Fintech Solutions", ln=True, align="C")

        file_name = f"stmt_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        file_path = os.path.join(self.static_dir, file_name)
        pdf.output(file_path)
        
        return f"{self.base_url}/static/statements/{file_name}"