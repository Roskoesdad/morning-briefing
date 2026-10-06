import os
import time
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

def fetch_rss_headlines(url, limit=8):
    try:
        feed = feedparser.parse(url)
        return [entry.title for entry in feed.entries[:limit]]
    except Exception:
        return []

def collect_market_news(tickers):
    news_items = []
    for ticker in tickers[:8]:
        try:
            t = yf.Ticker(ticker)
            for item in t.news[:2]:
                title = item.get("title")
                if title:
                    news_items.append(f"{ticker}: {title}")
        except Exception:
            continue
    return news_items

def get_available_flash_models():
    """Dynamically queries the API for supported models available to your key."""
    preferred = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            # Prioritize fast, free flash variants
            if "flash" in name.lower() and not name.endswith("-exp"):
                preferred.append(name)
    except Exception as e:
        print(f"Notice listing models: {e}")
    
    # Fallback to standard names if list query returns empty
    if not preferred:
        preferred = ["gemini-3.8-flash", "gemini-3-flash-preview"]
    return preferred

def run_agent():
    print("Collecting news feeds...")
    world_news = fetch_rss_headlines("https://feeds.bbci.co.uk/news/world/rss.xml")
    sports_news = fetch_rss_headlines("https://www.espn.com/espn/rss/news")
    tech_news = fetch_rss_headlines("https://feeds.arstechnica.com/arstechnica/technologylab")
    stock_news = collect_market_news(HOLDINGS + WATCHLIST)

    prompt = f"""
You are an automated morning executive intelligence system.
Build a clean, modern, dark-mode single-page HTML dashboard with embedded CSS.

Data Gathered:
- World News: {world_news}
- Sports News: {sports_news}
- AI & Tech News: {tech_news}
- Market News: {stock_news}

Tracked Holdings: {HOLDINGS}
Watchlist for Purchases: {WATCHLIST}

Layout Instructions:
- Modern dark slate aesthetic (background: #0f172a, card background: #1e293b, text: #f8fafc, accent: #38bdf8).
- Section 1: Top 10 World Headlines (concise single bullet points).
- Section 2: Top 10 Sports Headlines.
- Section 3: AI & Tech Breakthroughs.
- Section 4: Portfolio Pulse (highlight movements or news impacting holdings).
- Section 5: Watchlist Catalyst Radar. For the watchlist stocks (USAR, ISRG, LMT, TMO, MU, WDC, CSCO, VRT, AVGO), highlight any significant catalyst (contracts, demand, earnings surprises). Explain why it warrants immediate attention today.

Return ONLY clean HTML code starting with <!DOCTYPE html> and ending with </html>. Do not include markdown code ticks.
"""

    models_to_try = get_available_flash_models()
    print(f"Discovered candidate models: {models_to_try}")

    response = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                print(f"Calling {model_name} (Attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    print(f"Success with model {model_name}!")
                    break
            except Exception as err:
                print(f"Retry notice on {model_name}: {err}")
                time.sleep(6 * (attempt + 1))
        if response and response.text:
            break

    if not response or not response.text:
        raise RuntimeError("Could not complete generation due to upstream API capacity limits.")

    clean_html = response.text.replace("```html", "").replace("```", "").strip()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(clean_html)
    print("index.html written successfully!")

if __name__ == "__main__":
    run_agent()
