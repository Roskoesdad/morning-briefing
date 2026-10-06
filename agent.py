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
    
    mlb_general = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=18)
    padres_articles = [item for item in mlb_general if "padres" in item["title"].lower()][:5]
    other_mlb = [item for item in mlb_general if "padres" not in item["title"].lower()][:5]

    ai_tech_items = (
        fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=7) +
        fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=6)
    )[:10]

    print("Fetching market quotes...")
    holdings_quotes = get_ticker_quotes(HOLDINGS)
    watchlist_quotes = get_ticker_quotes(WATCHLIST)

    # JavaScript script injected as a separate variable to prevent f-string parser errors
    js_widget = """
<script>
async function updatePadresBox() {
  const box = document.getElementById('padres-live-box');
  if (!box) return;
  try {
    const res = await fetch('https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore,probablePitcher');
    const data = await res.json();
    if (!data.dates || data.dates.length === 0 || data.dates[0].games.length === 0) {
      box.innerHTML = '⚾ <strong>Padres:</strong> No game scheduled today.';
      return;
    }
    const game = data.dates[0].games[0];
    const status = game.status.abstractGameState;
    const detailed = game.status.detailedState;
    const away = game.teams.away.team.name;
    const home = game.teams.home.team.name;
    const awayScore = game.teams.away.score != null ? game.teams.away.score : 0;
    const homeScore = game.teams.home.score != null ? game.teams.home.score : 0;

    if (status === 'Live') {
      const inning = game.linescore ? (game.linescore.inningState + ' ' + game.linescore.currentInningOrdinal) : 'In Progress';
      box.innerHTML = '🔴 <span style="color:#dc2626; font-weight:700;">LIVE:</span> ' + away + ' ' + awayScore + ' @ ' + home + ' ' + homeScore + ' (' + inning + ')';
    } else if (status === 'Final') {
      box.innerHTML = '🏁 <strong>FINAL:</strong> ' + away + ' ' + awayScore + ' - ' + home + ' ' + homeScore + ' (' + detailed + ')';
    } else {
      const gameTime = new Date(game.gameDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      box.innerHTML = '⚾ <strong>Upcoming:</strong> ' + away + ' @ ' + home + ' - ' + gameTime + ' (' + detailed + ')';
    }
  } catch (e) {
    box.innerHTML = '⚾ <strong>Padres:</strong> Live box feed standby.';
  }
}
updatePadresBox();
setInterval(updatePadresBox, 30000);
</script>
"""

    prompt = (
        "You are an executive daily intelligence briefings designer.\n"
        "Generate a modern single-page HTML document with embedded CSS.\n\n"
        "DESIGN & PALETTE REQUIREMENTS:\n"
        "- Clean, crisp WHITE & SLATE theme.\n"
        "- Page Background: #f1f5f9 (slate 100).\n"
        "- Card Containers: #ffffff, border: 1px solid #e2e8f0, box-shadow: 0 1px 3px rgba(0,0,0,0.05), border-radius: 10px, padding: 16px.\n"
        "- Text: Primary #0f172a, Secondary #475569.\n"
        "- Links: #0284c7, text-decoration: none. On hover: underline.\n"
        "- Compact density to reduce page scrolling.\n\n"
        "LAYOUT REQUIREMENTS:\n"
        "1. HEADER: Title 'Executive Morning Intelligence' with a date/cycle badge on the right.\n"
        "2. TOP ROW (2-COLUMN GRID):\n"
        "   - LEFT COLUMN: 'Sports Desk: San Diego Padres & MLB'\n"
        "     * Insert this placeholder card at top: <div id=\"padres-live-box\" style=\"padding:10px; border-radius:6px; background:#f8fafc; border:1px solid #cbd5e1; margin-bottom:12px; font-weight:600; font-size:14px;\">Checking live Padres status...</div>\n"
        "     * Subheader 'San Diego Padres Rumors & Roster' with up to 5 items: raw list: " + str(padres_articles) + "\n"
        "     * Subheader 'League-Wide MLB Radar' with up to 5 items: raw list: " + str(other_mlb) + "\n"
        "     * Every sport headline must be an HTML link <a href=\"URL\" target=\"_blank\">Title</a>.\n"
        "   - RIGHT COLUMN: 'World News Top 10'\n"
        "     * Exactly 10 concise bullet points with direct clickable links <a href=\"URL\" target=\"_blank\">Title</a>: raw list: " + str(world_news) + "\n"
        "3. MIDDLE ROW: 'AI & Tech Breakthroughs'\n"
        "   - Render top 10 items in a responsive 2-column compact list.\n"
        "   - DO NOT include bullet points/dots ('.') and DO NOT include 'Read more' buttons.\n"
        "   - The article title itself must be the clickable link: raw data: " + str(ai_tech_items) + "\n"
        "4. SECTION: 'Portfolio Pulse'\n"
        "   - Responsive chip grid displaying ticker, price, and daily percentage change: " + str(holdings_quotes) + "\n"
        "5. SECTION: 'Watchlist Catalyst Radar'\n"
        "   - Display ticker chips with quotes: " + str(watchlist_quotes) + "\n"
        "   - For each target ticker (USAR, ISRG, LMT, TMO, MU, WDC, CSCO, VRT, AVGO), provide a brief 1-2 sentence actionable catalyst (contracts, growth, AI data center demand).\n\n"
        "IMPORTANT: Before the closing </body> tag, insert the exact text marker [[PADRES_JS_INJECTION]].\n"
        "Return ONLY raw HTML starting with <!DOCTYPE html> and ending with </html>. Do not include markdown code block backticks."
    )

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
        raise RuntimeError("Generation failed across candidate models.")

    clean_html = response.text.replace("```html", "").replace("```", "").strip()
    
    # Safely inject the live Padres script
    if "[[PADRES_JS_INJECTION]]" in clean_html:
        clean_html = clean_html.replace("[[PADRES_JS_INJECTION]]", js_widget)
    elif "</body>" in clean_html:
        clean_html = clean_html.replace("</body>", f"{js_widget}</body>")
    else:
        clean_html += js_widget

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(clean_html)
    print("index.html successfully updated!")

if __name__ == "__main__":
    run_agent()
