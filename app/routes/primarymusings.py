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
from app.models.primarymusings import PrimaryMusings
from app.schemas.primarymusings import PrimaryMusingsResponse


# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/primerrymusings",
    tags=["PrimerryMusings"]
)

# -------------------------------------------------------------------
# Upload configuration
# -------------------------------------------------------------------

UPLOAD_DIR = Path("uploads/PrimaryMusingss")
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
# File helpers
# -------------------------------------------------------------------

def save_file(upload_file: UploadFile) -> str:
    ext = Path(upload_file.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return str(file_path)


def delete_file(path: Optional[str]):
    if path and Path(path).exists():
        Path(path).unlink()


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
    # Create instance of the model
    primarymusings = PrimaryMusings(
        company=company,
        exchange=exchange,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    # Save files if provided
    if logo:
        primarymusings.logo_image = save_file(logo)

    if pdf:
        primarymusings.pdf_path = save_file(pdf)  # ⚠ Use the instance, not the class

    # Add to DB
    db.add(primarymusings)
    db.commit()
    db.refresh(primarymusings)

    return primarymusings

# -------------------------------------------------------------------
# Get All PrimaryMusingss
# -------------------------------------------------------------------

@router.get("/", response_model=List[PrimaryMusingsResponse])
def get_PrimaryMusingss(db: Session = Depends(get_db)):
    return (
        db.query(PrimaryMusings)
        .order_by(PrimaryMusings.created_at.desc())
        .all()
    )


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
    # Use a different variable name for the instance
    primarymusings_instance = db.query(PrimaryMusings).filter(
        PrimaryMusings.id == PrimaryMusings_id
    ).first()

    if not primarymusings_instance:
        raise HTTPException(
            status_code=404,
            detail="PrimaryMusings not found"
        )

    # Update fields
    primarymusings_instance.company = company
    primarymusings_instance.exchange = exchange
    primarymusings_instance.content = content
    primarymusings_instance.created_at = datetime.now(timezone.utc)

    # Handle file uploads
    if logo:
        delete_file(primarymusings_instance.logo_image)
        primarymusings_instance.logo_image = save_file(logo)

    if pdf:
        delete_file(primarymusings_instance.pdf_path)
        primarymusings_instance.pdf_path = save_file(pdf)

    db.commit()
    db.refresh(primarymusings_instance)

    return primarymusings_instance
# -------------------------------------------------------------------
# Delete PrimaryMusings
# -------------------------------------------------------------------
@router.delete("/{PrimaryMusings_id}")
def delete_PrimaryMusings(
    PrimaryMusings_id: int,
    db: Session = Depends(get_db),
):
    # Use a different variable name for the instance
    primarymusings_instance = db.query(PrimaryMusings).filter(
        PrimaryMusings.id == PrimaryMusings_id
    ).first()

    if not primarymusings_instance:
        raise HTTPException(
            status_code=404,
            detail="PrimaryMusings not found"
        )

    # Delete associated files
    delete_file(primarymusings_instance.logo_image)
    delete_file(primarymusings_instance.pdf_path)

    # Delete from database
    db.delete(primarymusings_instance)
    db.commit()

    return {"message": "PrimaryMusings deleted successfully"}