import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.ads import Ad
from app.schemas.ads import AdResponse
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_s3_file_url

router = APIRouter(prefix="/ads", tags=["ads"])

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Create Ad ----------------
@router.post("/", response_model=AdResponse)
async def create_ad(
    company_name: str = Form(...),
    company_website: str | None = Form(None),
    extra_info: str | None = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not image.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        raise HTTPException(status_code=400, detail="Invalid image file type")

    # Upload image to S3
    try:
        s3_key = upload_file_to_s3(
            file_obj=image.file,
            folder="ads",
            filename=f"{uuid.uuid4()}_{image.filename}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    ad = Ad(
        company_name=company_name,
        company_website=company_website,
        extra_info=extra_info,
        image_path=s3_key
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)

    return AdResponse(
        id=ad.id,
        company_name=ad.company_name,
        company_website=ad.company_website,
        extra_info=ad.extra_info,
        image_url=get_s3_file_url(ad.image_path),
        uploaded_at=ad.uploaded_at.isoformat()
    )

# ---------------- Get All Ads ----------------
@router.get("/", response_model=list[AdResponse])
def get_ads(db: Session = Depends(get_db)):
    ads = db.query(Ad).order_by(Ad.uploaded_at.desc()).all()
    return [
        AdResponse(
            id=a.id,
            company_name=a.company_name,
            company_website=a.company_website,
            extra_info=a.extra_info,
            image_url=get_s3_file_url(a.image_path),
            uploaded_at=a.uploaded_at.isoformat()
        )
        for a in ads
    ]

# ---------------- Update Ad ----------------
@router.put("/{ad_id}", response_model=AdResponse)
async def update_ad(
    ad_id: int,
    company_name: str = Form(...),
    company_website: str | None = Form(None),
    extra_info: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    ad.company_name = company_name
    ad.company_website = company_website
    ad.extra_info = extra_info

    if image:
        # Delete old image
        try:
            delete_file_from_s3(ad.image_path)
        except:
            pass

        # Upload new image
        try:
            s3_key = upload_file_to_s3(
                file_obj=image.file,
                folder="ads",
                filename=f"{uuid.uuid4()}_{image.filename}"
            )
            ad.image_path = s3_key
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    db.commit()
    db.refresh(ad)

    return AdResponse(
        id=ad.id,
        company_name=ad.company_name,
        company_website=ad.company_website,
        extra_info=ad.extra_info,
        image_url=get_s3_file_url(ad.image_path),
        uploaded_at=ad.uploaded_at.isoformat()
    )

# ---------------- Delete Ad ----------------
@router.delete("/{ad_id}")
def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    # Delete image from S3
    try:
        delete_file_from_s3(ad.image_path)
    except:
        pass

    db.delete(ad)
    db.commit()
    return {"detail": "Ad deleted successfully"}