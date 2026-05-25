from fastapi import APIRouter, Depends
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.mail_config import conf
from app.schemas.email import EmailSchema
from app.database import SessionLocal
from app.models.email import OneTimeLink   
import uuid
from fastapi.responses import RedirectResponse


router = APIRouter()

# -------------------- DB DEP --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- NORMAL MAIL --------------------
@router.post("/send-mail")
async def send_mail(data: EmailSchema):

    message = MessageSchema(
        subject=data.subject,
        recipients=[data.email],
        body=data.body,
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    return {"message": "Mail sent successfully"}


# -------------------- ONE TIME LINK --------------------
@router.post("/send-once-link")
async def send_once_link(data: EmailSchema, db=Depends(get_db)):

    token = str(uuid.uuid4())

    link = f"http://localhost:8000/open/{token}"

    # save token in DB
    db.add(OneTimeLink(token=token, url=data.body, used=False))
    db.commit()

    message = MessageSchema(
        subject="One Time Access Link",
        recipients=[data.email],
        body=f"Click this link (valid only once): {link}",
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    return {"message": "One-time link sent"}


# -------------------- OPEN LINK --------------------

@router.get("/open/{token}")
def open_once_link(token: str, db=Depends(get_db)):

    record = db.query(OneTimeLink).filter(OneTimeLink.token == token).first()

    if not record:
        return RedirectResponse(url="http://localhost:3000/invalid-link")

    if record.used:
        return RedirectResponse(url="http://localhost:3000/link-used")

    record.used = True
    db.commit()

    # 👉 redirect to actual page
    return RedirectResponse(url=record.url)