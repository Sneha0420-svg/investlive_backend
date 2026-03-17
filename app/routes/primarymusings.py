# app/routes/primerrymusings.py
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
import os

from app.database import SessionLocal
from app.models.primarymusings import PrimaryMusings
from app.schemas.primarymusings import PrimaryMusingsResponse
from app.s3_utils import s3, S3_BUCKET, upload_file_to_s3, delete_file_from_s3, get_s3_file_url

# -------------------------------------------------------------------
# Router
# -------------------------------------------------------------------
router = APIRouter(
    prefix="/primerrymusings",
    tags=["PrimerryMusings"]
)

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- CREATE -----------------
@router.post("/", response_model=PrimaryMusingsResponse)
def create_PrimaryMusings(
    company: str = Form(...),
    exchange: str = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    instance = PrimaryMusings(
        company=company,
        exchange=exchange,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    if logo:
        instance.logo_image = upload_file_to_s3(
            file_obj=logo,
            folder="PrimerryMusings/logos",
            filename=logo.filename
        )
    if pdf:
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="PrimerryMusings/pdfs",
            filename=pdf.filename
        )

    db.add(instance)
    db.commit()
    db.refresh(instance)

    # Return presigned URLs
    instance.logo_image = get_s3_file_url(instance.logo_image) if instance.logo_image else None
    instance.pdf_path = get_s3_file_url(instance.pdf_path) if instance.pdf_path else None

    return instance

# ----------------- GET ALL -----------------
@router.get("/", response_model=List[PrimaryMusingsResponse])
def get_PrimaryMusingss(db: Session = Depends(get_db)):
    results = db.query(PrimaryMusings).order_by(PrimaryMusings.created_at.desc()).all()
    for r in results:
        r.logo_image = get_s3_file_url(r.logo_image) if r.logo_image else None
        r.pdf_path = get_s3_file_url(r.pdf_path) if r.pdf_path else None
    return results

# ----------------- UPDATE -----------------
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
    instance = db.query(PrimaryMusings).filter(PrimaryMusings.id == PrimaryMusings_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="PrimaryMusings not found")

    instance.company = company
    instance.exchange = exchange
    instance.content = content
    instance.created_at = datetime.now(timezone.utc)

    if logo:
        delete_file_from_s3(instance.logo_image)
        instance.logo_image = upload_file_to_s3(
            file_obj=logo,
            folder="PrimerryMusings/logos",
            filename=logo.filename
        )

    if pdf:
        delete_file_from_s3(instance.pdf_path)
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="PrimerryMusings/pdfs",
            filename=pdf.filename
        )

    db.commit()
    db.refresh(instance)

    # Return presigned URLs
    instance.logo_image = get_s3_file_url(instance.logo_image) if instance.logo_image else None
    instance.pdf_path = get_s3_file_url(instance.pdf_path) if instance.pdf_path else None

    return instance

# ----------------- DELETE -----------------
@router.delete("/{PrimaryMusings_id}")
def delete_PrimaryMusings(
    PrimaryMusings_id: int,
    db: Session = Depends(get_db),
):
    instance = db.query(PrimaryMusings).filter(PrimaryMusings.id == PrimaryMusings_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="PrimaryMusings not found")

    delete_file_from_s3(instance.logo_image)
    delete_file_from_s3(instance.pdf_path)

    db.delete(instance)
    db.commit()

    return {"message": "PrimaryMusings deleted successfully"}