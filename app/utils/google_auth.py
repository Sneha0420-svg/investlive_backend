import os
import requests
from datetime import datetime, timedelta
def refresh_google_token(user, db):
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

        data = res.json()

        print("TOKEN RESPONSE:", data)

        if "access_token" not in data:
            return None

        user.google_access_token = data["access_token"]

        if "refresh_token" in data:
            user.google_refresh_token = data["refresh_token"]

        user.google_token_expiry = (
            datetime.utcnow()
            + timedelta(seconds=data.get("expires_in", 3600))
        )

        db.commit()

        return user.google_access_token

    except Exception as e:
        print("TOKEN REFRESH ERROR:", str(e))
        return None

def get_valid_google_token(user, db):
    # ✅ If still valid
    if user.google_token_expiry and user.google_token_expiry > datetime.utcnow():
        return user.google_access_token

    # ✅ Otherwise refresh
    return refresh_google_token(user, db)