import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.ads import Ad, VideoAd
from app.schemas.ads import AdResponse, VideoAdResponse
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_s3_file_url

router = APIRouter(tags=["ads"])
# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Create Ad ----------------
@router.post("/ads/", response_model=AdResponse)
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
@router.get("/ads/", response_model=list[AdResponse])
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
@router.put("/ads/{ad_id}", response_model=AdResponse)
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
@router.delete("/ads/{ad_id}")
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


# ============================================================
# VIDEO ADS
# ============================================================

# ---------------- Upload Video ----------------

@router.post("/videos", response_model=VideoAdResponse)
async def upload_video(
    video: UploadFile = File(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    # At least one file is required
    if not video and not image:
        raise HTTPException(
            status_code=400,
            detail="Please upload at least a video or image"
        )

    # Allowed video formats
    allowed_video_extensions = (
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
    )

    # Allowed image formats
    allowed_image_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    )

    video_s3_key = None
    image_s3_key = None

    # -------------------------
    # Upload Video if provided
    # -------------------------
    if video:
        if not video.filename:
            raise HTTPException(
                status_code=400,
                detail="Video filename is required"
            )

        if not video.filename.lower().endswith(
            allowed_video_extensions
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid video file type"
            )

        try:
            video_s3_key = upload_file_to_s3(
                file_obj=video.file,
                folder="videos",
                filename=f"{uuid.uuid4()}_{video.filename}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"S3 video upload failed: {e}"
            )

    # -------------------------
    # Upload Image if provided
    # -------------------------
    if image:
        if not image.filename:
            raise HTTPException(
                status_code=400,
                detail="Image filename is required"
            )

        if not image.filename.lower().endswith(
            allowed_image_extensions
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid image file type"
            )

        try:
            image_s3_key = upload_file_to_s3(
                file_obj=image.file,
                folder="video-images",
                filename=f"{uuid.uuid4()}_{image.filename}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"S3 image upload failed: {e}"
            )

    # -------------------------
    # Save to database
    # -------------------------
    video_ad = VideoAd(
        video_path=video_s3_key,
        image_path=image_s3_key,
    )

    db.add(video_ad)
    db.commit()
    db.refresh(video_ad)

    # -------------------------
    # Response
    # -------------------------
    return VideoAdResponse(
        id=video_ad.id,
        video_url=(
            get_s3_file_url(video_ad.video_path)
            if video_ad.video_path
            else None
        ),
        image_url=(
            get_s3_file_url(video_ad.image_path)
            if video_ad.image_path
            else None
        ),
        uploaded_at=video_ad.uploaded_at,
    )



# ---------------- Get Videos / Images ----------------

@router.get("/videos", response_model=list[VideoAdResponse])
def get_videos(
    db: Session = Depends(get_db),
):
    videos = (
        db.query(VideoAd)
        .order_by(VideoAd.uploaded_at.desc())
        .all()
    )

    return [
        VideoAdResponse(
            id=v.id,

            video_url=(
                get_s3_file_url(v.video_path)
                if v.video_path
                else None
            ),

            image_url=(
                get_s3_file_url(v.image_path)
                if v.image_path
                else None
            ),

            uploaded_at=v.uploaded_at,
        )
        for v in videos
    ]


# ---------------- Delete Video / Image ----------------

@router.delete("/videos/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
):
    video_ad = (
        db.query(VideoAd)
        .filter(VideoAd.id == video_id)
        .first()
    )

    if not video_ad:
        raise HTTPException(
            status_code=404,
            detail="Video/Image not found"
        )

    # -------------------------
    # Delete Video from S3
    # -------------------------
    if video_ad.video_path:
        try:
            delete_file_from_s3(video_ad.video_path)
        except Exception:
            pass

    # -------------------------
    # Delete Image from S3
    # -------------------------
    if video_ad.image_path:
        try:
            delete_file_from_s3(video_ad.image_path)
        except Exception:
            pass

    # -------------------------
    # Delete Database Record
    # -------------------------
    db.delete(video_ad)
    db.commit()

    return {
        "detail": "Video/Image deleted successfully"
    }
