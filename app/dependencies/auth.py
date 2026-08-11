from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.auth import User
from app.utils.jwt import verify_access_token


security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    print("AUTH HEADER:", credentials)

    token = credentials.credentials

    print("TOKEN:", token)


    payload = verify_access_token(token)

    print("PAYLOAD:", payload)


    user = db.query(User).filter(
        User.userid == payload["user_id"]
    ).first()


    print("USER FOUND:", user)


    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )


    return user