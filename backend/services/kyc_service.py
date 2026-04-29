from dataclasses import dataclass
from typing import Dict


def extract_ghana_card_data(image):
    # Placeholder OCR adapter. Replace with Tesseract/SmileID/Prembly provider implementation.
    text = str(image or "")
    return parse_ghana_fields(text)


def parse_ghana_fields(text: str) -> Dict[str, str]:
    # Minimal parser scaffold for production integration.
    return {
        "full_name": "",
        "date_of_birth": "",
        "ghana_card_number": "",
        "expiry_date": "",
        "raw_text": text,
    }


def face_match(id_photo, selfie):
    # Placeholder face match adapter. Replace with AWS Rekognition / Azure Face / Face++.
    # Return list-like compatible shape used by many provider SDKs.
    return [{"Similarity": 0.0}] if id_photo and selfie else []


@dataclass
class KYCResult:
    ghana_card_number: str
    full_name: str
    date_of_birth: str
    expiry_date: str
    face_match_score: float
    kyc_status: str


def process_agent_kyc(ghana_card_front_ref: str, ghana_card_back_ref: str, selfie_ref: str) -> KYCResult:
    front_data = extract_ghana_card_data(ghana_card_front_ref)
    back_data = extract_ghana_card_data(ghana_card_back_ref)
    card_number = front_data.get("ghana_card_number") or back_data.get("ghana_card_number") or ""
    full_name = front_data.get("full_name") or back_data.get("full_name") or ""
    dob = front_data.get("date_of_birth") or back_data.get("date_of_birth") or ""
    expiry = front_data.get("expiry_date") or back_data.get("expiry_date") or ""

    matches = face_match(ghana_card_front_ref, selfie_ref)
    score = float(matches[0].get("Similarity", 0.0)) if matches else 0.0
    status = "pending_admin_review" if score >= 90.0 else "failed_face_match"
    return KYCResult(
        ghana_card_number=card_number,
        full_name=full_name,
        date_of_birth=dob,
        expiry_date=expiry,
        face_match_score=score,
        kyc_status=status,
    )

