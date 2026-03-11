# app/routes/snapshots.py
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotResponse
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_file_url
)

# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------
router = APIRouter(
    prefix="/snapshots",
    tags=["Snapshots"]
)

# -------------------------------------------------------------------
# DB Dependency
# -------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------
# File helpers for S3
# -------------------------------------------------------------------
def save_file_to_s3(upload_file: UploadFile, folder: str) -> str:
    """
    Upload file to S3 and return the S3 key
    """
    ext = upload_file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    s3_key = f"{folder}/{filename}"

    upload_file.file.seek(0)
    upload_file_to_s3(upload_file.file, s3_key)

    return s3_key

def delete_file_from_s3_safe(s3_key: Optional[str]):
    if s3_key:
        try:
            delete_file_from_s3(s3_key)
        except Exception as e:
            print(f"Error deleting {s3_key} from S3: {e}")

# -------------------------------------------------------------------
# Create Snapshot
# -------------------------------------------------------------------
@router.post("/", response_model=SnapshotResponse)
def create_snapshot(
    company: str = Form(...),
    exchange: str = Form(...),
    listing_date: date = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    snapshot = Snapshot(
        company=company,
        exchange=exchange,
        listing_date=listing_date,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    # Upload files to S3
    if logo:
        snapshot.logo_image = save_file_to_s3(logo, folder="snapshots/logo")
    if pdf:
        snapshot.pdf_path = save_file_to_s3(pdf, folder="snapshots/pdf")

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    # Convert S3 keys to presigned URLs
    if snapshot.logo_image:
        snapshot.logo_image = get_s3_file_url(snapshot.logo_image)
    if snapshot.pdf_path:
        snapshot.pdf_path = get_s3_file_url(snapshot.pdf_path)

    return snapshot

# -------------------------------------------------------------------
# Get All Snapshots
# -------------------------------------------------------------------
@router.get("/", response_model=List[SnapshotResponse])
def get_snapshots(db: Session = Depends(get_db)):
    results = db.query(Snapshot).order_by(Snapshot.created_at.desc()).all()
    for s in results:
        if s.logo_image:
            s.logo_image = get_s3_file_url(s.logo_image)
        if s.pdf_path:
            s.pdf_path = get_s3_file_url(s.pdf_path)
    return results

# -------------------------------------------------------------------
# Update Snapshot
# -------------------------------------------------------------------
@router.put("/{snapshot_id}", response_model=SnapshotResponse)
def update_snapshot(
    snapshot_id: int,
    company: str = Form(...),
    exchange: str = Form(...),
    listing_date: date = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    snapshot.company = company
    snapshot.exchange = exchange
    snapshot.listing_date = listing_date
    snapshot.content = content
    snapshot.created_at = datetime.now(timezone.utc)

    # Replace files in S3 if provided
    if logo:
        delete_file_from_s3_safe(snapshot.logo_image)
        snapshot.logo_image = save_file_to_s3(logo, folder="snapshots/logo")
    if pdf:
        delete_file_from_s3_safe(snapshot.pdf_path)
        snapshot.pdf_path = save_file_to_s3(pdf, folder="snapshots/pdf")

    db.commit()
    db.refresh(snapshot)

    # Convert S3 keys to presigned URLs
    if snapshot.logo_image:
        snapshot.logo_image = get_s3_file_url(snapshot.logo_image)
    if snapshot.pdf_path:
        snapshot.pdf_path = get_s3_file_url(snapshot.pdf_path)

    return snapshot

# -------------------------------------------------------------------
# Delete Snapshot
# -------------------------------------------------------------------
@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Delete files from S3
    delete_file_from_s3_safe(snapshot.logo_image)
    delete_file_from_s3_safe(snapshot.pdf_path)

    # Delete from DB
    db.delete(snapshot)
    db.commit()

    return {"message": "Snapshot deleted successfully"}