import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.curtainraiser import CurtainRaiser
from app.schemas.curtainraiser import CurtainRaiserResponse

# Import your S3 helpers
from app.s3_utils import upload_file_to_s3, delete_file_from_s3

# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/curtainraisers",
    tags=["CurtainRaisers"]
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
# Create CurtainRaiser
# -------------------------------------------------------------------

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
            folder="CurtainRaisers/logos"
        )

    if pdf:
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="CurtainRaisers/pdfs"
        )

    db.add(instance)
    db.commit()
    db.refresh(instance)

    return instance

# -------------------------------------------------------------------
# Get All CurtainRaisers
# -------------------------------------------------------------------

@router.get("/", response_model=List[CurtainRaiserResponse])
def get_CurtainRaisers(db: Session = Depends(get_db)):
    return db.query(CurtainRaiser).order_by(CurtainRaiser.created_at.desc()).all()

# -------------------------------------------------------------------
# Update CurtainRaiser
# -------------------------------------------------------------------

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
        instance.logo_image = upload_file_to_s3(logo, "CurtainRaisers/logos")

    if pdf:
        delete_file_from_s3(instance.pdf_path)
        instance.pdf_path = upload_file_to_s3(pdf, "CurtainRaisers/pdfs")

    db.commit()
    db.refresh(instance)

    return instance

# -------------------------------------------------------------------
# Delete CurtainRaiser
# -------------------------------------------------------------------

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