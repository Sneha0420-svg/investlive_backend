from fastapi import APIRouter
from dotenv import load_dotenv
import requests
import os

load_dotenv()

router = APIRouter(prefix="/live-news", tags=["Live News"])

NEWS_API_KEY = os.getenv("NEWS_API_KEY")


@router.get("/market-news")
def get_market_news():

    url = "https://newsapi.org/v2/top-headlines"

    params = {
        "category": "business",
        "country": "in",
        "apiKey": NEWS_API_KEY,
    }

    response = requests.get(url, params=params)

    print("STATUS CODE:", response.status_code)

    data = response.json()

    print("FULL RESPONSE:", data)

    articles = data.get("articles", [])

    cleaned_news = []

    for index, article in enumerate(articles):

        cleaned_news.append({
            "id": index + 1,
            "title": article.get("title"),
            "description": article.get("description"),
            "content": article.get("content"),
            "image": article.get("urlToImage"),
            "url": article.get("url"),
            "source": article.get("source", {}).get("name"),
            "publishedAt": article.get("publishedAt"),
        })

    return cleaned_news