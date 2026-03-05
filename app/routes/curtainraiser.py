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
from app.models.curtainraiser import CurtainRaiser
from app.schemas.curtainraiser import CurtainRaiserResponse


# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/curtainraisers",
    tags=["CurtainRaisers"]
)

# -------------------------------------------------------------------
# Upload configuration
# -------------------------------------------------------------------

UPLOAD_DIR = Path("uploads/CurtainRaisers")
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
    # Use a separate variable for the instance
    curtain_raiser_instance = CurtainRaiser(
        company=company,
        exchange=exchange,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    # Save files if provided
    if logo:
        curtain_raiser_instance.logo_image = save_file(logo)

    if pdf:
        curtain_raiser_instance.pdf_path = save_file(pdf)

    # Add to DB
    db.add(curtain_raiser_instance)
    db.commit()
    db.refresh(curtain_raiser_instance)

    return curtain_raiser_instance

# -------------------------------------------------------------------
# Get All CurtainRaisers
# -------------------------------------------------------------------

@router.get("/", response_model=List[CurtainRaiserResponse])
def get_CurtainRaisers(db: Session = Depends(get_db)):
    return (
        db.query(CurtainRaiser)
        .order_by(CurtainRaiser.created_at.desc())
        .all()
    )


# -------------------------------------------------------------------
# Update CurtainRaiser
# -------------------------------------------------------------------
# Update CurtainRaiser
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
    # Use a different variable name for the instance
    curtain_instance = db.query(CurtainRaiser).filter(
        CurtainRaiser.id == CurtainRaiser_id
    ).first()

    if not curtain_instance:
        raise HTTPException(
            status_code=404,
            detail="CurtainRaiser not found"
        )

    curtain_instance.company = company
    curtain_instance.exchange = exchange
    curtain_instance.content = content
    curtain_instance.created_at = datetime.now(timezone.utc)

    if logo:
        delete_file(curtain_instance.logo_image)
        curtain_instance.logo_image = save_file(logo)

    if pdf:
        delete_file(curtain_instance.pdf_path)
        curtain_instance.pdf_path = save_file(pdf)

    db.commit()
    db.refresh(curtain_instance)

    return curtain_instance


# Delete CurtainRaiser
@router.delete("/{CurtainRaiser_id}")
def delete_CurtainRaiser(
    CurtainRaiser_id: int,
    db: Session = Depends(get_db),
):
    curtain_instance = db.query(CurtainRaiser).filter(
        CurtainRaiser.id == CurtainRaiser_id
    ).first()

    if not curtain_instance:
        raise HTTPException(
            status_code=404,
            detail="CurtainRaiser not found"
        )

    delete_file(curtain_instance.logo_image)
    delete_file(curtain_instance.pdf_path)

    db.delete(curtain_instance)
    db.commit()

    return {"message": "CurtainRaiser deleted successfully"}