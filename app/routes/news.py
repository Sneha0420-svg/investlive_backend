from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
import shutil
import os
from typing import List
from datetime import datetime
from fastapi.staticfiles import StaticFiles

from app.database import SessionLocal
from app.models.news import News
from app.schemas.news import NewsOut

router = APIRouter(prefix="/news", tags=["News"])

# Upload directory
UPLOAD_DIR = "uploads/news"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mount uploads (ensure this is also in main.py)
# app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ---------------- CREATE NEWS ----------------
@router.post("/", response_model=NewsOut)
def create_news(
    source: str = Form(...),
    heading: str = Form(...),
    title: str = Form(None),
    content: str = Form(...),
    news_type: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    request: Request = None,  # ✅ Must be after all defaults
):
    image_path = None
    if image:
        file_location = os.path.join(UPLOAD_DIR, image.filename)
        with open(file_location, "wb") as f:
            shutil.copyfileobj(image.file, f)
        image_path = file_location

    db_news = News(
        source=source,
        heading=heading,
        title=title,
        content=content,
        news_type=news_type,
        news_date=datetime.utcnow(),
        image_path=image_path,
    )

    db.add(db_news)
    db.commit()
    db.refresh(db_news)

    # Return image URL
    image_url = (
        f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/uploads/news/{os.path.basename(image_path)}"
        if image_path else None
    )

    return {
        "id": db_news.id,
        "source": db_news.source,
        "heading": db_news.heading,
        "title": db_news.title,
        "content": db_news.content,
        "news_type": db_news.news_type,
        "news_date": db_news.news_date,
        "image_path": image_url,
    }

# ---------------- GET ALL NEWS ----------------
@router.get("/", response_model=List[NewsOut])
def get_news(db: Session = Depends(get_db), request: Request = None):
    news_list = db.query(News).order_by(News.news_date.desc()).all()
    result = []
    for n in news_list:
        image_url = (
            f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/uploads/news/{os.path.basename(n.image_path)}"
            if n.image_path else None
        )
        result.append({
            "id": n.id,
            "source": n.source,
            "heading": n.heading,
            "title": n.title,
            "content": n.content,
            "news_type": n.news_type,
            "news_date": n.news_date,
            "image_path": image_url,
        })
    return result

# ---------------- GET SINGLE NEWS ----------------
@router.get("/{news_id}", response_model=NewsOut)
def get_single_news(news_id: int, db: Session = Depends(get_db), request: Request = None):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    image_url = (
        f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/uploads/news/{os.path.basename(news.image_path)}"
        if news.image_path else None
    )

    return {
        "id": news.id,
        "source": news.source,
        "heading": news.heading,
        "title": news.title,
        "content": news.content,
        "news_type": news.news_type,
        "news_date": news.news_date,
        "image_path": image_url,
    }

# ---------------- UPDATE NEWS ----------------
@router.put("/{news_id}", response_model=NewsOut)
def update_news(
    news_id: int,
    source: str = Form(...),
    heading: str = Form(...),
    title: str = Form(None),
    content: str = Form(...),
    news_type: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    # Update image if provided
    if image:
        file_location = os.path.join(UPLOAD_DIR, image.filename)
        with open(file_location, "wb") as f:
            shutil.copyfileobj(image.file, f)
        news.image_path = file_location

    # Update other fields
    news.source = source
    news.heading = heading
    news.title = title
    news.content = content
    news.news_type = news_type
    news.news_date = datetime.utcnow()  # always update timestamp

    db.commit()
    db.refresh(news)

    image_url = (
        f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/uploads/news/{os.path.basename(news.image_path)}"
        if news.image_path else None
    )

    return {
        "id": news.id,
        "source": news.source,
        "heading": news.heading,
        "title": news.title,
        "content": news.content,
        "news_type": news.news_type,
        "news_date": news.news_date,
        "image_path": image_url,
    }

# ---------------- DELETE NEWS ----------------
@router.delete("/{news_id}")
def delete_news(news_id: int, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    if news.image_path and os.path.exists(news.image_path):
        os.remove(news.image_path)
    db.delete(news)
    db.commit()
    return {"detail": "News deleted successfully"}
