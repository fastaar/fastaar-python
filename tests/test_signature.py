import hashlib
import hmac
import time
import unittest

from fastaar.signature import WebhookSignature


class TestWebhookSignature(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "super-secret-key"
        self.raw_body = '{"event":"payment.completed","data":{"invoice_id":"ORDER-42"}}'
        self.timestamp = int(time.time())

    def _generate_signature(self, secret: str, timestamp: int, body: str) -> str:
        payload = f"{timestamp}.{body}".encode("utf-8")
        h = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
        return f"t={timestamp},v1={h.hexdigest()}"

    def test_verify_valid_signature_string(self) -> None:
        sig = self._generate_signature(self.secret, self.timestamp, self.raw_body)
        self.assertTrue(
            WebhookSignature.verify(self.secret, self.raw_body, sig)
        )

    def test_verify_valid_signature_bytes(self) -> None:
        sig = self._generate_signature(self.secret, self.timestamp, self.raw_body)
        # Verify it works when raw_body is bytes
        self.assertTrue(
            WebhookSignature.verify(self.secret, self.raw_body.encode("utf-8"), sig)
        )
        # Verify it works when secret is bytes
        self.assertTrue(
            WebhookSignature.verify(self.secret.encode("utf-8"), self.raw_body, sig)
        )

    def test_verify_invalid_secret(self) -> None:
        sig = self._generate_signature(self.secret, self.timestamp, self.raw_body)
        self.assertFalse(
            WebhookSignature.verify("wrong-secret", self.raw_body, sig)
        )

    def test_verify_invalid_body(self) -> None:
        sig = self._generate_signature(self.secret, self.timestamp, self.raw_body)
        self.assertFalse(
            WebhookSignature.verify(self.secret, "modified-body", sig)
        )

    def test_verify_expired_timestamp(self) -> None:
        expired_ts = self.timestamp - 301
        sig = self._generate_signature(self.secret, expired_ts, self.raw_body)
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, sig)
        )

    def test_verify_future_timestamp_within_tolerance(self) -> None:
        future_ts = self.timestamp + 100
        sig = self._generate_signature(self.secret, future_ts, self.raw_body)
        self.assertTrue(
            WebhookSignature.verify(self.secret, self.raw_body, sig)
        )

    def test_verify_future_timestamp_outside_tolerance(self) -> None:
        future_ts = self.timestamp + 301
        sig = self._generate_signature(self.secret, future_ts, self.raw_body)
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, sig)
        )

    def test_verify_invalid_signature_format(self) -> None:
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, "invalid-format")
        )
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, f"t={self.timestamp}")
        )
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, "t=abc,v1=abcdef")
        )
        self.assertFalse(
            WebhookSignature.verify(self.secret, self.raw_body, "")
        )
