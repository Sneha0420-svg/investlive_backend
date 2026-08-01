# app/utils/jwt.py
from datetime import datetime, timedelta
from typing import Optional, Dict

from jose import JWTError
import jwt  # PyJWT library
from fastapi import HTTPException, status

# ---------------- Config ----------------
SECRET_KEY = "investlive"  # Replace with env variable in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# ---------------- Create Token ----------------
def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ---------------- Verify Token ----------------
def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"user_id": user_id}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
# Transfer token expires quickly
TRANSFER_TOKEN_EXPIRE_MINUTES = 2
TRANSFER_SECRET_KEY = "investlive-investvault-transfer"

def create_transfer_token(data: dict):
    payload = data.copy()

    payload["exp"] = datetime.utcnow() + timedelta(minutes=2)

    return jwt.encode(
        payload,
        TRANSFER_SECRET_KEY,
        algorithm=ALGORITHM
    )
    
def verify_transfer_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        return None