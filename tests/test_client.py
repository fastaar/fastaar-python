import io
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch, MagicMock

from fastaar import FastaarClient, FastaarException


class TestFastaarClient(unittest.TestCase):
    def setUp(self) -> None:
        self.api_key = "fk_test_12345"
        self.client = FastaarClient(api_key=self.api_key)

    def _mock_response(self, status_code: int, body: str) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = status_code
        mock_resp.read.return_value = body.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    @patch("urllib.request.urlopen")
    def test_create_payment_success(self, mock_urlopen: MagicMock) -> None:
        response_data = {
            "data": {
                "id": "pay_01jxyz",
                "status": "pending",
                "amount": 1250,
                "invoice_id": "ORDER-42",
                "checkout_url": "https://fastaar.test/checkout/01jxyz"
            }
        }
        mock_urlopen.return_value = self._mock_response(201, json.dumps(response_data))

        params = {
            "amount": 1250,
            "invoice_id": "ORDER-42",
            "success_url": "https://shop.example.com/thanks"
        }
        payment = self.client.create_payment(params)

        # Verify response matches
        self.assertEqual(payment["id"], "pay_01jxyz")
        self.assertEqual(payment["checkout_url"], "https://fastaar.test/checkout/01jxyz")

        # Verify request parameters
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        self.assertEqual(req.get_full_url(), "https://fastaar.com/api/v1/payments")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.headers["Authorization"], f"Bearer {self.api_key}")
        self.assertEqual(req.headers["Content-type"], "application/json")
        self.assertEqual(req.headers["Accept"], "application/json")
        self.assertEqual(json.loads(req.data.decode("utf-8")), params)

    @patch("urllib.request.urlopen")
    def test_get_payment_success(self, mock_urlopen: MagicMock) -> None:
        response_data = {
            "data": {
                "id": "pay/01jxyz",  # contains a slash to test encoding
                "status": "completed"
            }
        }
        mock_urlopen.return_value = self._mock_response(200, json.dumps(response_data))

        payment = self.client.get_payment("pay/01jxyz")

        self.assertEqual(payment["id"], "pay/01jxyz")
        self.assertEqual(payment["status"], "completed")

        args, _ = mock_urlopen.call_args
        req = args[0]
        # pay/01jxyz should be URL encoded as pay%2F01jxyz
        self.assertEqual(req.get_full_url(), "https://fastaar.com/api/v1/payments/pay%2F01jxyz")
        self.assertEqual(req.method, "GET")

    @patch("urllib.request.urlopen")
    def test_list_payments_success(self, mock_urlopen: MagicMock) -> None:
        response_data = {
            "data": [
                {"id": "1", "status": "completed"},
                {"id": "2", "status": "pending"}
            ]
        }
        mock_urlopen.return_value = self._mock_response(200, json.dumps(response_data))

        payments = self.client.list_payments({"status": "completed", "page": 2})

        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0]["id"], "1")

        args, _ = mock_urlopen.call_args
        req = args[0]
        # Query parameters should be correctly encoded
        self.assertIn("https://fastaar.com/api/v1/payments?", req.get_full_url())
        self.assertIn("status=completed", req.get_full_url())
        self.assertIn("page=2", req.get_full_url())
        self.assertEqual(req.method, "GET")

    @patch("urllib.request.urlopen")
    def test_find_by_invoice_id_found(self, mock_urlopen: MagicMock) -> None:
        response_data = {
            "data": [
                {"id": "pay_01jxyz", "invoice_id": "ORDER-42"}
            ]
        }
        mock_urlopen.return_value = self._mock_response(200, json.dumps(response_data))

        payment = self.client.find_by_invoice_id("ORDER-42")

        self.assertIsNotNone(payment)
        self.assertEqual(payment["id"], "pay_01jxyz")

    @patch("urllib.request.urlopen")
    def test_find_by_invoice_id_not_found(self, mock_urlopen: MagicMock) -> None:
        response_data = {"data": []}
        mock_urlopen.return_value = self._mock_response(200, json.dumps(response_data))

        payment = self.client.find_by_invoice_id("ORDER-42")

        self.assertIsNull = self.assertIsNone(payment)

    @patch("urllib.request.urlopen")
    def test_request_error_400(self, mock_urlopen: MagicMock) -> None:
        error_data = {
            "error": {
                "message": "The amount field is required.",
                "type": "validation_error"
            }
        }
        # Simulate HTTP Error in urlopen
        fp = io.BytesIO(json.dumps(error_data).encode("utf-8"))
        mock_urlopen.side_effect = HTTPError("url", 400, "Bad Request", {}, fp)

        with self.assertRaises(FastaarException) as context:
            self.client.create_payment({})

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.error_type, "validation_error")
        self.assertEqual(str(context.exception), "The amount field is required.")

    @patch("urllib.request.urlopen")
    def test_request_error_generic_500(self, mock_urlopen: MagicMock) -> None:
        # Simulate generic server error without JSON format
        fp = io.BytesIO(b"Internal Server Error")
        mock_urlopen.side_effect = HTTPError("url", 500, "Internal Server Error", {}, fp)

        with self.assertRaises(FastaarException) as context:
            self.client.create_payment({})

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.error_type, "api_error")
        self.assertEqual(str(context.exception), "Fastaar API returned HTTP 500.")

    @patch("urllib.request.urlopen")
    def test_request_connection_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(FastaarException) as context:
            self.client.create_payment({})

        self.assertEqual(context.exception.status_code, 0)
        self.assertEqual(context.exception.error_type, "connection_error")
        self.assertIn("connection refused", str(context.exception))
