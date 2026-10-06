import os
import re
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

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"

def extract_thumbnail(entry, category="general"):
    """Extracts image/thumbnail URL from RSS entry, parsing HTML description if needed, with context-aware fallbacks."""
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
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "#")
            img = extract_thumbnail(entry, category=category)
            if title:
                items.append({"title": title, "link": link, "image": img})
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
    world_news = fetch_rss_items("https://feeds.bbci.co.uk/news/world/rss.xml", limit=5, category="general")
    
    sd_local_news = fetch_rss_items("https://www.cbs8.com/feeds/syndication/rss/news/local", limit=6, category="general")
    if not sd_local_news:
        sd_local_news = fetch_rss_items("https://www.nbcsandiego.com/?rss=y", limit=6, category="general")
    sd_local_news = sd_local_news[:5]

    # Multi-source Padres feed aggregator
    padres_raw = (
        fetch_rss_items("https://www.mlbtraderumors.com/san-diego-padres/feed", limit=6, category="padres") +
        fetch_rss_items("https://gaslampball.com/rss/index.xml", limit=6, category="padres") +
        fetch_rss_items("https://padres.mlblogs.com/feed", limit=6, category="padres")
    )
    # Deduplicate while preserving order
    seen_titles = set()
    padres_articles = []
    for item in padres_raw:
        if item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            item["image"] = PADRES_LOGO
            padres_articles.append(item)
        if len(padres_articles) >= 5:
            break

    # League-Wide MLB Stories
    mlb_raw = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=12, category="mlb")
    other_mlb = []
    for item in mlb_raw:
        if "padres" not in item["title"].lower() and item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            item["image"] = MLB_LOGO
            other_mlb.append(item)
        if len(other_mlb) >= 5:
            break

    # AI Breakthroughs
    ai_tech_items = (
        fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=5, category="ai") +
        fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=5, category="ai")
    )[:10]

    print("Fetching market quotes...")
    holdings_quotes = get_ticker_quotes(HOLDINGS)
    watchlist_quotes = get_ticker_quotes(WATCHLIST)

    js_widget = """
<script>
async function updateWeather() {
  const container = document.getElementById('weather-forecast-list');
  if (!container) return;
  try {
    // Spring Valley, CA coordinates: 32.7448° N, 116.9989° W
    const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles');
    const data = await res.json();
    if (!data.daily || !data.daily.time) return;
    
    let html = '';
    const codes = {
      0: '☀️ Clear', 1: '🌤️ Mainly Clear', 2: '⛅ Partly Cloudy', 3: '☁️ Overcast',
      45: '🌫️ Fog', 48: '🌫️ Fog', 51: '🌦️ Light Drizzle', 61: '🌧️ Rain', 80: '🌦️ Showers', 95: '⛈️ Storm'
    };

    for (let i = 0; i < Math.min(data.daily.time.length, 7); i++) {
      const dateStr = data.daily.time[i];
      const d = new Date(dateStr + 'T12:00:00');
      const dayName = i === 0 ? 'Today' : d.toLocaleDateString('en-US', { weekday: 'short' });
      const max = Math.round(data.daily.temperature_2m_max[i]);
      const min = Math.round(data.daily.temperature_2m_min[i]);
      const code = data.daily.weathercode[i];
      const desc = codes[code] || '🌤️ Fair';
      
      html += `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:7px 0; border-bottom:1px solid #f1f5f9; font-size:13px;">
          <span style="font-weight:600; width:48px; color:#1e293b;">${dayName}</span>
          <span style="color:#64748b; font-size:12px; flex:1; text-align:center;">${desc}</span>
          <span style="font-weight:700; color:#0f172a;">${max}° <span style="font-weight:400; color:#94a3b8; font-size:12px;">/ ${min}°</span></span>
        </div>
      `;
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<div style="font-size:12px; color:#94a3b8; padding:8px 0;">Weather feed syncing...</div>';
  }
}

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

updateWeather();
updatePadresBox();
setInterval(updatePadresBox, 30000);
</script>
"""

    prompt = (
        "You are an executive daily intelligence briefings designer.\n"
        "Generate a modern single-page HTML document with clean embedded CSS.\n\n"
        "PAGE PALETTE & ARCHITECTURE:\n"
        "- Clean White & Slate aesthetic: Page Background: #f1f5f9, Container Cards: #ffffff, Border: 1px solid #e2e8f0, Border-radius: 10px, Padding: 16px.\n"
        "- Typography: system-ui, -apple-system, sans-serif. High contrast dark text #0f172a, muted #64748b, link #0284c7.\n"
        "- NO TOP HEADER OR TITLE. The layout must start immediately at the top edge.\n\n"
        "THREE-COLUMN TOP LEVEL LAYOUT:\n"
        "1. LEFT COLUMN (WIDTH: 220px): 'Spring Valley 7-Day Weather'\n"
        "   - Card with title: 'Spring Valley Forecast'\n"
        "   - Insert container: <div id=\"weather-forecast-list\">Loading live forecast...</div>\n\n"
        "2. CENTER / MAIN COLUMN (FLEX: 1, WIDE): Sports, News & Tech\n"
        "   - TOP ROW: 2 side-by-side sub-columns:\n"
        "     * BOX A: 'Sports Desk: San Diego Padres & MLB'\n"
        "       - Live scoreboard: <div id=\"padres-live-box\" style=\"padding:10px; border-radius:6px; background:#f8fafc; border:1px solid #cbd5e1; margin-bottom:12px; font-weight:600; font-size:13px;\">Checking live Padres status...</div>\n"
        "       - 'SAN DIEGO PADRES (TOP 5 UPDATES)': Render all 5 items from data: " + str(padres_articles) + "\n"
        "         Show a 44x44 thumbnail using the item's 'image' URL (the official Padres SD logo). Headline must be a clickable link <a href=\"URL\" target=\"_blank\">Title</a>.\n"
        "       - 'LEAGUE-WIDE MLB STORIES (TOP 5)': Render all 5 items from data: " + str(other_mlb) + " with 44x44 MLB logo thumbnail and link.\n"
        "     * BOX B: 'Executive News (World & San Diego)'\n"
        "       - 'TOP 5 WORLD HEADLINES': 5 items from data: " + str(world_news) + " with 44x44 thumbnail and clickable title.\n"
        "       - 'TOP 5 SAN DIEGO LOCAL NEWS': 5 items from data: " + str(sd_local_news) + " with 44x44 thumbnail and clickable title.\n"
        "   - BOTTOM SECTION: 'AI & Tech Breakthroughs'\n"
        "     * 2-column card grid of items from data: " + str(ai_tech_items) + "\n"
        "     * Use each item's 'image' URL (never Padres logo). NO leading dots ('.') and NO 'Read more' text. Title is the direct hyperlink.\n\n"
        "3. RIGHT COLUMN (WIDTH: 310px): 'Portfolio Pulse' & 'Watchlist Catalyst Radar'\n"
        "   - 'Portfolio Pulse' at top-right: Tight vertical listing of ALL 20 holdings: " + str(holdings_quotes) + "\n"
        "     Use compact 13px font, 4px-5px vertical padding per row, NO inner scrollbar so that ALL 20 assets (including VOO, PLTR, TSM, EQIX) fit cleanly within standard viewport height.\n"
        "   - 'Watchlist Catalyst Radar' directly underneath Portfolio Pulse: compact cards for: " + str(watchlist_quotes) + " with ticker, quote, and 1-sentence catalyst.\n\n"
        "Before closing </body> tag, insert marker [[WEATHER_AND_PADRES_JS]].\n"
        "Return ONLY clean raw HTML starting with <!DOCTYPE html> and ending with </html>. Do not include markdown code block backticks."
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
    
    if "[[WEATHER_AND_PADRES_JS]]" in clean_html:
        clean_html = clean_html.replace("[[WEATHER_AND_PADRES_JS]]", js_widget)
    elif "</body>" in clean_html:
        clean_html = clean_html.replace("</body>", f"{js_widget}</body>")
    else:
        clean_html += js_widget

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(clean_html)
    print("index.html successfully updated!")

if __name__ == "__main__":
    run_agent()
