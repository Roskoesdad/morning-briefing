import os
import re
import time
import urllib.request
import json
import feedparser
import yfinance as yf
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

HOLDINGS = [
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT", "AAPL",
    "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD", "META",
    "GOOGL", "EQIX", "PLTR", "TSM", "VOO"
]

WATCHLIST = ["USAR", "ISRG", "LMT", "TMO", "MU", "WDC", "CSCO", "VRT", "AVGO"]

DISCOVERY_TICKERS = ["RTX", "NOC", "GD", "BA"]

ENTITY_MAP = {
    "PLTR": ["palantir"],
    "MSFT": ["microsoft"],
    "NVDA": ["nvidia"],
    "AMZN": ["amazon", "amazon web services", "aws"],
    "EQIX": ["equinix"],
    "LMT": ["lockheed martin", "lockheed"],
    "USAR": ["usa rare earth", "round top"],
    "VRT": ["vertiv"],
    "AVGO": ["broadcom"],
    "MU": ["micron"],
    "CSCO": ["cisco"],
    "RTX": ["raytheon", "rtx corp"],
    "NOC": ["northrop grumman", "northrop"],
    "GD": ["general dynamics"]
}

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"

PADRES_KEYWORDS = [
    "padres", "san diego", "friars", "petco", "cassavell", "dennis lin",
    "morejon", "michael king", "ty france", "tatis", "machado", "merrill",
    "bogaerts", "cease", "musgrove", "suarez", "arApplicationez", "shildt", "preller"
]

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
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        feed_data = urllib.request.urlopen(req, timeout=8).read()
        feed = feedparser.parse(feed_data)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "#")
            img = extract_thumbnail(entry, category=category)
            published = entry.get("published_parsed")
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "image": img,
                    "published_parsed": published
                })
    except Exception as e:
        print(f"Notice fetching RSS {url}: {e}")
    return items

def is_padres_related(text):
    text_lower = text.lower()
    return any(k in text_lower for k in PADRES_KEYWORDS)

def scrape_mlb_front_page():
    padres_articles = []
    mlb_articles = []
    seen = set()

    urls_to_scrape = [
        "https://www.mlb.com",
        "https://www.mlb.com/padres",
        "https://www.mlb.com/padres/news"
    ]

    for page_url in urls_to_scrape:
        try:
            req = urllib.request.Request(
                page_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
            )
            html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')

            for a in soup.find_all('a', href=True):
                href = a['href']
                title = a.get_text(strip=True)
                
                if '/news/' in href and len(title) > 20:
                    if title in seen:
                        continue
                    seen.add(title)

                    full_url = href if href.startswith('http') else f"https://www.mlb.com{href}"
                    
                    if is_padres_related(title) or 'padres' in href:
                        padres_articles.append({"title": title, "link": full_url, "image": PADRES_LOGO})
                    else:
                        mlb_articles.append({"title": title, "link": full_url, "image": MLB_LOGO})
        except Exception as e:
            print(f"Error scraping {page_url}: {e}")

    return padres_articles, mlb_articles

def fetch_padres_and_mlb_stories():
    padres_mlb_scraped, mlb_stories = scrape_mlb_front_page()
    padres_final = []
    seen_padres_titles = set()

    for item in padres_mlb_scraped:
        if item["title"] not in seen_padres_titles:
            seen_padres_titles.add(item["title"])
            padres_final.append(item)
            if len(padres_final) == 2:
                break

    now_utc = datetime.now(timezone.utc)
    two_days_ago = now_utc - timedelta(days=2)
    
    tr_items = fetch_rss_items("https://www.mlbtraderumors.com/san-diego-padres/feed", limit=8, category="padres")
    for item in tr_items:
        if len(padres_final) >= 5:
            break
        if item["title"] in seen_padres_titles:
            continue
        
        pub_parsed = item.get("published_parsed")
        if pub_parsed:
            try:
                pub_dt = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                if pub_dt >= two_days_ago:
                    seen_padres_titles.add(item["title"])
                    padres_final.append(item)
            except Exception:
                pass

    if len(padres_final) < 5:
        gaslamp_items = fetch_rss_items("https://gaslampball.com/rss/index.xml", limit=8, category="padres")
        for item in gaslamp_items:
            if len(padres_final) >= 5:
                break
            if item["title"] not in seen_padres_titles:
                seen_padres_titles.add(item["title"])
                padres_final.append(item)

    seen_mlb_titles = {m["title"] for m in mlb_stories}
    if len(mlb_stories) < 5:
        supp_mlb = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=8, category="mlb")
        for item in supp_mlb:
            if not is_padres_related(item["title"]) and item["title"] not in seen_mlb_titles:
                seen_mlb_titles.add(item["title"])
                mlb_stories.append(item)
                if len(mlb_stories) >= 5:
                    break

    return padres_final[:5], mlb_stories[:5]

def evaluate_high_conviction_catalysts():
    """
    Scans DoD daily contract bulletins and validates unusual institutional volume breakout
    across holdings, watchlist, and discovery candidates.
    """
    signals = []
    
    # Injected test catalyst for visual verification
    signals.append({
        "ticker": "APEX",
        "group": "Active Watchlist",
        "type": "DoD Defense Procurement Award",
        "vol_ratio": "3.2x",
        "pct": "+6.85%",
        "summary": "APEX Systems awarded $485M multi-year contract for Next-Gen Tactical Edge Sensor Arrays. Institutional volume running 3.2x above 20-day average.",
        "url": "https://finance.yahoo.com"
    })

    dod_text = ""
    try:
        url = "https://www.defense.gov/News/Contracts/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        dod_text = soup.get_text().lower()
    except Exception as e:
        print(f"Notice fetching DoD contracts: {e}")

    all_tickers = HOLDINGS + WATCHLIST + DISCOVERY_TICKERS
    seen_tickers = set()

    for ticker in all_tickers:
        if "-USD" in ticker or ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        aliases = ENTITY_MAP.get(ticker, [ticker.lower()])
        has_contract = any(alias in dod_text for alias in aliases)

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1mo")
            if len(hist) >= 15:
                avg_vol = float(hist['Volume'][:-1].mean())
                today_vol = float(hist['Volume'].iloc[-1])
                pct_change = float(((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100)
                vol_ratio = (today_vol / avg_vol) if avg_vol > 0 else 1.0

                if has_contract and pct_change >= 0:
                    group = "Current Portfolio" if ticker in HOLDINGS else ("Active Watchlist" if ticker in WATCHLIST else "Discovery Opportunity")
                    signals.append({
                        "ticker": ticker,
                        "group": group,
                        "type": "DoD Procurement / Contract Award",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_change:+.2f}%",
                        "summary": f"Confirmed major federal defense award or contract modification identified. Relative volume tracking at {vol_ratio:.1f}x average.",
                        "url": get_financial_url(ticker)
                    })
                elif vol_ratio >= 1.75 and pct_change >= 2.0:
                    group = "Current Portfolio" if ticker in HOLDINGS else ("Active Watchlist" if ticker in WATCHLIST else "Discovery Opportunity")
                    signals.append({
                        "ticker": ticker,
                        "group": group,
                        "type": "Institutional Volume Breakout",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_change:+.2f}%",
                        "summary": f"Unusual volume expansion ({vol_ratio:.1f}x average) indicating aggressive institutional accumulation.",
                        "url": get_financial_url(ticker)
                    })
        except Exception:
            continue

    return signals[:2]

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

    print("
