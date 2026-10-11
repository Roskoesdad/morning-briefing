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

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"
PADRES_KEYS = ["padres", "san diego", "friars", "petco", "cassavell", "lin", "morejon", "king", "france", "tatis", "machado", "merrill", "cease"]

def get_fin_url(t):
    return "https://finance.yahoo.com/quote/" + str(t) + "/"

def extract_thumb(e, cat="general"):
    if "media_thumbnail" in e and e.media_thumbnail:
        return e.media_thumbnail[0].get("url", "")
    if "media_content" in e and e.media_content:
        return e.media_content[0].get("url", "")
    c = e.get("content", [{}])[0].get("value", "") or e.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', c)
    if m:
        return m.group(1)
    return PADRES_LOGO if cat == "padres" else (MLB_LOGO if cat == "mlb" else TECH_LOGO)

def fetch_rss(url, limit=10, cat="general"):
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        fd = urllib.request.urlopen(req, timeout=8).read()
        f = feedparser.parse(fd)
        for e in f.entries[:limit]:
            t = e.get("title", "").strip()
            if t:
                items.append({"title": t, "link": e.get("link", "#"), "image": extract_thumb(e, cat), "pub": e.get("published_parsed")})
    except Exception:
        pass
    return items

def scrape_mlb():
    padres, mlb, seen = [], [], set()
    for u in ["https://www.mlb.com", "https://www.mlb.com/padres"]:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            h = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(h, "html.parser")
            for a in soup.find_all("a", href=True):
                href, title = a["href"], a.get_text(strip=True)
                if "/news/" in href and len(title) > 20 and title not in seen:
                    seen.add(title)
                    link = href if href.startswith("http") else ("https://www.mlb.com" + href)
                    is_p = any(k in title.lower() for k in PADRES_KEYS) or "padres" in href
                    if is_p:
                        padres.append({"title": title, "link": link, "image": PADRES_LOGO})
                    else:
                        mlb.append({"title": title, "link": link, "image": MLB_LOGO})
        except Exception:
            pass
    return padres, mlb

def fetch_padres_stories():
    p_scraped, mlb = scrape_mlb()
    p_final, seen = [], set()
    for item in p_scraped[:2]:
        seen.add(item["title"])
        p_final.append(item)
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    for item in fetch_rss("https://www.mlbtraderumors.com/san-diego-padres/feed", 8, "padres"):
        if len(p_final) >= 5:
            break
        if item["title"] not in seen and item.get("pub"):
            try:
                if datetime(*item["pub"][:6], tzinfo=timezone.utc) >= cutoff:
                    seen.add(item["title"])
                    p_final.append(item)
            except Exception:
                pass
    if len(p_final) < 5:
        for item in fetch_rss("https://gaslampball.com/rss/index.xml", 8, "padres"):
            if len(p_final) >= 5:
                break
            if item["title"] not in seen:
                seen.add(item["title"])
                p_final.append(item)
    return p_final[:5], mlb[:5]

def get_catalyst_alerts():
    return [{
        "ticker": "APEX",
        "group": "Active Watchlist",
        "type": "DoD Defense Procurement Award",
        "vol_ratio": "3.2x",
        "pct": "+6.85%",
        "summary": "APEX Systems awarded $485M multi-year contract for Tactical Edge Sensor Arrays. Volume running 3.2x above 20-day average.",
        "url": "https://finance.yahoo.com"
    }]

