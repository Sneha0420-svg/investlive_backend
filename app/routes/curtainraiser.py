import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.curtainraiser import CurtainRaiser
from app.schemas.curtainraiser import CurtainRaiserResponse
import os
from app.s3_utils import s3, S3_BUCKET, upload_file_to_s3, delete_file_from_s3, get_s3_file_url
router = APIRouter(
    prefix="/curtainraisers",
    tags=["CurtainRaisers"]
)

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- HELPERS -----------------
def upload_file_with_type(file: UploadFile, folder: str) -> str:
    """
    Upload a file to S3, keep original extension, set Content-Type correctly.
    """
    ext = os.path.splitext(file.filename)[1] or ""
    s3_key = f"{folder}/{uuid.uuid4()}{ext}"
    # Determine Content-Type
    content_type = file.content_type or "application/octet-stream"
    s3.upload_fileobj(getattr(file, "file", file), S3_BUCKET, s3_key, ExtraArgs={"ContentType": content_type})
    return s3_key

# ----------------- CREATE -----------------
@router.post("/", response_model=CurtainRaiserResponse)
def create_CurtainRaiser(
    company: str = Form(...),
    exchange: str = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    instance = CurtainRaiser(
        company=company,
        exchange=exchange,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    if logo:
        instance.logo_image = upload_file_to_s3(
            file_obj=logo,
            folder="CurtainRaisers/logos",
            filename=logo.filename
        )

    if pdf:
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="CurtainRaisers/pdfs",
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
@router.get("/", response_model=List[CurtainRaiserResponse])
def get_CurtainRaisers(db: Session = Depends(get_db)):
    results = db.query(CurtainRaiser).order_by(CurtainRaiser.created_at.desc()).all()
    for r in results:
        r.logo_image = get_s3_file_url(r.logo_image) if r.logo_image else None
        r.pdf_path = get_s3_file_url(r.pdf_path) if r.pdf_path else None
    return results

# ----------------- UPDATE -----------------
@router.put("/{CurtainRaiser_id}", response_model=CurtainRaiserResponse)
def update_CurtainRaiser(
    CurtainRaiser_id: int,
    company: str = Form(...),
    exchange: str = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    instance = db.query(CurtainRaiser).filter(CurtainRaiser.id == CurtainRaiser_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="CurtainRaiser not found")

    instance.company = company
    instance.exchange = exchange
    instance.content = content
    instance.created_at = datetime.now(timezone.utc)

    if logo:
        delete_file_from_s3(instance.logo_image)
        instance.logo_image = upload_file_to_s3(logo, "CurtainRaisers/logos", filename=logo.filename)

    if pdf:
        delete_file_from_s3(instance.pdf_path)
        instance.pdf_path = upload_file_to_s3(pdf, "CurtainRaisers/pdfs", filename=pdf.filename)

    db.commit()
    db.refresh(instance)

    # Return presigned URLs
    instance.logo_image = get_s3_file_url(instance.logo_image) if instance.logo_image else None
    instance.pdf_path = get_s3_file_url(instance.pdf_path) if instance.pdf_path else None

    return instance

# ----------------- DELETE -----------------
@router.delete("/{CurtainRaiser_id}")
def delete_CurtainRaiser(
    CurtainRaiser_id: int,
    db: Session = Depends(get_db),
):
    instance = db.query(CurtainRaiser).filter(CurtainRaiser.id == CurtainRaiser_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="CurtainRaiser not found")

    delete_file_from_s3(instance.logo_image)
    delete_file_from_s3(instance.pdf_path)

    db.delete(instance)
    db.commit()

    return {"message": "CurtainRaiser deleted successfully"}