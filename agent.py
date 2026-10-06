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
    
    mlb_general = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=16)
    padres_articles = [item for item in mlb_general if "padres" in item["title"].lower()][:5]
    other_mlb = [item for item in mlb_general if "padres" not in item["title"].lower()][:5]

    ai_tech_items = (
        fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=7) +
        fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=6)
    )[:10]

    print("Fetching initial market quotes...")
    holdings_quotes = get_ticker_quotes(HOLDINGS)
    watchlist_quotes = get_ticker_quotes(WATCHLIST)

    prompt = f"""
You are an executive daily intelligence briefings designer.
Generate a modern single-page HTML document with clean embedded CSS and client-side JavaScript.

DESIGN & PALETTE REQUIREMENTS:
- Clean, crisp white & slate aesthetic.
- Page Background: #f1f5f9 (light gray/slate).
- Container Background: #ffffff, border: 1px solid #e2e8f0, box-shadow: 0 2px 4px rgba(0,0,0,0.04), border-radius: 12px, padding: 18px.
- Fonts: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
- Text: Primary #0f172a, Secondary #475569.
- Links: Color #0284c7, text-decoration: none. On hover: underline.
- Compact, dense layout: Avoid excessive vertical margins so the dashboard is viewable without endless scrolling.

GRID STRUCTURE:
1. HEADER:
   - "Executive Morning Intelligence"
   - Right badge: "Live System Feed" with live clock.

2. TOP ROW (2-COLUMN GRID):
   - LEFT COLUMN: "Sports Desk: San Diego Padres & MLB"
     * Embed a dedicated live scoreboard card: `<div id="padres-live-box" style="padding:12px; border-radius:8px; background:#f8fafc; border:1px solid #cbd5e1; margin-bottom:12px; font-weight:600;">Checking live Padres game status...</div>`
     * Subheader: "San Diego Padres Rumors & Roster"
       List up to 5 items: `<ul style="margin:4px 0 12px 18px; padding:0; font-size:14px; line-height:1.4;">` with each item being `<a href="..." target="_blank">Title</a>`.
     * Subheader: "League-Wide MLB Radar"
       List up to 5 items with clickable links.
     * Raw Padres Data: {padres_articles}
     * Raw MLB Data: {other_mlb}

   - RIGHT COLUMN: "World News Top 10"
     * Exactly 10 concise bullet points with direct clickable links: `<a href="..." target="_blank">Title</a>`.
     * Raw World News Data: {world_news}

3. MIDDLE SECTION: "AI & Tech Breakthroughs"
   - Display the top 10 AI items in a 2-column responsive compact grid.
   - STRICT FORMATTING: Do NOT prepend with bullet dots ('.') and do NOT include any "Read more" links. The article title itself MUST be the hyperlink: `<a href="..." target="_blank" style="font-weight:600; color:#0f172a; text-decoration:none;">Title</a>`.
   - Raw AI Data: {ai_tech_items}

4. SECTION: "Portfolio Pulse"
   - Responsive flex/grid of ticker badges for Holdings: {holdings_quotes}.
   - Display ticker, price, and daily % change.

5. SECTION: "Watchlist Catalyst Radar"
   - Display Watchlist items: {watchlist_quotes}.
   - For each stock (USAR, ISRG, LMT, TMO, MU, WDC, CSCO, VRT, AVGO), provide the real-time quote chip and a concise 1-2 sentence actionable catalyst.

CLIENT-SIDE JAVASCRIPT INJECTION:
Include this script before </body> to power the live Padres API polling and time updates:
```html
<script>
async function updatePadresBox() {
  const box = document.getElementById('padres-live-box');
  try {
    const today = new Date().toISOString().split('T')[0];
    const res = await fetch(`[https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore,probablePitcher](https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore,probablePitcher)`);
    const data = await res.json();
    if (!data.dates || data.dates.length === 0 || data.dates[0].games.length === 0) {
      box.innerHTML = "⚾ <strong>Padres:</strong> No game scheduled today.";
      return;
    }
    const game = data.dates[0].games[0];
    const status = game.status.abstractGameState;
    const detailed = game.status.detailedState;
    const away = game.teams.away.team.name;
    const home = game.teams.home.team.name;
    const awayScore = game.teams.away.score ?? 0;
    const homeScore = game.teams.home.score ?? 0;

    if (status === "Live") {
      const inning = game.linescore ? `${game.linescore.inningState} ${game.linescore.currentInningOrdinal}` : "Live";
      box.innerHTML = `🔴 <strong>LIVE:</strong> ${away} ${awayScore} @ ${home} ${homeScore} (${inning})`;
    } else if (status === "Final") {
      box.innerHTML = `🏁 <strong>FINAL:</strong> ${away} ${awayScore} - ${home} ${homeScore} (${detailed})`;
    } else {
      const gameTime = new Date(game.gameDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      box.innerHTML = `⚾ <strong>Upcoming:</strong> ${away} @ ${home} - ${gameTime} (${detailed})`;
    }
  } catch (e) {
    box.innerHTML = "⚾ <strong>Padres:</strong> Unable to pull live box
