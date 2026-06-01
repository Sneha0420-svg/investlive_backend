from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import requests
import os
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.news import MarketNews

load_dotenv()

router = APIRouter(
    prefix="/live-news",
    tags=["Live News"]
)

API_KEY = os.getenv("MARKETAUX_API_KEY")


# ---------------- DB ---------------- #

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- CONFIG ---------------- #
NEWS_CONFIGS = [
    {
        "label": "market",
        "query": "NSE OR BSE OR Nifty OR Sensex"
    },
    {
        "label": "company",
        "query": "business OR corporate OR earnings"
    },
    {
        "label": "crypto",
        "query": "bitcoin OR cryptocurrency"
    },
    {
        "label": "banking",
        "query": "demat OR CDSL OR NSDL OR stock broker OR trading account"
    },
    {
        "label": "forex",
        "query": "forex OR USD INR"
    }
]
# ---------------- SYNC CONTROL ---------------- #

LAST_SYNC_TIMES = {
    "market": None,
    "company": None,
    "banking": None,
    "crypto": None,
    "forex": None,
}

SYNC_INTERVAL = timedelta(hours=24)


def should_sync(news_type: str):

    last_sync = LAST_SYNC_TIMES.get(news_type)

    if last_sync is None:
        return True

    return datetime.utcnow() - last_sync > SYNC_INTERVAL


def update_sync_time(news_type: str):

    LAST_SYNC_TIMES[news_type] = datetime.utcnow()


# ---------------- COMMON SYNC FUNCTION ---------------- #

def sync_news_by_type(
    news_type: str,
    db: Session
):

    config = next(
        (
            item for item in NEWS_CONFIGS
            if item["label"] == news_type
        ),
        None
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Invalid news type"
        )

    # DELETE OLD CATEGORY NEWS
    (
        db.query(MarketNews)
        .filter(MarketNews.category == news_type)
        .delete()
    )

    db.commit()

    url = "https://newsdata.io/api/1/latest"

    params = {
        "apikey": API_KEY,
        "q": config["query"],
        "language": "en",
        "country": "in",
        "category": "business"
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    data = response.json()

    print(data)

    if response.status_code != 200:

        raise HTTPException(
            status_code=response.status_code,
            detail=data
        )

    articles = data.get("results", [])

    inserted = 0

    for article in articles:

        try:

            title = article.get("title")

            if not title:
                continue

            description = article.get("description") or ""

            content = article.get("content") or ""

            if (
                content == "ONLY AVAILABLE IN PAID PLANS"
                or not content
            ):
                content = description

            image = article.get("image_url") or ""

            news_url = article.get("link") or ""

            source = (
                article.get("source_name") or ""
            )[:255]

            keywords = article.get("keywords", [])

            related = (
                ", ".join(keywords)
                if keywords else ""
            )

            published_at = None

            try:

                pub_date = article.get("pubDate")

                if pub_date:

                    published_at = datetime.strptime(
                        pub_date,
                        "%Y-%m-%d %H:%M:%S"
                    )

            except Exception:
                pass

            news = MarketNews(
                title=title,
                description=description,
                content=content,
                image=image,
                url=news_url,
                source=source,
                category=news_type,
                published_at=published_at,
                related=related
            )

            db.add(news)

            inserted += 1

        except Exception as article_error:

            print(
                "ARTICLE ERROR:",
                str(article_error)
            )

            continue

    db.commit()

    # UPDATE LAST SYNC TIME
    update_sync_time(news_type)

    return {
        "status": "success",
        "category": news_type,
        "inserted": inserted
    }


# ---------------- MANUAL SYNC ROUTES ---------------- #

@router.get("/sync-market-news")
def sync_market_news(
    db: Session = Depends(get_db)
):
    return sync_news_by_type(
        "market",
        db
    )


@router.get("/sync-company-news")
def sync_company_news(
    db: Session = Depends(get_db)
):
    return sync_news_by_type(
        "company",
        db
    )


@router.get("/sync-crypto-news")
def sync_crypto_news(
    db: Session = Depends(get_db)
):
    return sync_news_by_type(
        "crypto",
        db
    )


@router.get("/sync-forex-news")
def sync_forex_news(
    db: Session = Depends(get_db)
):
    return sync_news_by_type(
        "forex",
        db
    )

@router.get("/sync-banking-news")
def sync_banking_news(
    db: Session = Depends(get_db)
):
    return sync_news_by_type(
        "banking",
        db
    )
# ---------------- GET ROUTES ---------------- #

@router.get("/market-news")
def get_market_news(
    db: Session = Depends(get_db)
):

    if should_sync("market"):
        sync_news_by_type("market", db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category == "market")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }


@router.get("/company-news")
def get_company_news(
    db: Session = Depends(get_db)
):

    if should_sync("company"):
        sync_news_by_type("company", db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category == "company")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }


@router.get("/crypto-news")
def get_crypto_news(
    db: Session = Depends(get_db)
):

    if should_sync("crypto"):
        sync_news_by_type("crypto", db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category == "crypto")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }


@router.get("/forex-news")
def get_forex_news(
    db: Session = Depends(get_db)
):

    if should_sync("forex"):
        sync_news_by_type("forex", db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category == "forex")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }
@router.get("/banking-news")
def get_banking_news(
    db: Session = Depends(get_db)
):

    if should_sync("banking"):
        sync_news_by_type("banking", db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category == "banking")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }

# ---------------- GET NEWS BY ID ---------------- #

@router.get("/news/{news_id}")
def get_news_by_id(
    news_id: int,
    db: Session = Depends(get_db)
):

    news = (
        db.query(MarketNews)
        .filter(MarketNews.id == news_id)
        .first()
    )

    if not news:

        raise HTTPException(
            status_code=404,
            detail="News not found"
        )

    return {
        "status": "success",
        "data": news
    }


# ---------------- ALL OTHER NEWS ---------------- #

@router.get("/all-other-news")
def get_all_other_news(
    db: Session = Depends(get_db)
):

    for category in ["company", "forex","banking"]:

        if should_sync(category):
            sync_news_by_type(category, db)

    data = (
        db.query(MarketNews)
        .filter(MarketNews.category != "market")
        .order_by(MarketNews.id.desc())
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }


# ---------------- COMBINED NEWS ---------------- #

@router.get("/combined-news")
def get_combined_news(
    db: Session = Depends(get_db)
):

    for category in ["company", "forex","banking"]:

        if should_sync(category):
            sync_news_by_type(category, db)

    categories = ["company", "forex", "banking"]

    combined_data = []

    for category in categories:

        news_items = (
            db.query(MarketNews)
            .filter(MarketNews.category == category)
            .order_by(MarketNews.id.desc())
            .all()
        )

        combined_data.extend(news_items)

    combined_data.sort(
        key=lambda x: x.id,
        reverse=True
    )

    return {
        "status": "success",
        "total": len(combined_data),
        "data": combined_data
    }
    
@router.get("/all-news")
def get_all_news(
    db: Session = Depends(get_db)
):

    categories = [
        "market",
        "company",
        "banking",
        "crypto",
        "forex"
    ]

    for category in categories:

        if should_sync(category):
            sync_news_by_type(
                category,
                db
            )

    data = (
        db.query(MarketNews)
        .order_by(
            MarketNews.published_at.desc()
        )
        .all()
    )

    return {
        "status": "success",
        "total": len(data),
        "data": data
    }