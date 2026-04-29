from api.client import api_client


def register(momo: str, email: str, pin: str, agent_mode: bool, first_name: str = ""):
    return api_client.post("/auth/register", {
        "momo_number": momo,
        "email": email,
        "pin": pin,
        "is_agent": bool(agent_mode),
        "first_name": str(first_name or "").strip() or "Customer",
    })


def access_account(
    momo: str,
    pin: str,
    is_agent: bool,
    first_name: str = "",
    device_id: str = "",
    device_fingerprint: str = "",
):
    payload = {
        "momo_number": momo,
        "pin": pin,
        "is_agent": bool(is_agent),
        "first_name": str(first_name or "").strip() or "Customer",
        "device_id": device_id or None,
        "device_fingerprint": device_fingerprint or None,
    }
    return api_client.post("/auth/access", payload)


def lookup_registered_name(momo: str):
    return api_client.post("/auth/lookup-name", {"momo_number": momo})


def logout(access_token: str):
    token = str(access_token or "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return api_client.post("/auth/logout", {}, headers=headers)


def verify_account(momo: str, otp: str):
    return api_client.post("/auth/verify", {
        "momo_number": momo,
        "otp": otp,
    })


def resend_otp(momo: str):
    return api_client.post("/auth/resend-otp", {
        "momo_number": momo
    })
