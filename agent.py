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
    """Generates direct URL to validated catalyst and news analysis profiles."""
    if "-USD" in ticker:
        return f"https://finance.yahoo.com/quote/{ticker}/"
    return f"https://finance.yahoo.com/quote/{ticker}/"

def extract_thumbnail(entry, category="general"):
    """Extracts image/thumbnail URL from RSS entry, parsing HTML description if needed."""
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

def fetch_mlb_com_feed():
    """Scrapes official front-page headlines and stories from MLB.com feeds."""
    padres_stories = []
    mlb_stories = []
    try:
        feed_url = "https://www.mlb.com/feeds/news/rss.xml"
        req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
        feed_data = urllib.request.urlopen(req, timeout=8).read()
        feed = feedparser.parse(feed_data)
        
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "https://www.mlb.com")
            
            if any(k in title.lower() for k in ["padres", "san diego", "miller tipping", "chourio"]):
                padres_stories.append({"title": title, "link": link, "image": PADRES_LOGO})
            else:
                mlb_stories.append({"title": title, "link": link, "image": MLB_LOGO})
    except Exception as e:
        print(f"Notice querying MLB.com feed: {e}")

    if len(padres_stories) < 5:
        extra_padres = fetch_rss_items("https://www.gaslampball.com/rss/index.xml", limit=5, category="padres")
        padres_stories.extend(extra_padres)

    return padres_stories[:5], mlb_stories[:5]

