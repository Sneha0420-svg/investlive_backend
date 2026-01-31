import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementResponse

# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/announcements",
    tags=["Announcements"]
)

# -------------------------------------------------------------------
# Upload configuration
# -------------------------------------------------------------------

UPLOAD_DIR = Path("uploads/announcements")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------------
# Database dependency
# -------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------
# File helper functions
# -------------------------------------------------------------------

def save_file(upload_file: UploadFile) -> str:
    """
    Save uploaded file with a unique name and return file path
    """
    ext = Path(upload_file.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return str(file_path)


def delete_file(path: Optional[str]):
    """
    Delete file from disk if exists
    """
    if path and Path(path).exists():
        Path(path).unlink()

# -------------------------------------------------------------------
# Create announcement
# -------------------------------------------------------------------

@router.post("/", response_model=AnnouncementResponse)
def create_announcement(
    company: str = Form(...),
    announcement: str = Form(...),
    announcements_type: str = Form("General"),
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    announcement = Announcement(
        company=company,
        announcement=announcement,
        announcements_type=announcements_type,
       announcement_date = datetime.now(timezone.utc)
    )

    if image:
        announcement.image_path = save_file(image)

    if file:
        announcement.file_path = save_file(file)

    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    return announcement

# -------------------------------------------------------------------
# Get all announcements
# -------------------------------------------------------------------

@router.get("/", response_model=List[AnnouncementResponse])
def get_announcements(db: Session = Depends(get_db)):
    return (
        db.query(Announcement)
        .order_by(Announcement.announcement_date.desc())
        .all()
    )

# -------------------------------------------------------------------
# Update announcement
# -------------------------------------------------------------------

@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    company: str = Form(...),
    announcement: str = Form(...),
    announcements_type: str = Form("General"),
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    announcement = db.query(Announcement).filter(
        Announcement.id == announcement_id
    ).first()

    if not announcement:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found"
        )

    announcement.company = company
    announcement.announcement = announcement
    announcement.announcements_type = announcements_type
    announcement.announcement_date = datetime.utcnow()

    if image:
        delete_file(announcement.image_path)
        announcement.image_path = save_file(image)

    if file:
        delete_file(announcement.file_path)
        announcement.file_path = save_file(file)

    db.commit()
    db.refresh(announcement)

    return announcement

# -------------------------------------------------------------------
# Delete announcement
# -------------------------------------------------------------------

@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
):
    announcement = db.query(Announcement).filter(
        Announcement.id == announcement_id
    ).first()

    if not announcement:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found"
        )

    delete_file(announcement.image_path)
    delete_file(announcement.file_path)

    db.delete(announcement)
    db.commit()

    return {"message": "Announcement deleted successfully"}
