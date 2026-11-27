# CyberCash Agent Checkout API

Approved Agents can generate API keys from **Agent Dashboard → API**. API access has no CyberCash subscription fee; Paystack or other payment-provider fees can still apply.

API keys are secrets. Use them only from a trusted server you control. Do not put a key in a browser, mobile app, public source repository, or customer-visible page. CyberCash stores only a one-way hash and shows the full key once. Revoke a key immediately if it may have been exposed.

## Create a customer checkout

Send a server-to-server request to:

```text
POST https://<your-cybercash-backend>/agent-api/v1/payments/checkout
X-CyberCash-API-Key: <agent-api-key>
Idempotency-Key: <unique-order-id>
Content-Type: application/json
```

```json
{
  "amount": "25.50",
  "customer_email": "buyer@example.com"
}
```

Amounts are in GHS, from GHS 1.00 to GHS 10,000.00, with up to two decimal places. Open the returned `authorization_url` for the customer to pay. The endpoint creates a pending checkout only; it does not credit a wallet from a client-supplied success response. CyberCash credits the Agent wallet after Paystack confirms the payment through its verified confirmation flow.

Example response:

```json
{
  "status": "pending",
  "reference": "provider-reference",
  "authorization_url": "https://checkout.paystack.com/...",
  "amount": "25.50",
  "currency": "GHS"
}
```

Use a stable, unique `Idempotency-Key` for each order and reuse it for retries of that same order. Reusing it with a different amount or customer email returns a conflict instead of creating another checkout.

## Check payment status

```text
GET https://<your-cybercash-backend>/agent-api/v1/payments/<reference>
X-CyberCash-API-Key: <agent-api-key>
```

The response contains the reference, amount, currency, and current state (`pending`, `completed`, or `failed`). Only the API key that created that checkout can query it. A payment is final only when its state is `completed`.

An Agent can have up to five active keys. Key creation and revocation are available in the signed-in app; creating a key requires an approved active Agent account.
