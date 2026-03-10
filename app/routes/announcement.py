from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementResponse
from app.s3_utils import upload_file_to_s3, delete_file_from_s3

router = APIRouter(
    prefix="/announcements",
    tags=["Announcements"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=AnnouncementResponse)
def create_announcement(
    company: str = Form(...),
    announcement: str = Form(...),
    announcements_type: str = Form("General"),
    url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    ann = Announcement(
        company=company,
        announcement=announcement,
        url=url,
        announcements_type=announcements_type,
        announcement_date=datetime.now(timezone.utc)
    )

    if image:
        ann.image_path = upload_file_to_s3(image, folder="announcements/images")
    if file:
        ann.file_path = upload_file_to_s3(file, folder="announcements/files")

    db.add(ann)
    db.commit()
    db.refresh(ann)

    return ann


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    company: str = Form(...),
    announcement: str = Form(...),
    announcements_type: str = Form("General"),
    url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    ann.company = company
    ann.announcement = announcement
    ann.announcements_type = announcements_type
    ann.url = url
    ann.announcement_date = datetime.now(timezone.utc)

    if image:
        delete_file_from_s3(ann.image_path)
        ann.image_path = upload_file_to_s3(image, folder="announcements/images")
    if file:
        delete_file_from_s3(ann.file_path)
        ann.file_path = upload_file_to_s3(file, folder="announcements/files")

    db.commit()
    db.refresh(ann)

    return ann


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    delete_file_from_s3(ann.image_path)
    delete_file_from_s3(ann.file_path)

    db.delete(ann)
    db.commit()

    return {"message": "Announcement deleted successfully"}


@router.get("/", response_model=List[AnnouncementResponse])
def get_announcements(db: Session = Depends(get_db)):
    return db.query(Announcement).order_by(Announcement.announcement_date.desc()).all()