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
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT",
    "AAPL", "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD",
    "META", "GOOGL", "EQIX", "PLTR", "TSM", "VOO", "TMO"
]
WATCHLIST = [
    "USAR", "ISRG", "LMT", "MU", "WDC", "CSCO", "VRT", "AVGO"
]
DISCOVERY_TICKERS = ["RTX", "NOC", "GD", "BA"]

ENTITY_MAP = {
    "PLTR": ["palantir"],
    "MSFT": ["microsoft"],
    "NVDA": ["nvidia"],
    "AMZN": ["amazon", "aws"],
    "EQIX": ["equinix"],
    "LMT": ["lockheed martin", "lockheed"],
    "USAR": ["usa rare earth"],
    "VRT": ["vertiv"],
    "AVGO": ["broadcom"],
    "MU": ["micron"],
    "CSCO": ["cisco"],
    "RTX": ["raytheon", "rtx"],
    "NOC": ["northrop grumman", "northrop"],
    "GD": ["general dynamics"],
    "TMO": ["thermo fisher", "thermo fisher scientific"]
}

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"
PADRES_KEYS = [
    "padres", "san diego", "friars", "petco", "cassavell", "lin",
    "morejon", "king", "france", "tatis", "machado", "merrill", "cease"
]

DEFAULT_JS_CONTENT = """async function updateWeather() {
  const c = document.getElementById('weather-forecast-list');
  if (!c) return;
  try {
    const u = 'https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles&forecast_days=14';
    const r = await fetch(u);
    const d = await r.json();
    let h = '';
    const codes = {
      0: '☀️ Clear',
      1: '🌤️ Mostly Clear',
      2: '⛅ Pt Cloudy',
      3: '☁️ Overcast',
      45: '🌫️ Fog',
      48: '🌫️ Fog',
      51: '🌦️ Light Drizzle',
      53: '🌦️ Drizzle',
      55: '🌧️ Heavy Drizzle',
      61: '🌧️ Light Rain',
      63: '🌧️ Rain',
      65: '🌧️ Heavy Rain',
      80: '🌦️ Showers',
      81: '🌧️ Heavy Showers',
      95: '⛈️ Storm'
    };
    for (let i = 0; i < d.daily.time.length; i++) {
      const dt = new Date(d.daily.time[i] + 'T12:00:00');
      const day = i === 0 ? 'Today' : dt.toLocaleDateString('en-US', { weekday: 'short' });
      const md = (dt.getMonth() + 1) + '/' + dt.getDate();
      const max = Math.round(d.daily.temperature_2m_max[i]);
      const min = Math.round(d.daily.temperature_2m_min[i]);
      const code = d.daily.weathercode[i];
      const prob = d.daily.precipitation_probability_max ? d.daily.precipitation_probability_max[i] : 0;
      const inch = d.daily.precipitation_sum ? d.daily.precipitation_sum[i] : 0;
      let desc = codes[code] || '🌤️ Fair';
      if (prob >= 35 || inch >= 0.02) {
        if (!desc.includes('Rain') && !desc.includes('Drizzle') && !desc.includes('Showers')) {
          desc = '🌦️ Rain (' + prob + '%)';
        } else {
          desc += ' (' + prob + '%)';
        }
      }
      h += '<div style="display:flex;justify-content:space-between;align-items:center;padding:14px 6px;border-bottom:1px solid #f1f5f9;font-size:14px;"><div><strong>' + day + '</strong> <span style="font-size:11px;color:#94a3b8;">' + md + '</span></div><span style="color:#64748b;font-size:13px;">' + desc + '</span><strong>' + max + '° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ ' + min + '°</span></strong></div>';
    }
    c.innerHTML = h;
  } catch (e) {
    c.innerHTML = '<div style="color:#94a3b8;">Weather syncing...</div>';
  }
}

async function updatePadres() {
  const b = document.getElementById('padres-live-box');
  if (!b) return;
  try {
    const u = 'https://statsapi.mlb.com/api/v1/schedule?' +
      'sportId=1&teamId=135&hydrate=linescore';
    const r = await fetch(u);
    const d = await r.json();
    if (!d.dates || !d.dates[0] || !d.dates[0].games[0]) {
      b.innerHTML = '⚾ <strong>Padres:</strong> Offseason / No game scheduled today.';
      return;
    }
    const g = d.dates[0].games[0];
    const s = g.status.abstractGameState;
    const a = g.teams.away.team.name;
    const h = g.teams.home.team.name;
    const as = g.teams.away.score || 0;
    const hs = g.teams.home.score || 0;
    if (s === 'Live') {
      b.innerHTML = '🔴 <span style="color:#dc2626;font-weight:700;">LIVE:</span> ' + a + ' ' + as + ' @ ' + h + ' ' + hs;
    } else if (s === 'Final') {
      b.innerHTML = '🏁 <strong>FINAL:</strong> ' + a + ' ' + as + ' - ' + h + ' ' + hs;
    } else {
      b.innerHTML = '⚾ <strong>Upcoming:</strong> ' + a + ' @ ' + h;
    }
  } catch (e) {
    b.innerHTML = 'Padres live feed standby.';
  }
}

updateWeather();
updatePadres();
setInterval(updatePadres, 30000);
"""

