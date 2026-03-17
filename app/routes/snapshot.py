# app/routes/snapshots.py
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional
import os

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotResponse
from app.s3_utils import s3, S3_BUCKET, upload_file_to_s3, delete_file_from_s3, get_s3_file_url

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
# File helper (upload with correct content type)
# -------------------------------------------------------------------
def upload_file_with_content_type(file: UploadFile, folder: str) -> str:
    ext = os.path.splitext(file.filename)[1] or ""
    s3_key = f"{folder}/{uuid.uuid4()}{ext}"
    content_type = file.content_type or "application/octet-stream"
    s3.upload_fileobj(getattr(file, "file", file), S3_BUCKET, s3_key, ExtraArgs={"ContentType": content_type})
    return s3_key

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

    if logo:
        snapshot.logo_image = upload_file_to_s3(file_obj=logo, folder="snapshots/logo", filename=logo.filename)
    if pdf:
        snapshot.pdf_path = upload_file_to_s3(file_obj=pdf, folder="snapshots/pdf", filename=pdf.filename)

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    # Return presigned URLs
    snapshot.logo_image = get_s3_file_url(snapshot.logo_image) if snapshot.logo_image else None
    snapshot.pdf_path = get_s3_file_url(snapshot.pdf_path) if snapshot.pdf_path else None

    return snapshot

# -------------------------------------------------------------------
# Get All Snapshots
# -------------------------------------------------------------------
@router.get("/", response_model=List[SnapshotResponse])
def get_snapshots(db: Session = Depends(get_db)):
    results = db.query(Snapshot).order_by(Snapshot.created_at.desc()).all()
    for s in results:
        s.logo_image = get_s3_file_url(s.logo_image) if s.logo_image else None
        s.pdf_path = get_s3_file_url(s.pdf_path) if s.pdf_path else None
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

    if logo:
        delete_file_from_s3(snapshot.logo_image)
        snapshot.logo_image = upload_file_to_s3(file_obj=logo, folder="snapshots/logo", filename=logo.filename)
    if pdf:
        delete_file_from_s3(snapshot.pdf_path)
        snapshot.pdf_path = upload_file_to_s3(file_obj=pdf, folder="snapshots/pdf", filename=pdf.filename)

    db.commit()
    db.refresh(snapshot)

    snapshot.logo_image = get_s3_file_url(snapshot.logo_image) if snapshot.logo_image else None
    snapshot.pdf_path = get_s3_file_url(snapshot.pdf_path) if snapshot.pdf_path else None

    return snapshot

# -------------------------------------------------------------------
# Delete Snapshot
# -------------------------------------------------------------------
@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    delete_file_from_s3(snapshot.logo_image)
    delete_file_from_s3(snapshot.pdf_path)

    db.delete(snapshot)
    db.commit()

    return {"message": "Snapshot deleted successfully"}