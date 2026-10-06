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

def fetch_rss_items(url, limit=10):
    """Fetches articles with title and link."""
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "#")
            if title:
                items.append({"title": title, "link": link})
    except Exception as e:
        print(f"Error fetching RSS {url}: {e}")
    return items

def get_ticker_quotes(tickers):
    """Pulls current prices and daily change for tickers."""
    quotes = {}
    for ticker in tickers:
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
                quotes[ticker] = {
                    "price": f"${price:,.2f}" if price >= 1 else f"${price:,.4f}",
                    "pct": f"{pct_change:+.2f}%",
                    "positive": pct_change >= 0
                }
            else:
                quotes[ticker] = {"price": "N/A", "pct": "0.00%", "positive": True}
        except Exception:
            quotes[ticker] = {"price": "N/A", "pct": "0.00%", "positive": True}
    return quotes

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
    world_news = fetch_rss_items("https://feeds.bbci.co.uk/news/world/rss.xml", limit=12)
    
    # MLB & Padres Rumors
    mlb_general = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=15)
    padres_articles = [item for item in mlb_general if "padres" in item["title"].lower()][:5]
    other_mlb = [item for item in mlb_general if "padres" not in item["title"].lower()][:5]

    # AI Breakthroughs (The Rundown AI style)
    ai_tech_items = (
        fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=8) +
        fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=6)
    )[:12]

    print("Fetching live market prices...")
    holdings_quotes = get_ticker_quotes(HOLDINGS)
    watchlist_quotes = get_ticker_quotes(WATCHLIST)

    prompt = f"""
You are an elite executive daily intelligence briefings generator.
Generate a complete, modern single-page HTML document with embedded CSS.

STYLING & PALETTE REQUIREMENTS:
- Modern LIGHT THEME.
- Background: #f8fafc (slate 50).
- Card / Module Background: #ffffff with subtle border: 1px solid #e2e8f0, box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05).
- Text primary: #0f172a, Text secondary: #475569.
- Accent / Brand: #0284c7 (sky blue) or #1e40af (navy).
- Positive gains: #16a34a (green), Negative losses: #dc2626 (red).
- Modern sans-serif font stack (system-ui, -apple-system, Segoe UI, Roboto, sans-serif).

DASHBOARD SECTIONS REQUIRED:

1. HEADER:
   - "Executive Morning Intelligence"
   - Subtitle: "Automated Daily Briefing & Threat/Opportunity Radar"
   - Timestamp badge showing current date and update cycle.

2. SECTION: "World News Top 10"
   - Exactly 10 concise bullet items based on World News data.
   - EVERY headline must be a clickable HTML link `<a href="..." target="_blank">Title</a>` taking the user to the original source.
   - Raw Data: {world_news}

3. SECTION: "Sports Desk: San Diego Padres & MLB"
   - Subsection A: "San Diego Padres Report" (Top 5 Padres-focused articles/trade rumors, plus a note on their upcoming game/series schedule). Link every title to its URL.
   - Subsection B: "League-Wide MLB Radar" (Next 5 top baseball stories across the league with clickable links).
   - Raw Padres Data: {padres_articles}
   - Raw MLB Data: {other_mlb}

4. SECTION: "AI & Tech Breakthroughs"
   - Modeled after "The Rundown AI" format: punchy executive summaries of the top 10 AI developments, breakthroughs, model releases, or enterprise moves.
   - Each item should have a clear bold takeaway and a clickable source link `<a href="..." target="_blank">Read more</a>`.
   - Raw AI Data: {ai_tech_items}

5. SECTION: "Portfolio Pulse"
   - Display a responsive grid of ticker chips showing the real-time prices and percentage changes for all owned assets:
     {holdings_quotes}
   - Add a brief 2-sentence macro analysis below the ticker grid.

6. SECTION: "Watchlist Catalyst Radar"
   - Display the ticker cards for target watchlist items with real-time price & % change:
     {watchlist_quotes}
   - For each target ticker (USAR, ISRG, LMT, TMO, MU, WDC, CSCO, VRT, AVGO), explain actionable catalysts (DoD/government contracts, surge in AI data center demand, hospital cap-ex, earnings beats) and why it warrants observation today.

OUTPUT CONSTRAINT:
Output ONLY valid HTML starting with <!DOCTYPE html> and closing with </html>. Do not include markdown ticks (```html).
"""

    models_to_try = get_available_flash_models()
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
                    break
            except Exception as err:
                print(f"Retry notice on {model_name}: {err}")
                time.sleep(6 * (attempt + 1))
        if response and response.text:
            break

    if not response or not response.text:
        raise RuntimeError("Generation failed across models.")

    clean_html = response.text.replace("```html", "").replace("```", "").strip()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(clean_html)
    print("index.html successfully updated!")

if __name__ == "__main__":
    run_agent()
