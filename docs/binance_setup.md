# Binance API connection

The app's Binance integration runs in the backend. Public BTC prices do not need a Binance key. The key is used only for the admin-only account and BTC dashboard endpoints.

## Create a restricted API key

In Binance API Management, create a dedicated key for this backend. Enable read access needed to view the Spot account. Keep trading, withdrawals, margin, futures, and transfers disabled. If the Binance account allows IP restrictions and the backend has stable outbound IP addresses, allowlist those addresses.

Never put the secret in the Android app, a source file, a support message, or a repository. If a key is exposed, revoke it in Binance and create a replacement.

## Add the key to Render

Open the backend web service in Render and add these environment variables under its private Environment settings:

| Name | Value |
| --- | --- |
| `BINANCE_API_KEY` | Binance API key |
| `BINANCE_SECRET_KEY` | Matching Binance secret |
| `BINANCE_WITHDRAWALS_ENABLED` | `false` |

Save the settings and let Render redeploy the backend. Do not add these variables to the Android app or commit them in an environment file. The Render Blueprint already declares the two credentials as unsynced secrets and keeps withdrawals disabled.

## Verify the connection

Sign in with an admin account and request `GET /admin/binance/health` on the deployed backend. A successful read-only signed request returns `configured: true` and `connected: true`. If the key is absent, rejected, or lacks read access, the response gives a safe setup hint without returning Binance account data or credentials. The BTC admin dashboard also reads the live BTC/USDT market price and, when the key is valid, the configured account's BTC balance and deposit address.

The normal user BTC market-price feed is public and does not depend on this private key. Linking this API does not enable BTC trading or create per-user blockchain deposit addresses; withdrawals remain disabled by default.