def get_sorted_ticker_quotes(tickers):
    """Pulls prices, appends analysis URLs, and sorts descending by performance."""
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

    padres_articles, other_mlb = fetch_mlb_com_feed()

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

    print("Fetching sorted market quotes with clickable URLs...")
    sorted_holdings = get_sorted_ticker_quotes(HOLDINGS)
    sorted_watchlist = get_sorted_ticker_quotes(WATCHLIST)

    js_widget = """
<script>
async function updateWeather() {
  const container = document.getElementById('weather-forecast-list');
  if (!container) return;
  try {
    const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles&forecast_days=14');
    const data = await res.json();
    if (!data.daily || !data.daily.time) return;
    
    let html = '';
    const codes = {
      0: '☀️ Clear', 1: '🌤️ Clear', 2: '⛅ Pt Cloudy', 3: '☁️ Overcast',
      45: '🌫️ Fog', 48: '🌫️ Fog', 51: '🌦️ Drizzle', 61: '🌧️ Rain', 80: '🌦️ Showers', 95: '⛈️ Storm'
    };

    for (let i = 0; i < data.daily.time.length; i++) {
      const dateStr = data.daily.time[i];
      const d = new Date(dateStr + 'T12:00:00');
      const dayName = i === 0 ? 'Today' : d.toLocaleDateString('en-US', { weekday: 'short' });
      const monthDay = (d.getMonth() + 1) + '/' + d.getDate();
      const max = Math.round(data.daily.temperature_2m_max[i]);
      const min = Math.round(data.daily.temperature_2m_min[i]);
      const code = data.daily.weathercode[i];
      const desc = codes[code] || '🌤️ Fair';
      
      html += `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 4px; border-bottom:1px solid #f1f5f9; font-size:14px;">
          <div style="display:flex; flex-direction:column;">
            <span style="font-weight:700; color:#1e293b; font-size:14px;">${dayName}</span>
            <span style="font-size:11px; color:#94a3b8;">${monthDay}</span>
          </div>
          <span style="color:#64748b; font-size:13px; flex:1; text-align:center;">${desc}</span>
          <span style="font-weight:700; color:#0f172a; font-size:14px;">${max}° <span style="font-weight:400; color:#94a3b8; font-size:12px;">/ ${min}°</span></span>
        </div>
      `;
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<div style="font-size:13px; color:#94a3b8; padding:8px 0;">Weather feed syncing...</div>';
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
        "You are an executive intelligence dashboard developer.\n"
        "Generate a single-page HTML document with embedded CSS.\n\n"
        "PAGE STYLING & FULL-WIDTH SCREEN SIZING:\n"
        "- Clean White & Slate aesthetic: Page Background: #f1f5f9, Container Cards: #ffffff, Border: 1px solid #e2e8f0, Border-radius: 12px, Padding: 18px.\n"
        "- Fluid full-width layout: width: 98vw; max-width: 1820px; margin: 0 auto;.\n"
        "- NO TOP TITLE BANNER. Layout starts at the very top edge.\n\n"
        "THREE-COLUMN TOP LEVEL LAYOUT:\n"
        "1. LEFT COLUMN (WIDTH: 260px): 'Spring Valley 14-Day Forecast'\n"
        "   - Card title: 'Spring Valley 14-Day Forecast'\n"
        "   - Container: <div id=\"weather-forecast-list\">Loading live forecast...</div>\n\n"
        "2. CENTER / MAIN COLUMN (FLEX: 1, WIDE): Sports, News & Tech\n"
        "   - TOP ROW: 2 side-by-side sub-columns:\n"
        "     * BOX A: 'Sports Desk: San Diego Padres & MLB'\n"
        "       - Live scoreboard: <div id=\"padres-live-box\" style=\"padding:12px; border-radius:8px; background:#f8fafc; border:1px solid #cbd5e1; margin-bottom:14px; font-weight:700; font-size:15px;\">Checking live Padres status...</div>\n"
        "       - 'SAN DIEGO PADRES (TOP 5 UPDATES)': Render all 5 items from data: " + str(padres_articles) + "\n"
        "         Display 50x50 thumbnail using the Padres SD logo. Title must be a clickable link: <a href=\"URL\" target=\"_blank\" style=\"font-size:15px; font-weight:600; color:#0f172a; text-decoration:none;\">Title</a>.\n"
        "       - 'LEAGUE-WIDE MLB STORIES (TOP 5)': Render all 5 items from data: " + str(other_mlb) + " with 50x50 MLB logo and clickable links.\n"
        "     * BOX B: 'Executive News (World & San Diego)'\n"
        "       - 'TOP 5 WORLD HEADLINES': 5 items from data: " + str(world_news) + " with 50x50 thumbnail and clickable title.\n"
        "       - 'TOP 5 SAN DIEGO LOCAL NEWS': 5 items from data: " + str(sd_local_news) + " with 50x50 thumbnail and clickable title.\n"
        "   - BOTTOM SECTION: 'AI, Big Tech & Enterprise M&A'\n"
        "     * Responsive 2-column card grid of exactly 10 items from data: " + str(ai_tech_items) + "\n"
        "     * Include 54x54 thumbnail, clickable title (15px font). Highlight acquisitions or enterprise additions. Title is the direct hyperlink.\n\n"
        "3. RIGHT COLUMN (WIDTH: 330px): 'Portfolio Pulse' & 'Watchlist Catalyst Radar'\n"
        "   - 'Portfolio Pulse' (Top-Right):\n"
        "     * Sorted data: " + str(sorted_holdings) + "\n"
        "     * CRITICAL REQUIREMENT: Wrap EVERY single stock row in an HTML hyperlink `<a href=\"item.url\" target=\"_blank\">...</a>` so the entire row is clickable.\n"
        "     * Row styling: `display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 6px; text-decoration: none; color: inherit; transition: background 0.15s;` and on `:hover { background: #f8fafc; }`.\n"
        "     * Show Ticker (bold, #0f172a), Price (#334155), and the colored % badge (+ green, - red).\n"
        "     * Highest positive percentage performers at the very top, descending down to negative performers at the bottom. No internal scrollbars.\n"
        "   - 'Watchlist Catalyst Radar':\n"
        "     * Sorted data: " + str(sorted_watchlist) + "\n"
        "     * Wrap each watchlist ticker in `<a href=\"item.url\" target=\"_blank\">...</a>` linking directly to its catalyst feed.\n"
        "     * Display quote badge and 1-sentence actionable catalyst below each ticker.\n\n"
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
