import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementResponse
from app.s3_utils import s3, S3_BUCKET, upload_file_to_s3, delete_file_from_s3, get_s3_file_url

router = APIRouter(
    prefix="/announcements",
    tags=["Announcements"]
)

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- HELPERS ----------------
def upload_file_with_type(file: UploadFile, folder: str) -> str:
    """
    Upload a file to S3 with correct Content-Type.
    """
    import os
    ext = os.path.splitext(file.filename)[1].lower() or ""
    key = f"{folder}/{uuid.uuid4()}{ext}"

    # Determine Content-Type
    content_type = file.content_type or "application/octet-stream"
    if ext == ".pdf":
        content_type = "application/pdf"
    elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
        content_type = f"image/{ext[1:]}"  # remove dot

    s3.upload_fileobj(file.file, S3_BUCKET, key, ExtraArgs={"ContentType": content_type})
    return key


# ---------------- CREATE ----------------
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
        ann.image_path = upload_file_with_type(image, "announcements/images")
    if file:
        ann.file_path = upload_file_with_type(file, "announcements/files")

    db.add(ann)
    db.commit()
    db.refresh(ann)

    # Return presigned URLs
    ann.image_path = get_s3_file_url(ann.image_path) if ann.image_path else None
    ann.file_path = get_s3_file_url(ann.file_path) if ann.file_path else None

    return ann


# ---------------- UPDATE ----------------
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
        ann.image_path = upload_file_with_type(image, "announcements/images")
    if file:
        delete_file_from_s3(ann.file_path)
        ann.file_path = upload_file_with_type(file, "announcements/files")

    db.commit()
    db.refresh(ann)

    ann.image_path = get_s3_file_url(ann.image_path) if ann.image_path else None
    ann.file_path = get_s3_file_url(ann.file_path) if ann.file_path else None

    return ann


# ---------------- DELETE ----------------
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


# ---------------- GET ALL ----------------
@router.get("/", response_model=List[AnnouncementResponse])
def get_announcements(db: Session = Depends(get_db)):
    results = db.query(Announcement).order_by(Announcement.announcement_date.desc()).all()
    for ann in results:
        ann.image_path = get_s3_file_url(ann.image_path) if ann.image_path else None
        ann.file_path = get_s3_file_url(ann.file_path) if ann.file_path else None
    return results