def get_fin_url(t):
    return f"https://finance.yahoo.com/quote/{t}/"

def extract_thumb(e, cat="general"):
    if "media_content" in e and e.media_content:
        for m in e.media_content:
            u = m.get("url", "")
            if u and any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return u
    if "media_thumbnail" in e and e.media_thumbnail:
        for m in e.media_thumbnail:
            u = m.get("url", "")
            if u:
                return u
    if "enclosures" in e and e.enclosures:
        for enc in e.enclosures:
            u = enc.get("href", "")
            if u and any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return u
    c = e.get("content", [{}])[0].get("value", "") or e.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', c)
    if m:
        return m.group(1)
    if cat == "padres":
        return PADRES_LOGO
    if cat == "mlb":
        return MLB_LOGO
    return TECH_LOGO

def fetch_rss(url, limit=10, cat="general"):
    items = []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        fd = urllib.request.urlopen(req, timeout=8).read()
        f = feedparser.parse(fd)
        for e in f.entries[:limit]:
            t = e.get("title", "").strip()
            link = e.get("link", "#")
            if t:
                items.append({
                    "title": t,
                    "link": link,
                    "image": extract_thumb(e, cat),
                    "pub": e.get("published_parsed")
                })
    except Exception:
        pass
    return items

def scrape_mlb():
    padres, mlb, seen = [], [], set()
    urls = ["https://www.mlb.com", "https://www.mlb.com/padres"]
    for u in urls:
        try:
            req = urllib.request.Request(
                u,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            h = urllib.request.urlopen(req, timeout=10).read()
            html = h.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(strip=True)
                if "/news/" in href and len(title) > 20 and title not in seen:
                    seen.add(title)
                    link = href if href.startswith("http") else f"https://www.mlb.com{href}"
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
    tr_url = "https://www.mlbtraderumors.com/san-diego-padres/feed"
    for item in fetch_rss(tr_url, 8, "padres"):
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
        gl_url = "https://gaslampball.com/rss/index.xml"
        for item in fetch_rss(gl_url, 8, "padres"):
            if len(p_final) >= 5:
                break
            if item["title"] not in seen:
                seen.add(item["title"])
                p_final.append(item)
    return p_final[:5], mlb[:5]

def fetch_fox5_news():
    feeds = [
        "https://fox5sandiego.com/news/feed/",
        "https://fox5sandiego.com/feed/"
    ]
    seen_titles = set()
    items = []
    for f_url in feeds:
        fetched = fetch_rss(f_url, 8, "general")
        for it in fetched:
            t = it["title"]
            if t not in seen_titles and len(t) > 10:
                seen_titles.add(t)
                items.append(it)
                if len(items) >= 5:
                    break
        if len(items) >= 5:
            break
    return items[:5]

def fetch_tech_and_industry_articles():
    # 4 articles from Snacks (Sherwood Media / Robinhood Snacks)
    snacks_items = fetch_rss("https://sherwood.news/rss.xml", 8, "ai")
    if len(snacks_items) < 4:
        snacks_items += fetch_rss("https://sherwood.news/feed/", 6, "ai")

    # 4 articles from The Decoder (Direct open AI breakthroughs, zero login prompts)
    decoder_items = fetch_rss("https://the-decoder.com/feed/", 8, "ai")

    # 2 articles from TechCrunch AI
    tc_items = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 6, "ai")

    seen = set()
    final_list = []

    for item in snacks_items:
        if item["title"] not in seen and len(item["title"]) > 10:
            seen.add(item["title"])
            final_list.append(item)
            if len(final_list) == 4:
                break

    decoder_count = 0
    for item in decoder_items:
        if item["title"] not in seen and len(item["title"]) > 10:
            seen.add(item["title"])
            final_list.append(item)
            decoder_count += 1
            if decoder_count == 4:
                break

    tc_count = 0
    for item in tc_items:
        if item["title"] not in seen and len(item["title"]) > 10:
            seen.add(item["title"])
            final_list.append(item)
            tc_count += 1
            if tc_count == 2:
                break

    return final_list[:10]

