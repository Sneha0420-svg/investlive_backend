# app/cron/sync_calendar.py

from app.database import SessionLocal
from app.models.auth import User
from app.models.google_events import GoogleEvent
from app.routes.google_calendar import refresh_google_token
from app.services.ipo_service import getIPOEvents
import requests


def sync_ipo_calendar():
    db = SessionLocal()

    users = db.query(User).filter(User.google_refresh_token != None).all()

    ipo_data = getIPOEvents()

    for user in users:
        access_token = refresh_google_token(user)

        for ipo in ipo_data:
            title = f"{ipo['SCRIP']} IPO Opening"
            date = ipo["ISS_OPEN"]

            # check existing
            existing = db.query(GoogleEvent).filter_by(
                user_id=user.userid,
                ipo_name=title,
                event_date=date
            ).first()

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            body = {
                "summary": title,
                "start": {"date": date},
                "end": {"date": date},
            }

            if existing:
                # 🔁 UPDATE
                requests.put(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{existing.google_event_id}",
                    headers=headers,
                    json=body,
                )
            else:
                # ➕ CREATE
                res = requests.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers=headers,
                    json=body,
                )

                if res.status_code == 200:
                    event_id = res.json()["id"]

                    db.add(GoogleEvent(
                        user_id=user.userid,
                        ipo_name=title,
                        event_type="Opening",
                        event_date=date,
                        google_event_id=event_id,
                    ))
                    db.commit()

    db.close()