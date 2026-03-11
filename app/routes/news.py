import io
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.news import News
from app.schemas.news import NewsOut
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3, get_s3_file_url

router = APIRouter(prefix="/news", tags=["News"])

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- HELPER --------------------
def generate_s3_key(filename: str):
    """
    Create a unique S3 key in the 'news/' folder
    """
    return f"news/{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{filename}"

# -------------------- CREATE NEWS --------------------
@router.post("/", response_model=NewsOut)
async def create_news(
    source: str = Form(...),
    title: str = Form(None),
    content: str = Form(...),
    news_type: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    image_s3_key = None
    if image:
        file_bytes = await image.read()
        image_s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(image.filename))

    db_news = News(
        source=source,
        title=title,
        content=content,
        news_type=news_type,
        news_date=datetime.utcnow(),
        image_path=image_s3_key
    )

    db.add(db_news)
    db.commit()
    db.refresh(db_news)

    return {
        "id": db_news.id,
        "source": db_news.source,
        "title": db_news.title,
        "content": db_news.content,
        "news_type": db_news.news_type,
        "news_date": db_news.news_date,
        "image_path": get_s3_file_url(db_news.image_path) if db_news.image_path else None
    }

# -------------------- GET ALL NEWS --------------------
@router.get("/", response_model=List[NewsOut])
def get_news(db: Session = Depends(get_db)):
    news_list = db.query(News).order_by(News.news_date.desc()).all()
    return [
        {
            "id": n.id,
            "source": n.source,
            "title": n.title,
            "content": n.content,
            "news_type": n.news_type,
            "news_date": n.news_date,
            "image_path": get_s3_file_url(n.image_path) if n.image_path else None
        }
        for n in news_list
    ]

# -------------------- GET SINGLE NEWS --------------------
@router.get("/{news_id}", response_model=NewsOut)
def get_single_news(news_id: int, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    return {
        "id": news.id,
        "source": news.source,
        "title": news.title,
        "content": news.content,
        "news_type": news.news_type,
        "news_date": news.news_date,
        "image_path": get_s3_file_url(news.image_path) if news.image_path else None
    }

# -------------------- UPDATE NEWS --------------------
@router.put("/{news_id}", response_model=NewsOut)
async def update_news(
    news_id: int,
    source: str = Form(...),
    title: str = Form(None),
    content: str = Form(...),
    news_type: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    # Replace image if provided
    if image:
        if news.image_path:
            delete_file_from_s3(news.image_path)
        file_bytes = await image.read()
        news.image_path = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(image.filename))

    # Update other fields
    news.source = source
    news.title = title
    news.content = content
    news.news_type = news_type
    news.news_date = datetime.utcnow()

    db.commit()
    db.refresh(news)

    return {
        "id": news.id,
        "source": news.source,
        "title": news.title,
        "content": news.content,
        "news_type": news.news_type,
        "news_date": news.news_date,
        "image_path": get_s3_file_url(news.image_path) if news.image_path else None
    }

# -------------------- DELETE NEWS --------------------
@router.delete("/{news_id}")
def delete_news(news_id: int, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    if news.image_path:
        delete_file_from_s3(news.image_path)

    db.delete(news)
    db.commit()
    return {"detail": "News deleted successfully"}

# -------------------- DOWNLOAD IMAGE --------------------
@router.get("/image/{news_id}")
def download_news_image(news_id: int, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news or not news.image_path:
        raise HTTPException(status_code=404, detail="Image not found")

    file_stream = get_file_stream_from_s3(news.image_path)
    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{news.id}.jpg"'}
    )