# Fastaar Python SDK

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

payment = fastaar.create_payment({
    'amount': 1250,
    'invoice_id': 'ORDER-42',                         # your order reference
    'success_url': 'https://shop.example.com/thanks', # optional, customer returns here
    'cancel_url': 'https://shop.example.com/cart',    # optional
})

# Redirect the customer to checkout
checkout_url = payment['checkout_url']
print(f"Redirecting customer to: {checkout_url}")
```

Passing the same `invoice_id` again returns the existing payment instead of creating a duplicate, so a retried request never double-charges.

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
    order_id = event['data']['invoice_id']
    payment_id = event['data']['id']
    # Mark the order as paid idempotently using the payment_id as key
    print(f"Payment completed: {payment_id} for invoice {order_id}")

return "OK", 200
```

## Other calls

```python
# Retrieve one payment by its ID (e.g. "01jxyz...")
payment = fastaar.get_payment('01jxyz...')

# Look up most recent payment by your reference/invoice ID
payment = fastaar.find_by_invoice_id('ORDER-42')

# List payments
payments = fastaar.list_payments(params={'status': 'completed'})
```

## Error Handling

Errors raise `fastaar.FastaarException` with `error_type` (e.g. `authentication_error`, `subscription_required`, `transaction_limit_reached`, `connection_error`) and `status_code`.

```python
from fastaar import FastaarException

try:
    payment = fastaar.create_payment({'amount': 100})
except FastaarException as e:
    print(f"API Error: {e}")
    print(f"Type: {e.error_type}")
    print(f"Status Code: {e.status_code}")
```

## Test mode

Use an `fk_test_` key: payments auto-complete on the checkout page without real money, and webhooks fire exactly like production with `"livemode": false`.
