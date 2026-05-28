from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
import requests
import os
import time
from datetime import datetime

load_dotenv()

router = APIRouter(
    prefix="/live-news",
    tags=["Live News"]
)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


@router.get("/market-news")
def get_market_news():

    try:

        if not FINNHUB_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="FINNHUB_API_KEY missing"
            )

        final_news = []

        news_configs = [
            {
                "category": "general",
                "label": "business"
            },
            {
                "category": "forex",
                "label": "forex"
            },
            {
                "category": "crypto",
                "label": "crypto"
            },
            {
                "category": "merger",
                "label": "merger"
            }
        ]

        news_id = 1

        for item in news_configs:

            url = "https://finnhub.io/api/v1/news"

            params = {
                "category": item["category"],
                "token": FINNHUB_API_KEY
            }

            response = requests.get(
                url,
                params=params,
                timeout=20
            )

            print(f"{item['category']} STATUS:", response.status_code)

            if response.status_code != 200:
                continue

            articles = response.json()

            for article in articles[:10]:

                # REMOVE EMPTY TITLES
                if not article.get("headline"):
                    continue

                # CLEAN CONTENT
                summary = article.get("summary") or ""

                # REMOVE HTML TAGS IF ANY
                summary = summary.replace("<p>", "")
                summary = summary.replace("</p>", "")
                summary = summary.replace("\n", " ")

                final_news.append({
                    "id": news_id,
                    "title": article.get("headline"),
                    "description": summary[:300],
                    "content": summary,
                    "image": article.get("image"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "category": item["label"],
                    "publishedAt": datetime.fromtimestamp(
                        article.get("datetime", time.time())
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "related": article.get("related")
                })

                news_id += 1

        # REMOVE DUPLICATES
        unique_news = []
        seen_titles = set()

        for news in final_news:

            title = news["title"]

            if title not in seen_titles:
                unique_news.append(news)
                seen_titles.add(title)

        # SORT LATEST FIRST
        unique_news.sort(
            key=lambda x: x["publishedAt"],
            reverse=True
        )

        return {
            "status": "success",
            "total": len(unique_news),
            "data": unique_news
        }

    except Exception as e:

        import traceback
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )