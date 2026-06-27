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

    # -------------------------------------------------------------------------
    # Payments
    # -------------------------------------------------------------------------

    def create_payment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a payment intent.

        Reusing the same `invoice_number` returns the existing payment instead of
        creating a duplicate (HTTP 200 rather than 201), so retries are safe.
        Supply `success_url`/`cancel_url` to return the customer to your site
        after checkout; Fastaar appends `payment_id` (and `invoice_number`) to them.

        Args:
            params: Dictionary containing:
                - amount: int|float|str (required)
                - invoice_number: str (required)
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
                - invoice_number: str (optional)
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

    def find_by_invoice_number(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """
        Find the most recent payment for one of your invoice numbers, or None if none.
        """
        payments = self.list_payments({"invoice_number": invoice_number})
        return payments[0] if payments else None

    def refund_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Refund a completed payment. Only payments with status `completed` can be refunded.

        Returns:
            The updated payment object with status `refunded`.

        Raises:
            FastaarException: if the payment is not in a refundable state.
        """
        encoded_id = urllib.parse.quote(payment_id, safe="")
        result = self._request("POST", f"/api/v1/payments/{encoded_id}/refund")
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    # -------------------------------------------------------------------------
    # Customers
    # -------------------------------------------------------------------------

    def list_customers(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        List customers, newest first.

        Args:
            params: Optional filters — email, phone, per_page, page.
        """
        query = "?" + urllib.parse.urlencode(params) if params else ""
        result = self._request("GET", f"/api/v1/customers{query}")
        if not isinstance(result, list):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def create_customer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a customer.

        Args:
            params: name (required), phone (required), email, address, notes.
        """
        result = self._request("POST", "/api/v1/customers", body=params)
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """Retrieve a customer by ID."""
        result = self._request("GET", f"/api/v1/customers/{customer_id}")
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

    def update_customer(self, customer_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update a customer (partial — only sent fields are changed)."""
        result = self._request("PATCH", f"/api/v1/customers/{customer_id}", body=params)
        if not isinstance(result, dict):
            raise FastaarException("Fastaar API returned an unexpected response format.", "api_error")
        return result

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
                error_message = decoded.get("message")
                error_type = decoded.get("code", "api_error")

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
