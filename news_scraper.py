import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")


def get_from_cryptopanic(limit: int = 3) -> list[str]:
    if not CRYPTOPANIC_API_KEY:
        return []
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&currencies=BTC&public=true"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return [post["title"] for post in data.get("results", [])[:limit]]
    except Exception as e:
        print(f"[CryptoPanic] Error: {e}")
        return []


def get_from_cointelegraph(limit: int = 3) -> list[str]:
    url = "https://cointelegraph.com/tags/bitcoin"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("a.post-card-inline__title-link")
        return [a.get_text(strip=True) for a in articles[:limit]]
    except Exception as e:
        print(f"[Cointelegraph] Error: {e}")
        return []


def get_from_cryptonews(limit: int = 3) -> list[str]:
    url = "https://cryptonews.com/news/bitcoin-news/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("div.article__title a")
        return [a.get_text(strip=True) for a in articles[:limit]]
    except Exception as e:
        print(f"[CryptoNews] Error: {e}")
        return []


def get_bitcoin_headlines(limit: int = 5) -> list[str]:
    headlines = []
    # headlines += get_from_cryptopanic(limit)
    headlines += get_from_cointelegraph(limit)
    headlines += get_from_cryptonews(limit)
    return headlines[:limit]
