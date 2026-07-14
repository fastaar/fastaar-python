# Fastaar Python SDK

[![CI](https://github.com/fastaar/fastaar-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fastaar/fastaar-python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fastaar-python.svg)](https://pypi.org/project/fastaar-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Accept bKash & Nagad payments on any Python website or application via [Fastaar](https://fastaar.com).

This is a zero-dependency SDK utilizing Python's standard library.

## Install

Install the package via `pip` (or configure it in your `requirements.txt` / `pyproject.toml`):

```bash
pip install fastaar-python
```

## Create a payment & redirect to checkout

Here is an example using a generic Python web application:

```python
import os
from fastaar import FastaarClient

fastaar = FastaarClient(api_key=os.getenv('FASTAAR_API_KEY'))  # fk_live_... or fk_test_...

# The key must have the `payments:write` ability (and not be expired) or this
# call returns a 403 `ability_denied` / 401 `authentication_error` error.
payment = fastaar.create_payment({
    'amount': 1250,
    'invoice_number': 'ORDER-42',                         # required — your order reference
    'customer_id': customer['id'] if customer else None, # optional — attach an existing customer
    'success_url': 'https://shop.example.com/thanks', # optional, customer returns here
    'cancel_url': 'https://shop.example.com/cart',    # optional
})

# Redirect the customer to checkout
checkout_url = payment['checkout_url']
print(f"Redirecting customer to: {checkout_url}")
```

`invoice_number` is idempotent: if a payment already exists for it and hasn't reached `failed`
or `expired`, creating another one raises a `FastaarException` with error type
`duplicate_invoice_number` (HTTP 409) instead of creating a duplicate — so a dropped connection
never double-charges. Use `find_by_invoice_number()` to look the existing payment up rather than
retrying blindly.

## Confirm the order from a webhook

Verify the signature header to ensure webhook security:

```python
import os
from fastaar import WebhookSignature, FastaarException

# Get raw request body as bytes/string and signature header from request
raw_body = request.body  # must be the raw string or bytes of the request body
signature = request.headers.get('X-Fastaar-Signature', '')

secret = os.getenv('FASTAAR_WEBHOOK_SECRET')

if not WebhookSignature.verify(secret, raw_body, signature):
    # Signature verification failed
    return "Invalid signature", 400

# Parse the event
event = request.json()

if event['event'] == 'payment.completed':
    order_id = event['data']['invoice_number']
    payment_id = event['data']['id']
    # Mark the order as paid idempotently using the payment_id as key
    print(f"Payment completed: {payment_id} for invoice {order_id}")

return "OK", 200
```

## Other payment calls

```python
# Retrieve one payment by its ID (e.g. "01jxyz...")
payment = fastaar.get_payment('01jxyz...')

# Look up most recent payment by your reference
payment = fastaar.find_by_invoice_number('ORDER-42')

# List payments
payments = fastaar.list_payments(params={'status': 'completed'})

# Refund a completed (or partially refunded) payment
payment = fastaar.refund_payment('01jxyz...')          # refund the full remaining balance
payment = fastaar.refund_payment('01jxyz...', 200)     # or refund only part of it
refunds = fastaar.list_refunds('01jxyz...')            # full refund history, newest first
```

## Customers

Store customer records to attach them to payments collected via payment links.

```python
# Create a customer — name and phone are required
customer = fastaar.create_customer({
    'name':    'Rahim Uddin',
    'phone':   '01712345678',
    'email':   'rahim@example.com',   # optional
    'address': 'Dhaka, Bangladesh',   # optional
    'notes':   'VIP customer',        # optional
})

# Retrieve, update, list
customer  = fastaar.get_customer(customer['id'])
customer  = fastaar.update_customer(customer['id'], {'name': 'Rahim Ahmed'})
customers = fastaar.list_customers({'email': 'rahim@example.com'})
```

## Error Handling

Errors raise `fastaar.FastaarException` with `error_type` (e.g. `authentication_error`, `subscription_required`, `transaction_limit_reached`, `connection_error`) and `status_code`.

```python
from fastaar import FastaarException

try:
    payment = fastaar.create_payment({'amount': 100, 'invoice_number': 'ORDER-42'})
except FastaarException as e:
    print(f"API Error: {e}")
    print(f"Type: {e.error_type}")
    print(f"Status Code: {e.status_code}")
```

## Test mode

Use an `fk_test_` key: payments auto-complete on the checkout page without real money, and webhooks fire exactly like production with `"livemode": false`.
