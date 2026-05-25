from fastapi import APIRouter, Depends, Request, HTTPException, Cookie
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
import os
from dotenv import load_dotenv
from fastapi import Response

from app.database import SessionLocal
from app.models.auth import User
from app.utils.jwt import create_access_token, decode_token
from app.utils.security import hash_password
from datetime import datetime, timedelta

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# -----------------------
# DB
# -----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------
# OAuth
# -----------------------
oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/calendar",
        "access_type": "offline",   # ✅ REQUIRED for refresh token
        "prompt": "consent",        # ✅ REQUIRED to get refresh token
    },
)
oauth.register(
    name="facebook",
    client_id=os.getenv("FACEBOOK_CLIENT_ID"),
    client_secret=os.getenv("FACEBOOK_CLIENT_SECRET"),
    access_token_url="https://graph.facebook.com/v17.0/oauth/access_token",
    authorize_url="https://www.facebook.com/v17.0/dialog/oauth",
    api_base_url="https://graph.facebook.com/",
)
oauth.register(
    name="twitter",
    client_id=os.getenv("TWITTER_CLIENT_ID"),
    client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
    authorize_url="https://twitter.com/i/oauth2/authorize",
    access_token_url="https://api.twitter.com/2/oauth2/token",
    client_kwargs={
        "scope": "tweet.read users.read offline.access",
    },
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

## =========================
# GOOGLE LOGIN
# =========================
@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = "http://localhost:8000/auth/google/callback"

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        access_type="offline",   # ✅ REQUIRED
        prompt="consent"         # ✅ REQUIRED
    )


# =========================
# GOOGLE CALLBACK
# =========================
@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)

    print("TOKEN RESPONSE:", token)  # 🔍 DEBUG

    user_info = token.get("userinfo")

    email = user_info["email"]
    name = user_info["name"]

    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password("oauth_user")
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # ✅ STORE TOKENS
    user.google_access_token = token.get("access_token")

    if token.get("refresh_token"):
        user.google_refresh_token = token.get("refresh_token")

    # ✅ STORE EXPIRY
    if token.get("expires_in"):
        user.google_token_expiry = datetime.utcnow() + timedelta(seconds=token["expires_in"])

    db.commit()

    # ✅ JWT
    jwt_token = create_access_token({"sub": str(user.userid)})

    response = RedirectResponse(url=f"{FRONTEND_URL}/")
    response.set_cookie(
    key="access_token",
    value=jwt_token,
    httponly=True,
    secure=False,      # localhost only
    samesite="lax",
    path="/"
)

    return response

# ======================================================
# FACEBOOK
# ======================================================
@router.get("/facebook/login")
async def facebook_login(request: Request):
    redirect_uri = "http://localhost:8000/auth/facebook/callback"

    return await oauth.facebook.authorize_redirect(
        request,
        redirect_uri,
        scope=["public_profile", "email"]
    )


@router.get("/facebook/callback")
async def facebook_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.facebook.authorize_access_token(request)

    resp = await oauth.facebook.get(
        "me?fields=id,name,email",
        token=token
    )

    user_info = resp.json()

    email = user_info.get("email")
    name = user_info.get("name")

    if not email:
        raise HTTPException(400, "Facebook did not return email")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password("oauth_user")
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token({"sub": str(user.userid)})

    response = RedirectResponse(url=f"{FRONTEND_URL}/")

    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    return response

# ======================================================
# TWITTER
# ======================================================
@router.get("/twitter/login")
async def twitter_login(request: Request):
    redirect_uri = "http://127.0.0.1:8000/auth/twitter/callback"

    return await oauth.twitter.authorize_redirect(
        request,
        redirect_uri,
        code_challenge_method="S256"
    )


@router.get("/twitter/callback")
async def twitter_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.twitter.authorize_access_token(request)

    # ✅ Twitter OAuth2 already includes user info in token response (depending on scope)
    user_info = token.get("userinfo") or {}

    twitter_id = user_info.get("sub") or user_info.get("id")

    if not twitter_id:
        # fallback: use token identity if userinfo not present
        twitter_id = token.get("user_id") or "unknown"

    name = user_info.get("name") or "Twitter User"

    # Twitter does NOT reliably provide email
    email = f"{twitter_id}@twitter.com"

    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password("oauth_user")
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token({"sub": str(user.userid)})

    response = RedirectResponse(url="http://127.0.0.1:3000/")

    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/"
    )

    return response
# ======================================================
# GET CURRENT USER (REAL AUTH)
# ======================================================
@router.get("/me")
def get_current_user(
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not access_token:
        raise HTTPException(401, "Not authenticated")

    payload = decode_token(access_token)
    user_id = payload.get("sub")

    user = db.query(User).filter(User.userid == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    return {
        "userid": user.userid,
        "name": user.name,
        "email": user.email,
        "profession": user.profession,
        "phone": user.phone
    }
# ======================================================
# USER API
# ======================================================
@router.get("/user/{userid}")
def get_user(userid: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.userid == userid).first()

    if not user:
        raise HTTPException(404, "User not found")

    return {
        "userid": user.userid,
        "name": user.name,
        "email": user.email,
        "profession": user.profession,
        "phone": user.phone
    }
    
@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=False
    )
    return {"message": "Logged out successfully"}