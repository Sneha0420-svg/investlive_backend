from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from typing import Optional

from app.models.auth import User
from app.database import SessionLocal
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password

# -----------------------
# DB Dependency
# -----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------
# Auth Router
# -----------------------
router = APIRouter(prefix="/auth", tags=["auth"])

# -----------------------
# Registration
# -----------------------
@router.post("/register")
def register(
    name: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    profession: Optional[str] = Body(None),
    phone:str= Body(...),  # <-- phone optional
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        profession=profession,
        phone=phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully"}

# -----------------------
# Login
# -----------------------
@router.post("/login")
def login(email: str = Body(...), password: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.userid)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "userid": user.userid,
            "name": user.name,
            "email": user.email,
            "profession": user.profession,
            "phone": user.phone
        }
    }

# -----------------------
# Google Login
# -----------------------
@router.post("/google-login")
def google_login(email: str = Body(...), name: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        random_password = str(random.randint(100000, 999999))
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(random_password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.userid)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "userid": user.userid,
            "name": user.name,
            "email": user.email,
            "profession": user.profession,
            "phone": user.phone
        }
    }

# -----------------------
# Get User by userid
# -----------------------
@router.get("/user/{userid}")
def get_user(userid: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.userid == userid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "userid": user.userid,
        "name": user.name,
        "email": user.email,
        "profession": user.profession,
        "phone": user.phone
    }

# -----------------------
# Forgot Password
# -----------------------
@router.put("/forgot-password")
def forgot_password(
    email: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)

    return {
        "message": "Password updated successfully",
        "user": {
            "userid": user.userid,
            "email": user.email,
            "phone":user.phone
        }
    }