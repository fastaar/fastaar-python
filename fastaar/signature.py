import hashlib
import hmac
import re
import time
from typing import Union


class WebhookSignature:
    @staticmethod
    def verify(
        secret: Union[str, bytes],
        raw_body: Union[str, bytes],
        signature_header: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verify the X-Fastaar-Signature header (`t=<ts>,v1=<hmac>`) against
        the raw request body using your merchant webhook secret.
        """
        if not signature_header or not secret:
            return False

        # Match signature header pattern: t=<timestamp>,v1=<hmac-sha256>
        match = re.match(r"^t=(?P<t>\d+),v1=(?P<v1>[a-f0-9]{64})$", signature_header)
        if not match:
            return False

        try:
            timestamp = int(match.group("t"))
        except ValueError:
            return False

        # Check timestamp tolerance
        current_time = int(time.time())
        if abs(current_time - timestamp) > tolerance_seconds:
            return False

        # Ensure raw_body is a string
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8")

        # Prepare secret and message payload
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        payload_bytes = f"{timestamp}.{raw_body}".encode("utf-8")

        # Generate expected signature
        expected = hmac.new(
            secret_bytes,
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, match.group("v1"))
