import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone,date
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
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotResponse


# -------------------------------------------------------------------
# Router setup
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/snapshots",
    tags=["Snapshots"]
)

# -------------------------------------------------------------------
# Upload configuration
# -------------------------------------------------------------------

UPLOAD_DIR = Path("uploads/snapshots")
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
# Create Snapshot
# -------------------------------------------------------------------

@router.post("/", response_model=SnapshotResponse)
def create_snapshot(
    company: str = Form(...),
    exchange: str = Form(...),
    listing_date:date=Form(...),
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
        snapshot.logo_image = save_file(logo)

    if pdf:
        snapshot.pdf_path = save_file(pdf)

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot


# -------------------------------------------------------------------
# Get All Snapshots
# -------------------------------------------------------------------

@router.get("/", response_model=List[SnapshotResponse])
def get_snapshots(db: Session = Depends(get_db)):
    return (
        db.query(Snapshot)
        .order_by(Snapshot.created_at.desc())
        .all()
    )


# -------------------------------------------------------------------
# Update Snapshot
# -------------------------------------------------------------------

@router.put("/{snapshot_id}", response_model=SnapshotResponse)
def update_snapshot(
    snapshot_id: int,
    company: str = Form(...),
    exchange: str = Form(...),
    listing_date:date=Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    snapshot = db.query(Snapshot).filter(
        Snapshot.id == snapshot_id
    ).first()

    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail="Snapshot not found"
        )

    snapshot.company = company
    snapshot.exchange =exchange
    snapshot.listing_date=listing_date
    snapshot.content = content
    snapshot.created_at = datetime.now(timezone.utc)

    if logo:
        delete_file(snapshot.logo_image)
        snapshot.logo_image = save_file(logo)

    if pdf:
        delete_file(snapshot.pdf_path)
        snapshot.pdf_path = save_file(pdf)

    db.commit()
    db.refresh(snapshot)

    return snapshot


# -------------------------------------------------------------------
# Delete Snapshot
# -------------------------------------------------------------------

@router.delete("/{snapshot_id}")
def delete_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    snapshot = db.query(Snapshot).filter(
        Snapshot.id == snapshot_id
    ).first()

    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail="Snapshot not found"
        )

    delete_file(snapshot.logo_image)
    delete_file(snapshot.pdf_path)

    db.delete(snapshot)
    db.commit()

    return {"message": "Snapshot deleted successfully"}