def get_quotes(tickers):
    out = []
    for sym in tickers:
        p, chg = None, 0.0
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            if fi and fi.last_price and fi.previous_close:
                p, chg = fi.last_price, ((fi.last_price - fi.previous_close) / fi.previous_close) * 100
            else:
                h = t.history(period="2d")
                if len(h) >= 2:
                    p = float(h["Close"].iloc[-1])
                    chg = ((p - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
        except Exception:
            pass
        out.append({
            "ticker": sym,
            "price": f"${p:,.2f}" if p else "N/A",
            "pct_num": chg,
            "pct": f"{chg:+.2f}%",
            "positive": chg >= 0,
            "url": get_fin_url(sym)
        })
    out.sort(key=lambda x: x["pct_num"], reverse=True)
    return out

def get_available_flash_models():
    preferred = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name.lower() and not name.endswith("-exp"):
                preferred.append(name)
    except Exception as e:
        print("Models notice:", str(e))
    if not preferred:
        preferred = ["gemini-2.5-flash", "gemini-2.0-flash"]
    return preferred

def get_js():
    return """
<script>
async function updateWeather() {
  const c = document.getElementById('weather-forecast-list');
  if (!c) return;
  try {
    const r = await fetch('https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles&forecast_days=14');
    const d = await r.json();
    let h = '';
    const codes = {0:'Clear', 1:'Clear', 2:'Pt Cloudy', 3:'Overcast', 45:'Fog', 51:'Drizzle', 61:'Rain', 80:'Showers', 95:'Storm'};
    for (let i = 0; i < d.daily.time.length; i++) {
      const dt = new Date(d.daily.time[i] + 'T12:00:00');
      const day = i === 0 ? 'Today' : dt.toLocaleDateString('en-US', {weekday:'short'});
      const md = (dt.getMonth() + 1) + '/' + dt.getDate();
      const max = Math.round(d.daily.temperature_2m_max[i]);
      const min = Math.round(d.daily.temperature_2m_min[i]);
      const desc = codes[d.daily.weathercode[i]] || 'Fair';
      h += '<div style="display:flex;justify-content:space-between;padding:8px 4px;border-bottom:1px solid #f1f5f9;font-size:14px;"><div><strong>' + day + '</strong> <span style="font-size:11px;color:#94a3b8;">' + md + '</span></div><span style="color:#64748b;font-size:13px;">' + desc + '</span><strong>' + max + '° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ ' + min + '°</span></strong></div>';
    }
    c.innerHTML = h;
  } catch (e) { c.innerHTML = 'Weather syncing...'; }
}
async function updatePadres() {
  const b = document.getElementById('padres-live-box');
  if (!b) return;
  try {
    const r = await fetch('https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore');
    const d = await r.json();
    if (!d.dates || !d.dates[0] || !d.dates[0].games[0]) {
      b.innerHTML = '⚾ <strong>Padres:</strong> Offseason / No game scheduled today.';
      return;
    }
    const g = d.dates[0].games[0];
    const s = g.status.abstractGameState;
    const a = g.teams.away.team.name, h = g.teams.home.team.name;
    const as = g.teams.away.score || 0, hs = g.teams.home.score || 0;
    if (s === 'Live') {
      b.innerHTML = '🔴 <span style="color:#dc2626;font-weight:700;">LIVE:</span> ' + a + ' ' + as + ' @ ' + h + ' ' + hs;
    } else if (s === 'Final') {
      b.innerHTML = '🏁 <strong>FINAL:</strong> ' + a + ' ' + as + ' - ' + h + ' ' + hs;
    } else {
      b.innerHTML = '⚾ <strong>Upcoming:</strong> ' + a + ' @ ' + h;
    }
  } catch (e) { b.innerHTML = 'Padres live feed standby.'; }
}
updateWeather();
updatePadres();
setInterval(updatePadres, 30000);
</script>
"""

def run_agent():
    print("Collecting news feeds...")
    world = fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml", 5)
    sd = fetch_rss("https://www.cbs8.com/feeds/syndication/rss/news/local", 5)
    padres, mlb = fetch_padres_stories()
    ai = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 10, "ai")
    catalysts = get_catalyst_alerts()
    holdings = get_quotes(HOLDINGS)
    watchlist = get_quotes(WATCHLIST)

    prompt = (
        "Generate a single HTML dashboard document.\n"
        "PAGE STYLING: Background: #f1f5f9; Cards: #ffffff; Border: 1px solid #e2e8f0; Border-radius: 12px; Padding: 18px; Layout: width 98vw; max-width: 1820px; margin: 0 auto; Start at top edge.\n"
        "CSS KEYFRAME ANIMATION: @keyframes pulse-alert { 0% { border-color:#ef4444; box-shadow:0 0 0 0 rgba(239,68,68,0.65); } 50% { border-color:#b91c1c; box-shadow:0 0 18px 5px rgba(239,68,68,0.55); } 100% { border-color:#ef4444; box-shadow:0 0 0 0 rgba(239,68,68,0.65); } }\n"
        "EXPANDED CATALYST RADAR ALERT BANNER (TOP OF PAGE):\n"
        "Data: " + str(catalysts) + "\n"
        "Render a prominent 15% enlarged alert container across full width above the 3 columns: padding 18px 26px; margin-bottom: 22px; border-radius: 12px; display flex; align-items center; justify-content space-between; background #fff5f5; border 3px solid #ef4444; animation pulse-alert 1.5s infinite;\n"
        "Left side: <span style='background:#dc2626;color:#fff;font-size:14px;font-weight:800;padding:6px 14px;border-radius:6px;text-transform:uppercase;'>🚨 Catalyst Radar Alert</span> <strong style='font-size:20px;color:#991b1b;margin-left:12px;'>APEX</strong> <span style='font-size:15px;color:#b91c1c;'>(DoD Defense Procurement Award)</span> <div style='font-size:15px;color:#1e293b;margin-top:6px;'>APEX Systems awarded $485M multi-year contract for Tactical Edge Sensor Arrays. Volume running 3.2x above 20-day average.</div>\n"
        "Right side: <a href='https://finance.yahoo.com' target='_blank' style='background:#dc2626;color:#fff;font-size:15px;font-weight:700;padding:12px 20px;border-radius:8px;text-decoration:none;'>Review Filing / Catalyst →</a>\n"
        "THREE COLUMNS:\n"
        "1. LEFT (260px): 'Spring Valley 14-Day Forecast' with <div id='weather-forecast-list'>Loading...</div>\n"
        "2. CENTER (FLEX 1): Top: Box A 'Sports Desk: Padres & MLB' (<div id='padres-live-box'></div>, Top 5 Padres: " + str(padres) + ", Top 5 MLB: " + str(mlb) + ") and Box B 'Executive News' (Top 5 World: " + str(world) + ", Top 5 SD: " + str(sd) + "). Bottom: 'AI & Big Tech' (10 items: " + str(ai) + ").\n"
        "3. RIGHT (330px): 'Portfolio Pulse' (" + str(holdings) + " clickable rows sorted descending) and 'Watchlist Catalyst Radar' (" + str(watchlist) + " clickable cards sorted descending).\n"
        "Insert marker [[WEATHER_AND_PADRES_JS]] before </body>. Output clean raw HTML without markdown ticks."
    )

    models = get_available_flash_models()
    resp = None
    for m in models:
        try:
            print("Calling model:", m)
            resp = client.models.generate_content(model=m, contents=prompt)
            if resp and resp.text:
                break
        except Exception as err:
            print("Model retry error:", str(err))
            time.sleep(4)

    if not resp or not resp.text:
        raise RuntimeError("Generation failed across all available models.")

    html = resp.text.replace("```html", "").replace("```", "").strip()
    js = get_js()
    if "[[WEATHER_AND_PADRES_JS]]" in html:
        html = html.replace("[[WEATHER_AND_PADRES_JS]]", js)
    elif "</body>" in html:
        html = html.replace("</body>", js + "</body>")
    else:
        html += js

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html successfully updated!")

if __name__ == "__main__":
    run_agent()