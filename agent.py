import os
import re
import time
import urllib.request
import json
import feedparser
import yfinance as yf
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

HOLDINGS = [
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT", "AAPL",
    "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD", "META",
    "GOOGL", "EQIX", "PLTR", "TSM", "VOO"
]

WATCHLIST = ["USAR", "ISRG", "LMT", "TMO", "MU", "WDC", "CSCO", "VRT", "AVGO"]

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"

def get_financial_url(ticker):
    return f"https://finance.yahoo.com/quote/{ticker}/"

def extract_thumbnail(entry, category="general"):
    if "media_thumbnail" in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get("url", "")
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", ""):
                return enc.get("href", "")
    
    content_html = ""
    if "content" in entry and entry.content:
        content_html = entry.content[0].get("value", "")
    elif "description" in entry:
        content_html = entry.description or ""
    
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_html)
    if img_match:
        return img_match.group(1)

    if category == "padres":
        return PADRES_LOGO
    elif category == "mlb":
        return MLB_LOGO
    elif category == "ai":
        return TECH_LOGO
    return ""

def fetch_rss_items(url, limit=10, category="general"):
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        feed_data = urllib.request.urlopen(req, timeout=8).read()
        feed = feedparser.parse(feed_data)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "#")
            img = extract_thumbnail(entry, category=category)
            if title:
                items.append({"title": title, "link": link, "image": img})
    except Exception as e:
        print(f"Notice fetching RSS {url}: {e}")
    return items

def get_live_padres_roster_keywords():
    keywords = {"padres", "san diego", "san diego padres", "friars", "petco park", "shildt", "preller"}
    try:
        url = "https://statsapi.mlb.com/api/v1/teams/135/roster/fullRoster"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=6)
        data = json.loads(resp.read().decode('utf-8'))
        for member in data.get("roster", []):
            person = member.get("person", {})
            full_name = person.get("fullName", "").lower().strip()
            if full_name:
                keywords.add(full_name)
                parts = full_name.split()
                for p in parts:
                    if len(p) > 3:
                        keywords.add(p)
    except Exception as e:
        print(f"Notice dynamically fetching live roster: {e}")
        keywords.update(["morejon", "king", "france", "tatis", "machado", "merrill", "bogaerts", "cease", "musgrove", "suarez", "arApplicationez", "cronenworth"])
    return keywords

def fetch_padres_and_mlb_stories():
    padres_keywords = get_live_padres_roster_keywords()
    padres_stories = []
    seen_padres_titles = set()
    mlb_stories = []
    seen_mlb_titles = set()

    def is_padres_match(title_str):
        tl = title_str.lower()
        return any(k in tl for k in padres_keywords)

    # 1. MLB.com Front Page News Feed & Official Headlines
    try:
        req = urllib.request.Request("https://www.mlb.com/feeds/news/rss.xml", headers={'User-Agent': 'Mozilla/5.0'})
        feed_data = urllib.request.urlopen(req, timeout=8).read()
        mlb_feed = feedparser.parse(feed_data)
        
        for entry in mlb_feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "https://www.mlb.com")
            
            if is_padres_match(title):
                if title not in seen_padres_titles:
                    seen_padres_titles.add(title)
                    padres_stories.append({"title": title, "link": link, "image": PADRES_LOGO})
            else:
                if title not in seen_mlb_titles:
                    seen_mlb_titles.add(title)
                    mlb_stories.append({"title": title, "link": link, "image": MLB_LOGO})
    except Exception as e:
        print(f"MLB.com feed error: {e}")

    # Official MLB Team News API for beat coverage
    try:
        api_url = "https://statsapi.mlb.com/api/v1/teams/135?hydrate=news(limit=10)"
        req_api = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req_api, timeout=6)
        data = json.loads(resp.read().decode('utf-8'))
        articles = data.get("teams", [{}])[0].get("news", {}).get("articles", [])
        for art in articles:
            t = art.get("headline") or art.get("title") or ""
            link = art.get("url") or "https://www.mlb.com/padres/news"
            if t and t not in seen_padres_titles and len(padres_stories) < 5:
                seen_padres_titles.add(t)
                padres_stories.append({"title": t, "link": link, "image": PADRES_LOGO})
    except Exception as e:
        print(f"MLB team news API error: {e}")

    # 2. MLB Trade Rumors Padres (top 2 fallback)
    if len(padres_stories) < 5:
        traderumors_padres = fetch_rss_items("https://www.mlbtraderumors.com/san-diego-padres/feed", limit=4, category="padres")
        added_tr = 0
        for item in traderumors_padres:
            if item["title"] not in seen_padres_titles:
                seen_padres_titles.add(item["title"])
                padres_stories.append(item)
                added_tr += 1
                if added_tr >= 2 or len(padres_stories) >= 5:
                    break

    # 3. Gaslamp Ball backfill to reach 5 items
    if len(padres_stories) < 5:
        gaslamp = fetch_rss_items("https://www.gaslampball.com/rss/index.xml", limit=5, category="padres")
        for item in gaslamp:
            if item["title"] not in seen_padres_titles:
                seen_padres_titles.add(item["title"])
                padres_stories.append(item)
                if len(padres_stories) >= 5:
                    break

    # Fill general MLB stories if needed
    if len(mlb_stories) < 5:
        supp_mlb = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=8, category="mlb")
        for item in supp_mlb:
            if not is_padres_match(item["title"]) and item["title"] not in seen_mlb_titles:
                seen_mlb_titles.add(item["title"])
                mlb_stories.append(item)
                if len(mlb_stories) >= 5:
                    break

    return padres_stories[:5], mlb_stories[:5]

