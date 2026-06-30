# routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from typing import Optional

from app.models.auth import User
from app.database import SessionLocal
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password
from datetime import datetime

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
def login(
    email: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update login status
    now = datetime.utcnow()
    user.is_online = True
    user.last_login = now
    user.last_seen = now

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
            "phone": user.phone,
            "is_online": user.is_online,
            "last_login": user.last_login,
            "last_seen": user.last_seen
        }
    }
# -----------------------
# Google Login
# -----------------------
@router.post("/google-login")
def google_login(
    email: str = Body(...),
    name: str = Body(...),
    db: Session = Depends(get_db)
):

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

    now = datetime.utcnow()

    user.is_online = True
    user.last_login = now
    user.last_seen = now

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
            "phone": user.phone,
            "is_online": user.is_online,
            "last_login": user.last_login,
            "last_seen": user.last_seen
        }
    }
    
@router.post("/logout")
def logout(
    userid: int = Body(...),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.userid == userid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()

    user.is_online = False
    user.last_logout = now
    user.last_seen = now

    db.commit()

    return {
        "message": "Logged out successfully"
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
        "phone": user.phone,
         "status": "Online" if user.is_online else "Offline",

  "last_login": user.last_login.isoformat() + "Z" if user.last_login else None,
        "last_logout": user.last_logout.isoformat() + "Z" if user.last_logout else None,
        "last_seen": user.last_seen.isoformat() + "Z" if user.last_seen else None,
        "registered_at": user.created_at.isoformat() + "Z" if user.created_at else None,
    }
# -----------------------
# Get All Users
# -----------------------
@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()

    return [
        {
            "userid": user.userid,
            "name": user.name,
            "email": user.email,
            "profession": user.profession,
            "phone": user.phone,
            "status": "Online" if user.is_online else "Offline",

            "last_login": user.last_login.isoformat() + "Z" if user.last_login else None,
            "last_logout": user.last_logout.isoformat() + "Z" if user.last_logout else None,
            "last_seen": user.last_seen.isoformat() + "Z" if user.last_seen else None,
            "registered_at": user.created_at.isoformat() + "Z" if user.created_at else None,
        }
        for user in users
    ]
    
@router.put("/update-last-seen")
def update_last_seen(
    userid: int = Body(...),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.userid == userid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.last_seen = datetime.utcnow()

    db.commit()

    return {
        "success": True
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