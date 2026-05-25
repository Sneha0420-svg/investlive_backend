# =========================================================
# GOOGLE CALENDAR ROUTES
# =========================================================

import os
import asyncio
import requests
import httpx

from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.auth import User
from app.models.google_events import GoogleEvent
from app.models.ipoevents import CalendarEvents

from app.utils.jwt import decode_token
from app.utils.google_auth import get_valid_google_token

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"]
)

# =========================================================
# DB
# =========================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
# AUTH
# =========================================================

def get_user_from_token(request: Request, db: Session):

    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing token"
        )

    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = db.query(User).filter(
        User.userid == int(payload["sub"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user

# =========================================================
# REFRESH TOKEN
# =========================================================

def refresh_google_token(user: User):

    if not user.google_refresh_token:
        return None

    try:

        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10
        )

        if res.status_code != 200:
            return None

        data = res.json()

        return data.get("access_token")

    except Exception:
        return None

# =========================================================
# SYNC GOOGLE CALENDAR
# =========================================================

@router.post("/sync")
async def sync_calendar(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_user_from_token(request, db)

    token = get_valid_google_token(user, db)

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Google not connected"
        )

    # =====================================================
    # DATE FILTER
    # PREVIOUS 3 MONTHS + NEXT 3 MONTHS
    # =====================================================

    today = datetime.now()

    past_limit = today - timedelta(days=90)

    future_limit = today + timedelta(days=90)

    # =====================================================
    # DELETE OLD EVENTS FROM GOOGLE
    # =====================================================

    old_events = db.query(GoogleEvent).filter(
        GoogleEvent.user_id == user.userid
    ).all()

    async with httpx.AsyncClient() as client:

        for old in old_events:

            try:

                if old.google_event_id:

                    await client.delete(
                        f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{old.google_event_id}",
                        headers={
                            "Authorization": f"Bearer {token}"
                        },
                        timeout=30
                    )

                    # IMPORTANT
                    await asyncio.sleep(1)

            except Exception as ex:
                print("DELETE ERROR:", ex)

    # =====================================================
    # CLEAR OLD DB EVENTS
    # =====================================================

    db.query(GoogleEvent).filter(
        GoogleEvent.user_id == user.userid
    ).delete()

    db.commit()

    # =====================================================
    # FETCH EVENTS
    # =====================================================

    events = db.query(CalendarEvents).all()

    synced = 0

    failed = 0

    # =====================================================
    # CREATE EVENTS
    # =====================================================

    async with httpx.AsyncClient() as client:

        for e in events:

            try:

                # =========================================
                # DATE FIX
                # =========================================

                if isinstance(e.event_date, str):

                    d = datetime.strptime(
                        e.event_date,
                        "%Y-%m-%d"
                    )

                else:

                    d = e.event_date

                # =========================================
                # DATE FILTER
                # =========================================

                if d < past_limit or d > future_limit:
                    continue

                start_date = d.strftime("%Y-%m-%d")

                end_date = (
                    d + timedelta(days=1)
                ).strftime("%Y-%m-%d")

                # =========================================
                # GOOGLE BODY
                # =========================================

                body = {
                    "summary": f"{e.company} IPO - {e.event_type}",
                    "start": {
                        "date": start_date
                    },
                    "end": {
                        "date": end_date
                    }
                }

                # =========================================
                # CREATE EVENT
                # =========================================

                res = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=30
                )

                # =========================================
                # QUOTA HANDLING
                # =========================================

                if res.status_code == 403:

                    print("GOOGLE QUOTA EXCEEDED")

                    print(res.text)

                    failed += 1

                    await asyncio.sleep(5)

                    continue

                # =========================================
                # OTHER ERRORS
                # =========================================

                if res.status_code not in [200, 201]:

                    print("GOOGLE ERROR:")

                    print(res.text)

                    failed += 1

                    continue

                # =========================================
                # SUCCESS
                # =========================================

                data = res.json()

                db.add(
                    GoogleEvent(
                        user_id=user.userid,
                        ipo_name=e.company,
                        event_type=e.event_type,
                        event_date=start_date,
                        google_event_id=data.get("id"),
                        synced_google=True
                    )
                )

                db.commit()

                synced += 1

                # =========================================
                # VERY IMPORTANT
                # =========================================

                await asyncio.sleep(1.2)

            except Exception as ex:

                print("SYNC ERROR:", ex)

                failed += 1

    # =====================================================
    # ENABLE SYNC
    # =====================================================

    user.google_sync_enabled = True

    db.commit()

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "success": True,
        "synced": synced,
        "failed": failed,
        "message": f"{synced} IPO events synced successfully"
    }

# =========================================================
# UNSYNC GOOGLE CALENDAR
# =========================================================

@router.post("/unsync")
async def unsync_calendar(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_user_from_token(request, db)

    token = get_valid_google_token(user, db)

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Google not connected"
        )

    events = db.query(GoogleEvent).filter(
        GoogleEvent.user_id == user.userid
    ).all()

    deleted = 0

    failed = 0

    async with httpx.AsyncClient() as client:

        for e in events:

            try:

                if not e.google_event_id:
                    continue

                res = await client.delete(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{e.google_event_id}",
                    headers={
                        "Authorization": f"Bearer {token}"
                    },
                    timeout=30
                )

                if res.status_code in [200, 204, 404]:

                    deleted += 1

                else:

                    failed += 1

                    print("DELETE ERROR:")

                    print(res.text)

                # IMPORTANT
                await asyncio.sleep(1)

            except Exception as ex:

                print("UNSYNC ERROR:", ex)

                failed += 1

    # =====================================================
    # CLEAR DB
    # =====================================================

    db.query(GoogleEvent).filter(
        GoogleEvent.user_id == user.userid
    ).delete()

    user.google_sync_enabled = False

    db.commit()

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "success": True,
        "deleted": deleted,
        "failed": failed,
        "message": f"{deleted} events removed successfully"
    }