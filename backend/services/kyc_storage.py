from __future__ import annotations

import base64
import hashlib
import io
import json

from cryptography.fernet import Fernet, InvalidToken
from PIL import Image, ImageOps

from backend.core.config import settings


MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_IMAGE_EDGE = 1800


def _fernet() -> Fernet:
    configured_key = str(settings.KYC_ENCRYPTION_KEY or "").strip()
    if configured_key:
        try:
            return Fernet(configured_key.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("KYC encryption is not configured.") from exc
    secret = str(settings.SECRET_KEY or "").strip()
    if len(secret) < 16:
        raise RuntimeError("KYC encryption is not configured.")
    key = base64.urlsafe_b64encode(hashlib.sha256((secret + ":cybercash-kyc-v1").encode("utf-8")).digest())
    return Fernet(key)


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    try:
        return _fernet().decrypt(str(value).encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise RuntimeError("Stored KYC data could not be decrypted.") from exc


def encrypt_identity(full_name: str, date_of_birth: str, ghana_card_number: str) -> str:
    payload = json.dumps(
        {
            "full_name": full_name,
            "date_of_birth": date_of_birth,
            "ghana_card_number": ghana_card_number,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return encrypt_text(payload)


def decrypt_identity(value: str) -> dict[str, str]:
    result = json.loads(decrypt_text(value))
    if not isinstance(result, dict):
        raise RuntimeError("Stored KYC data is invalid.")
    return {key: str(result.get(key, "")) for key in ("full_name", "date_of_birth", "ghana_card_number")}


def normalize_image(raw: bytes) -> tuple[bytes, str]:
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Each photo must be smaller than 4 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Upload a JPG, PNG, or WebP image.")
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            return output.getvalue(), "image/jpeg"
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The photo dimensions are too large. Choose a smaller image.") from exc
    except (OSError, SyntaxError) as exc:
        raise ValueError("One of the selected files is not a valid image.") from exc


def encrypt_image(raw: bytes) -> str:
    return _fernet().encrypt(raw).decode("ascii")


def decrypt_image(value: str) -> bytes:
    try:
        return _fernet().decrypt(str(value).encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Stored KYC photo could not be decrypted.") from exc


def image_data_url(raw: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
