
CYBER CASH TECHNOLOGIES LTD
Full stack starter pack:
- Node.js backend
- PostgreSQL schema
- React Native mobile app
- React admin panel

Android / backend status:
- The Android APK build now targets `https://cybercash.space`.
- The repository includes GitHub Actions APK workflows plus Render-style backend manifests (`Procfile`, `render.yaml`).
- Before the mobile app can work on a real Android device, `cybercash.space` must serve the FastAPI backend successfully over HTTPS.
- Health check endpoint: `GET /health`

SMS note:
- Use `TWILIO_MESSAGING_SERVICE_SID` when you have a Twilio Messaging Service and want Twilio to route from approved sender numbers automatically.
- Use `TWILIO_FROM_NUMBER` when you want to send from one specific verified Twilio number.
- The app-level sender label remains `SMS_SENDER_ID=CyberCash`.

Binance (admin-only):
- Configure `BINANCE_API_KEY` + `BINANCE_SECRET_KEY` in `.env` / `backend/.env`.
- Admin endpoints: `GET /admin/binance/health`, `GET /admin/binance/price/BTCUSDT`, `GET /admin/binance/balance/BTC`, `GET /admin/binance/deposit-address/BTC`.
- Withdrawals are disabled by default; enable explicitly with `BINANCE_WITHDRAWALS_ENABLED=true` only after a full security review.
