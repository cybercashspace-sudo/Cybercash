import unittest

from core.message_sanitizer import (
    GENERIC_SERVER_MESSAGE,
    extract_backend_message,
    sanitize_backend_message,
)


class TestMessageSanitizer(unittest.TestCase):
    def test_redacts_debug_otp_text(self):
        self.assertEqual(
            sanitize_backend_message("Test OTP: 123456"),
            GENERIC_SERVER_MESSAGE,
        )
        self.assertEqual(
            sanitize_backend_message("debug otp 654321"),
            GENERIC_SERVER_MESSAGE,
        )

    def test_extract_backend_message_redacts_debug_otp_detail(self):
        payload = {"detail": "Test OTP: 123456"}
        self.assertEqual(extract_backend_message(payload), GENERIC_SERVER_MESSAGE)


if __name__ == "__main__":
    unittest.main()
