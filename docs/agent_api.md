# CyberCash Agent Checkout API

Approved, active Agents can manage API credentials from **Agent Dashboard → API**. Creating a key has no CyberCash subscription fee; payment-provider fees can still apply to live Paystack transactions.

## Keys and environments

Choose **Test mode** while integrating and **Live mode** only when ready to accept real payments. A generated secret is shown once, then only its prefix is listed. Store it in a server-side environment variable; never embed it in a browser, mobile app, public repository, or customer-visible page. Revoke it if exposed.

Each secret is paired with a `cc_pub_...` public ID. The public ID identifies the integration only; it grants no access and cannot authenticate API calls or receive money. Checkout requires the matching secret in `X-CyberCash-API-Key`.

Test keys create idempotent simulated checkout records with `CC-TEST-...` references. They never contact Paystack, create a payment URL, or credit a wallet. Test responses have `status: "test"` and `authorization_url: null`. Use this mode to verify your server integration without moving funds.

Live keys start real Paystack checkouts. A wallet is credited only after CyberCash verifies Paystack's payment confirmation. Keep live secrets on a trusted server.

## Create a checkout

Send a server-to-server request to:

```text
POST https://<your-cybercash-backend>/agent-api/v1/payments/checkout
X-CyberCash-API-Key: <agent-api-secret>
Idempotency-Key: <unique-order-id>
Content-Type: application/json
```

```json
{
  "amount": "25.50",
  "customer_email": "buyer@example.com"
}
```

Amounts are in GHS from 1.00 to 10,000.00, with up to two decimal places. For live keys, open the returned `authorization_url` so the customer can pay. For test keys, the response is simulated and has no payment URL.

Use a stable, unique `Idempotency-Key` for each order and reuse it for retries of that order. Reusing it with a different amount or customer email returns a conflict rather than creating another checkout.

Live response example:

```json
{
  "status": "pending",
  "reference": "provider-reference",
  "authorization_url": "https://checkout.paystack.com/...",
  "amount": "25.50",
  "currency": "GHS"
}
```

Test response example:

```json
{
  "status": "test",
  "reference": "CC-TEST-example",
  "authorization_url": null,
  "amount": "25.50",
  "currency": "GHS"
}
```

## Check status

```text
GET https://<your-cybercash-backend>/agent-api/v1/payments/<reference>
X-CyberCash-API-Key: <agent-api-secret>
```

The response includes the reference, status, amount, currency, and environment. Only the key that created a checkout can query it. Live payment is final only when the status is `completed`; a test checkout remains `test` and never represents a real payment.

An Agent can have up to five active keys across both environments. Creating or revoking a key requires a verified, active account and an approved, active Agent profile.
