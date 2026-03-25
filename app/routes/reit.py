import uuid
from datetime import datetime, timezone,date
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
import os
from sqlalchemy import func
from app.database import SessionLocal
from app.models.reit import ReitInvitDebenture
from app.s3_utils import s3, S3_BUCKET, upload_file_to_s3, delete_file_from_s3, get_s3_file_url
from decimal import Decimal

# -------------------------------------------------------------------
# Router
# -------------------------------------------------------------------
router = APIRouter(
    prefix="/reit/invit/debenture",
    tags=["Reit/Invit/Debenture"]
)

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- CREATE -----------------

@router.post("/")
def create_reit_invit_debenture(
    company: str = Form(...),
    category: str = Form(...),
    lead_manager: str = Form(...),
    issue_start: date = Form(...),
    issue_end: date = Form(...),
    issue_price: Decimal = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if issue_end < issue_start:
        raise HTTPException(status_code=400, detail="issue_end must be after issue_start")

    instance = ReitInvitDebenture(
        company=company,
        category=category,
        lead_manager=lead_manager,
        issue_start=issue_start,
        issue_end=issue_end,
        issue_price=issue_price,
        content=content,
        created_at=datetime.now(timezone.utc)
    )

    # Upload logo
    if logo:
        unique_logo_name = f"{uuid.uuid4()}_{logo.filename}"
        instance.logo_image = upload_file_to_s3(
            file_obj=logo,
            folder="PrimaryMusings/logos",
            filename=unique_logo_name
        )

    # Upload PDF
    if pdf:
        unique_pdf_name = f"{uuid.uuid4()}_{pdf.filename}"
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="PrimaryMusings/pdfs",
            filename=unique_pdf_name
        )

    db.add(instance)
    db.commit()
    db.refresh(instance)

    # Convert S3 keys → URLs
    logo_url = get_s3_file_url(instance.logo_image) if instance.logo_image else None
    pdf_url = get_s3_file_url(instance.pdf_path) if instance.pdf_path else None

    # ✅ Hardcoded response
    return {
        "id": instance.id,
        "company": instance.company,
        "category": instance.category,
        "lead_manager": instance.lead_manager,
        "issue_start": instance.issue_start,
        "issue_end": instance.issue_end,
        "issue_price": float(instance.issue_price),
        "content": instance.content,
        "logo_image": logo_url,
        "pdf_path": pdf_url,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
    }
@router.get("/")
def get_reit_invit_debenture(db: Session = Depends(get_db)):
    results = db.query(ReitInvitDebenture)\
        .order_by(ReitInvitDebenture.created_at.desc())\
        .all()

    response = []

    for r in results:
        response.append({
            "id": r.id,
            "company": r.company,
            "category": r.category,
            "lead_manager": r.lead_manager,
            "issue_start": r.issue_start,
            "issue_end": r.issue_end,
            "issue_price": float(r.issue_price) if r.issue_price else None,
            "content": r.content,
            "logo_image": get_s3_file_url(r.logo_image) if r.logo_image else None,
            "pdf_path": get_s3_file_url(r.pdf_path) if r.pdf_path else None,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        })

    return response

# ----------------- GET BY CATEGORY -----------------
@router.get("/category/{category}")
def get_by_category(category: str, db: Session = Depends(get_db)):
    results = db.query(ReitInvitDebenture)\
        .filter(func.lower(ReitInvitDebenture.category) == category.lower())\
        .order_by(ReitInvitDebenture.created_at.desc())\
        .all()

    if not results:
        raise HTTPException(status_code=404, detail="No records found for this category")

    response = []
    for r in results:
        response.append({
            "id": r.id,
            "company": r.company,
            "category": r.category,
            "lead_manager": r.lead_manager,
            "issue_start": r.issue_start,
            "issue_end": r.issue_end,
            "issue_price": float(r.issue_price) if r.issue_price else None,
            "content": r.content,
            "logo_image": get_s3_file_url(r.logo_image) if r.logo_image else None,
            "pdf_path": get_s3_file_url(r.pdf_path) if r.pdf_path else None,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        })

    return response

@router.put("/{id}")
def update_reit_invit_debenture(
    id: int,
    company: str = Form(...),
    category: str = Form(...),
    lead_manager: str = Form(...),
    issue_start: date = Form(...),
    issue_end: date = Form(...),
    issue_price: Decimal = Form(...),
    content: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    instance = db.query(ReitInvitDebenture).filter(ReitInvitDebenture.id == id).first()

    if not instance:
        raise HTTPException(status_code=404, detail="Record not found")

    # ✅ Validate dates
    if issue_end < issue_start:
        raise HTTPException(status_code=400, detail="issue_end must be after issue_start")

    # ✅ Update fields
    instance.company = company
    instance.category = category
    instance.lead_manager = lead_manager
    instance.issue_start = issue_start
    instance.issue_end = issue_end
    instance.issue_price = issue_price
    instance.content = content
    instance.updated_at = datetime.now(timezone.utc)

    # ✅ Update logo
    if logo:
        if instance.logo_image:
            delete_file_from_s3(instance.logo_image)

        unique_logo_name = f"{uuid.uuid4()}_{logo.filename}"
        instance.logo_image = upload_file_to_s3(
            file_obj=logo,
            folder="PrimaryMusings/logos",
            filename=unique_logo_name
        )

    # ✅ Update PDF
    if pdf:
        if instance.pdf_path:
            delete_file_from_s3(instance.pdf_path)

        unique_pdf_name = f"{uuid.uuid4()}_{pdf.filename}"
        instance.pdf_path = upload_file_to_s3(
            file_obj=pdf,
            folder="PrimaryMusings/pdfs",
            filename=unique_pdf_name
        )

    db.commit()
    db.refresh(instance)

    # ✅ Return clean response
    return {
        "id": instance.id,
        "company": instance.company,
        "category": instance.category,
        "lead_manager": instance.lead_manager,
        "issue_start": instance.issue_start,
        "issue_end": instance.issue_end,
        "issue_price": float(instance.issue_price),
        "content": instance.content,
        "logo_image": get_s3_file_url(instance.logo_image) if instance.logo_image else None,
        "pdf_path": get_s3_file_url(instance.pdf_path) if instance.pdf_path else None,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
    }
# ----------------- DELETE -----------------
@router.delete("/{id}")
def delete_reit_invit_debenture(
    id: int,
    db: Session = Depends(get_db),
):
    instance = db.query(ReitInvitDebenture).filter(ReitInvitDebenture.id == id).first()

    if not instance:
        raise HTTPException(status_code=404, detail="Record not found")

    # ✅ Delete logo if exists
    if instance.logo_image:
        try:
            delete_file_from_s3(instance.logo_image)
        except Exception as e:
            print(f"Error deleting logo: {e}")

    # ✅ Delete PDF if exists
    if instance.pdf_path:
        try:
            delete_file_from_s3(instance.pdf_path)
        except Exception as e:
            print(f"Error deleting pdf: {e}")

    db.delete(instance)
    db.commit()

    return {"message": "Deleted successfully"}