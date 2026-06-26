import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional, Union

from fastaar.exceptions import FastaarException

BASE_URL = "https://fastaar.com"


class FastaarClient:
    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 15,
    ) -> None:
        """
        Initialize the Fastaar client.

        Args:
            api_key: Your Fastaar API key (e.g. fk_live_... or fk_test_...)
            timeout_seconds: Connection and read timeout in seconds
        """
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def create_payment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a payment intent.

        Reusing the same `invoice_id` returns the existing payment instead of
        creating a duplicate (HTTP 200 rather than 201), so retries are safe.
        Supply `success_url`/`cancel_url` to return the customer to your site
        after checkout; Fastaar appends `payment_id` (and `invoice_id`) to them.

        Args:
            params: Dictionary containing:
                - amount: int|float|str (required)
                - invoice_id: str (optional)
                - success_url: str (optional)
                - cancel_url: str (optional)
                - metadata: dict (optional)

        Returns:
            The payment object dictionary, including `id`, `status`, and `checkout_url`.
        """
        result = self._request("POST", "/api/v1/payments", body=params)
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Retrieve a payment by its reference (the `id` returned at creation).
        """
        encoded_id = urllib.parse.quote(payment_id, safe="")
        result = self._request("GET", f"/api/v1/payments/{encoded_id}")
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def list_payments(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        List payments, newest first.

        Args:
            params: Dictionary containing optional filters:
                - status: str (optional)
                - invoice_id: str (optional)
                - per_page: int (optional)
                - page: int (optional)
        """
        if params:
            query = "?" + urllib.parse.urlencode(params)
        else:
            query = ""

        result = self._request("GET", f"/api/v1/payments{query}")
        if not isinstance(result, list):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def find_by_invoice_id(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the most recent payment for one of your invoice IDs, or None if none.
        """
        payments = self.list_payments({"invoice_id": invoice_id})
        return payments[0] if payments else None

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        url = BASE_URL + path

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
        except HTTPError as e:
            status_code = e.code
            try:
                response_body = e.read().decode("utf-8")
            except Exception:
                response_body = ""
        except (URLError, Exception) as e:
            # Check if reason is present
            reason = getattr(e, "reason", str(e))
            raise FastaarException(
                message=f"Could not reach the Fastaar API: {reason}",
                error_type="connection_error",
                status_code=0,
            )

        try:
            decoded = json.loads(response_body)
        except json.JSONDecodeError:
            decoded = None

        if status_code >= 400 or not isinstance(decoded, (dict, list)):
            error_message = None
            error_type = "api_error"

            if isinstance(decoded, dict):
                error_info = decoded.get("error")
                if isinstance(error_info, dict):
                    error_message = error_info.get("message")
                    error_type = error_info.get("type", "api_error")

            if not error_message:
                error_message = f"Fastaar API returned HTTP {status_code}."

            raise FastaarException(
                message=error_message,
                error_type=error_type,
                status_code=status_code,
            )

        # In case Fastaar envelopes data, return decoded['data'] if it exists, otherwise full decoded
        if isinstance(decoded, dict) and "data" in decoded:
            return decoded["data"]
        return decoded
