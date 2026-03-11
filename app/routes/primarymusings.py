# app/routes/primerrymusings.py
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.primarymusings import PrimaryMusings
from app.schemas.primarymusings import PrimaryMusingsResponse
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_file_url
)

# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------
router = APIRouter(
    prefix="/primerrymusings",
    tags=["PrimerryMusings"]
)

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
# File helpers for S3
# -------------------------------------------------------------------
def save_file_to_s3(upload_file: UploadFile, folder: str) -> str:
    """
    Upload file to S3 and return S3 key
    """
    ext = upload_file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    s3_key = f"{folder}/{filename}"

    upload_file.file.seek(0)
    upload_file_to_s3(upload_file.file, s3_key)

    return s3_key

def delete_file_from_s3_safe(s3_key: Optional[str]):
    """
    Safely delete file from S3
    """
    if s3_key:
        try:
            delete_file_from_s3(s3_key)
        except Exception as e:
            print(f"Error deleting {s3_key} from S3: {e}")

# -------------------------------------------------------------------
# Create PrimaryMusings
# -------------------------------------------------------------------
@router.post("/", response_model=PrimaryMusingsResponse)
def create_PrimaryMusings(
    company: str = Form(...),
    exchange: str = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    primarymusings = PrimaryMusings(
        company=company,
        exchange=exchange,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    # Upload files to S3
    if logo:
        primarymusings.logo_image = save_file_to_s3(logo, folder="primerrymusings/logo")
    if pdf:
        primarymusings.pdf_path = save_file_to_s3(pdf, folder="primerrymusings/pdf")

    db.add(primarymusings)
    db.commit()
    db.refresh(primarymusings)

    # Convert S3 keys to presigned URLs for response
    if primarymusings.logo_image:
        primarymusings.logo_image = get_s3_file_url(primarymusings.logo_image)
    if primarymusings.pdf_path:
        primarymusings.pdf_path = get_s3_file_url(primarymusings.pdf_path)

    return primarymusings

# -------------------------------------------------------------------
# Get All PrimaryMusingss
# -------------------------------------------------------------------
@router.get("/", response_model=List[PrimaryMusingsResponse])
def get_PrimaryMusingss(db: Session = Depends(get_db)):
    results = db.query(PrimaryMusings).order_by(PrimaryMusings.created_at.desc()).all()
    for item in results:
        if item.logo_image:
            item.logo_image = get_s3_file_url(item.logo_image)
        if item.pdf_path:
            item.pdf_path = get_s3_file_url(item.pdf_path)
    return results

# -------------------------------------------------------------------
# Update PrimaryMusings
# -------------------------------------------------------------------
@router.put("/{PrimaryMusings_id}", response_model=PrimaryMusingsResponse)
def update_PrimaryMusings(
    PrimaryMusings_id: int,
    company: str = Form(...),
    exchange: str = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    instance = db.query(PrimaryMusings).filter(
        PrimaryMusings.id == PrimaryMusings_id
    ).first()

    if not instance:
        raise HTTPException(status_code=404, detail="PrimaryMusings not found")

    instance.company = company
    instance.exchange = exchange
    instance.content = content
    instance.created_at = datetime.now(timezone.utc)

    # Replace files in S3 if provided
    if logo:
        delete_file_from_s3_safe(instance.logo_image)
        instance.logo_image = save_file_to_s3(logo, folder="primerrymusings/logo")
    if pdf:
        delete_file_from_s3_safe(instance.pdf_path)
        instance.pdf_path = save_file_to_s3(pdf, folder="primerrymusings/pdf")

    db.commit()
    db.refresh(instance)

    # Convert S3 keys to presigned URLs
    if instance.logo_image:
        instance.logo_image = get_s3_file_url(instance.logo_image)
    if instance.pdf_path:
        instance.pdf_path = get_s3_file_url(instance.pdf_path)

    return instance

# -------------------------------------------------------------------
# Delete PrimaryMusings
# -------------------------------------------------------------------
@router.delete("/{PrimaryMusings_id}")
def delete_PrimaryMusings(
    PrimaryMusings_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a PrimaryMusings record and associated files from S3.
    """
    instance = db.query(PrimaryMusings).filter(
        PrimaryMusings.id == PrimaryMusings_id
    ).first()

    if not instance:
        raise HTTPException(status_code=404, detail="PrimaryMusings not found")

    # Delete files safely
    delete_file_from_s3_safe(instance.logo_image)
    delete_file_from_s3_safe(instance.pdf_path)

    # Delete DB record
    db.delete(instance)
    db.commit()

    return {"message": "PrimaryMusings deleted successfully"}