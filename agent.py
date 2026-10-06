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

def extract_thumbnail(entry, fallback_type="general"):
    """Extracts image/thumbnail URL from RSS entry, parsing HTML description if needed, with robust fallbacks."""
    # 1. Media tags
    if "media_thumbnail" in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get("url", "")
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", ""):
                return enc.get("href", "")
    
    # 2. Extract <img> tag from HTML description or content
    content_html = ""
    if "content" in entry and entry.content:
        content_html = entry.content[0].get("value", "")
    elif "description" in entry:
        content_html = entry.description or ""
    
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_html)
    if img_match:
        return img_match.group(1)

    # 3. Dedicated clean fallbacks so sports never shows empty grey boxes
    if fallback_type == "padres":
        return "https://www.mlbstatic.com/team-logos/135.svg"
    elif fallback_type == "mlb":
        return "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
    return ""

def fetch_rss_items(url, limit=10, fallback_type="general"):
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "#")
            img = extract_thumbnail(entry, fallback_type=fallback_type)
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
    print("Collecting news feeds with high-res thumbnails...")
    world_news = fetch_rss_items("https://feeds.bbci.co.uk/news/world/rss.xml", limit=5, fallback_type="general")
    
    sd_local_news = fetch_rss_items("https://www.cbs8.com/feeds/syndication/rss/news/local", limit=6, fallback_type="general")
    if not sd_local_news:
        sd_local_news = fetch_rss_items("https://www.nbcsandiego.com/?rss=y", limit=6, fallback_type="general")
    sd_local_news = sd_local_news[:5]

    padres_feed = fetch_rss_items("https://www.mlbtraderumors.com/san-diego-padres/feed", limit=6, fallback_type="padres")
    if len(padres_feed) < 5:
        padres_feed += fetch_rss_items("https://www.gaslampball.com/rss/index.xml", limit=6, fallback_type="padres")
    padres_articles = padres_feed[:5]

    other_mlb = fetch_rss_items("https://www.mlbtraderumors.com/feed", limit=8, fallback_type="mlb")[:5]

    ai_tech_items = (
        fetch_rss_items("https://techcrunch.com/category/artificial-intelligence/feed/", limit=6, fallback_type="general") +
        fetch_rss_items("https://feeds.arstechnica.com/arstechnica/technologylab", limit=6, fallback_type="general")
    )[:10]

    print("Fetching market quotes...")
    holdings_quotes = get_ticker_quotes(HOLDINGS)
    watchlist_quotes = get_ticker_quotes(WATCHLIST)

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
        "Generate a modern single-page HTML document with clean embedded CSS.\n\n"
        "PAGE DESIGN & SCALING RULES:\n"
        "- Clean White & Slate aesthetic: Page Background: #f1f5f9, Container Card Background: #ffffff, Border: 1px solid #e2e8f0, Border-radius: 12px, Padding: 20px.\n"
        "- DO NOT render any top title or heading like 'Executive Daily Intelligence Briefing'. Jump directly into the main content grid at the very top of the page.\n"
        "- SCALE ENLARGEMENT (+15-20%): Base font-size: 16px. Section Headings: 20px font-weight: 700. Article headline links: 16px font-weight: 600, color: #0f172a, line-height: 1.4. Thumbnail sizes: 64px width by 64px height, object-fit: cover, border-radius: 8px.\n"
        "- PAGE-LEVEL SCROLLING: Under NO circumstances should any section have internal scrollbars (NO max-height with overflow-y: scroll). Let the whole page scroll downward naturally.\n\n"
        "TWO-COLUMN TOP LEVEL LAYOUT:\n"
        "- LEFT / MAIN COLUMN (FLEX: 1, WIDER): Sports, News, and AI Breakthroughs.\n"
        "- RIGHT COLUMN (FIXED WIDTH: 380px): Portfolio Pulse and Watchlist Catalyst Radar.\n\n"
        "LEFT COLUMN SECTIONS:\n"
        "1. TOP ROW (2 side-by-side equal sub-boxes):\n"
        "   - BOX 1: 'Sports Desk: San Diego Padres & MLB'\n"
        "     * Top item: <div id=\"padres-live-box\" style=\"padding:12px; border-radius:8px; background:#f8fafc; border:1px solid #cbd5e1; margin-bottom:14px; font-weight:600; font-size:15px;\">Checking live Padres status...</div>\n"
        "     * Subhead: 'SAN DIEGO PADRES (TOP 5 UPDATES)'\n"
        "       Render all 5 items from data: " + str(padres_articles) + "\n"
        "       Display 64x64 thumbnail next to each item using the 'image' property. If image is missing or invalid, show Padres logo. Headline MUST be clickable link: <a href=\"URL\" target=\"_blank\">Title</a>.\n"
        "     * Subhead: 'LEAGUE-WIDE MLB STORIES (TOP 5)'\n"
        "       Render all 5 items from data: " + str(other_mlb) + " with 64x64 thumbnails and clickable links.\n"
        "   - BOX 2: 'Executive News (World & San Diego)'\n"
        "     * Subhead: 'TOP 5 WORLD HEADLINES'\n"
        "       Render 5 items from data: " + str(world_news) + " with 64x64 thumbnail and clickable title.\n"
        "     * Subhead: 'TOP 5 SAN DIEGO LOCAL NEWS'\n"
        "       Render 5 items from data: " + str(sd_local_news) + " with 64x64 thumbnail and clickable title.\n"
        "2. BOTTOM SECTION: 'AI & Tech Breakthroughs'\n"
        "   - 2-column card grid of AI articles from data: " + str(ai_tech_items) + "\n"
        "   - Include 64x64 thumbnail, clickable title. NO leading dots ('.') and NO 'Read more' text.\n\n"
        "RIGHT COLUMN (FINANCIAL INTEL):\n"
        "1. 'Portfolio Pulse' (Top-Right):\n"
        "   - Display ALL 20 holdings downward in a clean, vertical listing without scrollbars: " + str(holdings_quotes) + "\n"
        "   - Explicitly list: VOO, TSM, PLTR, EQIX, GOOGL, META, HOOD, COST, VLO, DLTR, NVDA, MSFT, AMZN, AAPL, WMT, BRK-B, SOL-USD, DOGE-USD, XRP-USD, BTC-USD.\n"
        "   - Each row should show: Bold Ticker (16px), Price (16px), and colored percentage badge (+ green, - red).\n"
        "2. 'Watchlist Catalyst Radar' (Directly below Portfolio Pulse):\n"
        "   - Vertical listing for: " + str(watchlist_quotes) + "\n"
        "   - Show ticker, quote, and 1-2 sentence actionable catalyst.\n\n"
        "Before the closing </body> tag, insert marker [[PADRES_JS_INJECTION]].\n"
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