def get_sorted_ticker_quotes(tickers):
    data_list = []
    for ticker in tickers:
        url = get_financial_url(ticker)
        try:
            t = yf.Ticker(ticker)
            fast_info = getattr(t, "fast_info", None)
            price = None
            pct_change = 0.0
            
            if fast_info:
                price = fast_info.last_price
                prev = fast_info.previous_close
                if price and prev:
                    pct_change = ((price - prev) / prev) * 100
            
            if price is None:
                hist = t.history(period="2d")
                if len(hist) >= 1:
                    price = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        prev = float(hist["Close"].iloc[-2])
                        pct_change = ((price - prev) / prev) * 100

            if price is not None:
                data_list.append({
                    "ticker": ticker,
                    "price": f"${price:,.2f}" if price >= 1 else f"${price:,.4f}",
                    "pct_num": pct_change,
                    "pct": f"{pct_change:+.2f}%",
                    "positive": pct_change >= 0,
                    "url": url
                })
            else:
                data_list.append({
                    "ticker": ticker,
                    "price": "N/A",
                    "pct_num": 0.0,
                    "pct": "0.00%",
                    "positive": True,
                    "url": url
                })
        except Exception:
            data_list.append({
                "ticker": ticker,
                "price": "N/A",
                "pct_num": 0.0,
                "pct": "0.00%",
                "positive": True,
                "url": url
            })

    data_list.sort(key=lambda x: x["pct_num"], reverse=True)
    return data_list

def get_available_flash_models():
    preferred = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name.lower() and not name.endswith("-exp"):
                preferred.append(name)
    except Exception as e:
        print(f"Notice listing models: {e}")
    if not preferred:
        preferred = ["gemini-3.8-flash", "gemini-3-flash-preview"]
    return preferred

def run_agent():
    print("Collecting news feeds...")
    world_news = fetch_rss_items("https://feeds.bbci.co.uk/news/world/rss.xml", limit=5, category="general")
    
    sd_local_news = fetch_rss_items("https://www.cbs8.com/feeds/syndication/rss/news/local", limit=6, category="general")
    if len(sd_local_news) < 5:
        sd_local_news += fetch_rss_items("https://www.nbcsandiego.com/?rss=y", limit=6, category="general")
    sd_local_news = sd_local_news[:5]

    padres_articles, other_mlb = fetch_padres_and_mlb_stories()

    rundown_ai = fetch_rss_items("https://rss.beehiiv.com/feeds/2b761741-2c06-4444-a093-6c845b4129b0.xml", limit=4, category="ai")
    tc_ai = fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=4, category="ai")
    msft_news = fetch_rss_items("https://blogs.microsoft.com/feed/", limit=4, category="ai")
    apple_news = fetch_rss_items("https://9to5mac.com/feed/", limit=4, category="ai")
    ars_tech = fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=4, category="ai")

    all_ai_tech = rundown_ai + tc_ai + msft_news + apple_news + ars_tech
    seen_tech = set()
    ai_tech_items = []
    for item in all_ai_tech:
        if item["title"] not in seen_tech:
            seen_tech.add(item["title"])
            if not item.get("image"):
                item["image"] = TECH_LOGO
            ai_tech_items.append(item)
        if len(ai_tech_items) >= 10:
            break

    print("Fetching sorted market quotes...")
    sorted_holdings = get_sorted_ticker_quotes(HOLDINGS)
    sorted_watchlist = get_sorted_ticker_quotes(WATCHLIST)

    js
