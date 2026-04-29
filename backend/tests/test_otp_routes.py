def test_otp_routes_support_send_verify_and_resend(client):
    phone_number = "0247000100"

    send_response = client.post("/otp/send", json={"momo_number": phone_number})
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["message"] == "OTP sent"
    assert send_payload["debug_otp"].isdigit()
    assert len(send_payload["debug_otp"]) == 6

    verify_response = client.post(
        "/otp/verify",
        json={"momo_number": phone_number, "otp": send_payload["debug_otp"]},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["message"] == "OTP verified"

    resend_response = client.post("/otp/resend", json={"momo_number": phone_number})
    assert resend_response.status_code == 200
    resend_payload = resend_response.json()
    assert resend_payload["message"] == "OTP resent"
    assert resend_payload["debug_otp"].isdigit()
    assert len(resend_payload["debug_otp"]) == 6
