from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession # Changed from Session
from sqlalchemy import select # New Import
from backend.database import get_db
from backend.models.user import User
from backend.core.security import create_access_token
from backend.core.config import settings
import httpx # For making HTTP requests to Google's API
from google.oauth2 import id_token
from google.auth.transport import requests as google_auth_requests

router = APIRouter(prefix="/auth/google", tags=["Google Auth"])

# Google OAuth2 Configuration
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
REDIRECT_URI = f"http://localhost:8000/auth/google/callback" # Must match Authorized redirect URIs in Google Cloud Console

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("WARNING: Google Client ID or Secret not set. Google Auth will not work.")

@router.get("/login")
async def google_login():
    """
    Redirects to Google's OAuth consent screen for user authentication.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID not configured.")
        
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        f"response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        "&scope=openid%20email%20profile&access_type=offline&prompt=consent"
    )
    return RedirectResponse(url=auth_url)

from backend.models.wallet import Wallet

@router.get("/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles the redirect from Google after user authentication.
    Exchanges authorization code for tokens, verifies ID token, and logs in/registers user.
    """
    try:
        code = request.query_params.get("code")
        if not code:
            return HTMLResponse("<h1>Google OAuth Callback Error: No authorization code received.</h1>")

        try:
            # Exchange authorization code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    token_url,
                    data={
                        "code": code,
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "redirect_uri": REDIRECT_URI,
                        "grant_type": "authorization_code",
                    },
                )
                token_response.raise_for_status()
                tokens = token_response.json()

            id_token_jwt = tokens.get("id_token")
            if not id_token_jwt:
                return HTMLResponse("<h1>Google OAuth Callback Error: No ID token received.</h1>")

            # Verify the ID token and get user info
            google_id_info = id_token.verify_oauth2_token(
                id_token_jwt, google_auth_requests.Request(), GOOGLE_CLIENT_ID
            )

            google_user_id = google_id_info["sub"]
            email = google_id_info["email"]
            full_name = google_id_info.get("name", email)

            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalars().first()

            if not user:
                # Register new user if not found
                user = User(
                    full_name=full_name,
                    email=email,
                    is_verified=True,
                    google_id=google_user_id
                )
                db.add(user)
                await db.flush() # Get user.id

                # Create default wallet for social login
                wallet = Wallet(user_id=user.id, currency="GHS", balance=0.0)
                db.add(wallet)
                
                await db.commit()
                await db.refresh(user)
            elif not user.google_id:
                # Link Google ID to existing user
                user.google_id = google_user_id
                await db.commit()
                await db.refresh(user)
            
            # Create internal JWT
            access_token = create_access_token(data={"sub": user.email})

            # --- Simplified Kivy Integration: Display JWT for manual copy ---
            # In a real app, this would redirect to a custom URL scheme (e.g., myapp://auth?token=...)
            # or handle session directly. For CLI and "easy access", we display it.
            response_html = f"""
            <html>
            <head>
                <title>Authentication Success</title>
                <style>
                    body {{ font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f4; }}
                    .container {{ background-color: #fff; margin: 0 auto; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 600px; }}
                    h1 {{ color: #4CAF50; }}
                    p {{ color: #333; font-size: 1.1em; }}
                    .token {{ background-color: #e8e8e8; padding: 15px; border-radius: 4px; overflow-wrap: break-word; text-align: left; }}
                    code {{ font-family: monospace; }}
                    .instructions {{ margin-top: 20px; font-size: 0.9em; color: #555; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Authentication Successful!</h1>
                    <p>Your Google account has been linked and you are logged in.</p>
                    <p>Please copy the access token below and paste it into your Kivy application:</p>
                    <div class="token"><code>{access_token}</code></div>
                    <p class="instructions">You can close this browser window/tab now.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=response_html)

        except id_token.exceptions.InvalidIdTokenError:
            return HTMLResponse("<h1>Google OAuth Callback Error: Invalid ID token.</h1>")
        except httpx.HTTPStatusError as e:
            return HTMLResponse(f"<h1>Google OAuth Callback Error: Failed to exchange code for tokens. Status: {e.response.status_code}</h1><p>{e.response.text}</p>")
        except Exception as e:
            return HTMLResponse(f"<h1>Google OAuth Callback Error: An unexpected error occurred.</h1><p>{e}</p>")
    finally:
        await db.close()