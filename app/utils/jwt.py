# app/utils/jwt.py

from datetime import datetime, timedelta
from typing import Optional, Dict

import jwt

from jose import JWTError

from fastapi import (
    HTTPException,
    status
)


# ==========================
# JWT CONFIG
# ==========================

SECRET_KEY = "a8f7d9e3c5b1f6a9d2e4f8c7b6a1e9d4f5c8b2a7e6d3f1c9"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


# ==========================
# CREATE ACCESS TOKEN
# ==========================

def create_access_token(
    data: Dict,
    expires_delta: Optional[timedelta] = None
):

    payload = data.copy()


    expire = (
        datetime.utcnow()
        +
        (
            expires_delta
            or timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )
    )


    payload.update(
        {
            "exp": expire
        }
    )


    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


    return token



# ==========================
# VERIFY ACCESS TOKEN
# ==========================

def verify_access_token(token: str):

    try:

        print("VERIFY TOKEN START")

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )

        print("DECODED PAYLOAD:", payload)


        user_id = payload.get("sub")


        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="sub missing"
            )


        return {
            "user_id": int(user_id)
        }


    except jwt.ExpiredSignatureError as e:

        print("TOKEN EXPIRED:", e)

        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )


    except jwt.InvalidSignatureError as e:

        print("INVALID SIGNATURE:", e)

        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )


    except Exception as e:

        print("JWT ERROR:", type(e), str(e))

        raise HTTPException(
            status_code=401,
            detail="JWT failed"
        )

# ==========================
# TRANSFER TOKEN
# ==========================

TRANSFER_SECRET_KEY = (
    "investlive-investvault-transfer"
)


TRANSFER_TOKEN_EXPIRE_MINUTES = 2



def create_transfer_token(
    data: dict
):

    payload = data.copy()


    payload["exp"] = (

        datetime.utcnow()

        +
        timedelta(
            minutes=
            TRANSFER_TOKEN_EXPIRE_MINUTES
        )

    )


    return jwt.encode(

        payload,

        TRANSFER_SECRET_KEY,

        algorithm=ALGORITHM

    )



def verify_transfer_token(
    token: str
):

    try:

        payload = jwt.decode(

            token,

            TRANSFER_SECRET_KEY,

            algorithms=[
                ALGORITHM
            ]

        )


        return payload



    except JWTError:

        return None
    