def get_catalyst_alerts():
    signals = []
    dod_text = ""
    try:
        url = "https://www.defense.gov/News/Contracts/"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        h = urllib.request.urlopen(req, timeout=8).read()
        html = h.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        dod_text = soup.get_text().lower()
    except Exception as e:
        print("Notice DoD contracts:", str(e))

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
                avg_vol = float(hist["Volume"].iloc[:-1].mean())
                today_vol = float(hist["Volume"].iloc[-1])
                c_prev = float(hist["Close"].iloc[-2])
                c_last = float(hist["Close"].iloc[-1])
                pct_val = ((c_last - c_prev) / c_prev) * 100.0
                vol_ratio = (today_vol / avg_vol) if avg_vol > 0 else 1.0

                if ticker in HOLDINGS:
                    grp = "Current Portfolio"
                elif ticker in WATCHLIST:
                    grp = "Active Watchlist"
                else:
                    grp = "Discovery Opportunity"

                if has_contract and pct_val >= 0:
                    signals.append({
                        "ticker": ticker,
                        "group": grp,
                        "type": "DoD Procurement / Defense Contract Award",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_val:+.2f}%",
                        "summary": f"Confirmed federal procurement award identified. Volume: {vol_ratio:.1f}x average.",
                        "url": get_fin_url(ticker)
                    })
                elif vol_ratio >= 1.75 and pct_val >= 2.0:
                    signals.append({
                        "ticker": ticker,
                        "group": grp,
                        "type": "Institutional Volume Breakout",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_val:+.2f}%",
                        "summary": f"Institutional accumulation detected ({vol_ratio:.1f}x normal volume) on upward move.",
                        "url": get_fin_url(ticker)
                    })
        except Exception:
            continue

    return signals[:2]

def get_quotes(tickers):
    out = []
    for sym in tickers:
        p, chg = None, 0.0
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            if fi and fi.last_price and fi.previous_close:
                p = fi.last_price
                chg = ((fi.last_price - fi.previous_close) / fi.previous_close) * 100
            else:
                h = t.history(period="2d")
                if len(h) >= 2:
                    p = float(h["Close"].iloc[-1])
                    c_prev = float(h["Close"].iloc[-2])
                    chg = ((p - c_prev) / c_prev) * 100
        except Exception:
            pass
        out.append({
            "ticker": sym,