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

def get_fin_url(t):
    return "https://finance.yahoo.com/quote/" + str(t) + "/"

def extract_thumb(e, cat="general"):
    if "media_content" in e and e.media_content:
        for m in e.media_content:
            u = m.get("url", "")
            if u and ("jpg" in u or "png" in u or "jpeg" in u or "webp" in u):
                return u
    if "media_thumbnail" in e and e.media_thumbnail:
        for m in e.media_thumbnail:
            u = m.get("url", "")
            if u:
                return u
    if "enclosures" in e and e.enclosures:
        for enc in e.enclosures:
            u = enc.get("href", "")
            if u and ("jpg" in u or "png" in u or "jpeg" in u or "webp" in u):
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
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        fd = urllib.request.urlopen(req, timeout=8).read()
        f = feedparser.parse(fd)
        for e in f.entries[:limit]:
            t = e.get("title", "").strip()
            if t:
                items.append({
                    "title": t,
                    "link": e.get("link", "#"),
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
                headers={"User-Agent": "Mozilla/5.0"}
            )
            h = urllib.request.urlopen(req, timeout=10).read()
            html = h.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(strip=True)
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

def get_catalyst_alerts():
    signals = []
    dod_text = ""
    try:
        url = "https://www.defense.gov/News/Contracts/"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
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
                        "summary": "Confirmed federal procurement award identified. Volume: " + f"{vol_ratio:.1f}x average.",
                        "url": get_fin_url(ticker)
                    })
                elif vol_ratio >= 1.75 and pct_val >= 2.0:
                    signals.append({
                        "ticker": ticker,
                        "group": grp,
                        "type": "Institutional Volume Breakout",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_val:+.2f}%",
                        "summary": "Institutional accumulation detected (" + f"{vol_ratio:.1f}x normal volume) on upward move.",
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
    js_chunks = [
        "<script>\n",
        "async function updateWeather() {\n",
        "  const c = document.getElementById('weather-forecast-list');\n",
        "  if (!c) return;\n",
        "  try {\n",
        "    const u = 'https://api.open-meteo.com/v1/forecast?' +\n",
        "      'latitude=32.7448&longitude=-116.9989&' +\n",
        "      'daily=weathercode,temperature_2m_max,temperature_2m_min,' +\n",
        "      'precipitation_probability_max,precipitation_sum&' +\n",
        "      'temperature_unit=fahrenheit&precipitation_unit=inch&' +\n",
        "      'timezone=America%2FLos_Angeles&forecast_days=14';\n",
        "    const r = await fetch(u);\n",
        "    const d = await r.json();\n",
        "    let h = '';\n",
        "    const codes = {\n",
        "      0: '☀️ Clear',\n",
        "      1: '🌤️ Mostly Clear',\n",
        "      2: '⛅ Pt Cloudy',\n",
        "      3: '☁️ Overcast',\n",
        "      45: '🌫️ Fog',\n",
        "      48: '🌫️ Fog',\n",
        "      51: '🌦️ Light Drizzle',\n",
        "      53: '🌦️ Drizzle',\n",
        "      55: '🌧️ Heavy Drizzle',\n",
        "      61: '🌧️ Light Rain',\n",
        "      63: '🌧️ Rain',\n",
        "      65: '🌧️ Heavy Rain',\n",
        "      80: '🌦️ Showers',\n",
        "      81: '🌧️ Heavy Showers',\n",
        "      95: '⛈️ Storm'\n",
        "    };\n",
        "    for (let i = 0; i < d.daily.time.length; i++) {\n",
        "      const dt = new Date(d.daily.time[i] + 'T12:00:00');\n",
        "      const day = i === 0 ? 'Today' : dt.toLocaleDateString('en-US', {weekday:'short'});\n",
        "      const md = (dt.getMonth() + 1) + '/' + dt.getDate();\n",
        "      const max = Math.round(d.daily.temperature_2m_max[i]);\n",
        "      const min = Math.round(d.daily.temperature_2m_min[i]);\n",
        "      const code = d.daily.weathercode[i];\n",
        "      const precipProb = d.daily.precipitation_probability_max ? d.daily.precipitation_probability_max[i] : 0;\n",
        "      const precipIn = d.daily.precipitation_sum ? d.daily.precipitation_sum[i] : 0;\n",
        "      let desc = codes[code] || '🌤️ Fair';\n",
        "      if (precipProb >= 35 || precipIn >= 0.02) {\n",
        "        if (!desc.includes('Rain') && !desc.includes('Drizzle') && !desc.includes('Showers')) {\n",
        "          desc = '🌦️ Rain (' + precipProb + '%)';\n",
        "        } else {\n",
        "          desc += ' (' + precipProb + '%)';\n",
        "        }\n",
        "      }\n",
        "      h += '<div style=\"display:flex;justify-content:space-between;' +\n",
        "        'align-items:center;padding:14px 6px;' +\n",
        "        'border-bottom:1px solid #f1f5f9;font-size:14px;\">' +\n",
        "        '<div><strong>' + day + '</strong> ' +\n",
        "        '<span style=\"font-size:11px;color:#94a3b8;\">' + md + '</span></div>' +\n",
        "        '<span style=\"color:#64748b;font-size:13px;\">' + desc + '</span>' +\n",
        "        '<strong>' + max + '° ' +\n",
        "        '<span style=\"font-weight:400;color:#94a3b8;font-size:12px;\">/ ' +\n",
        "        min + '°</span></strong></div>';\n",
        "    }\n",
        "    c.innerHTML = h;\n",
        "  } catch (e) {\n",
        "    c.innerHTML = '<div style=\"color:#94a3b8;\">Weather syncing...</div>';\n",
        "  }\n",
        "}\n",
        "async function updatePadres() {\n",
        "  const b = document.getElementById('padres-live-box');\n",
        "  if (!b) return;\n",
        "  try {\n",
        "    const u = 'https://statsapi.mlb.com/api/v1/schedule?' +\n",
        "      'sportId=1&teamId=135&hydrate=linescore';\n",
        "    const r = await fetch(u);\n",
        "    const d = await r.json();\n",
        "    if (!d.dates || !d.dates[0] || !d.dates[0].games[0]) {\n",
        "      b.innerHTML = '⚾ <strong>Padres:</strong> Offseason / No game scheduled today.';\n",
        "      return;\n",
        "    }\n",
        "    const g = d.dates[0].games[0];\n",
        "    const s = g.status.abstractGameState;\n",
        "    const a = g.teams.away.team.name;\n",
        "    const h = g.teams.home.team.name;\n",
        "    const as = g.teams.away.score || 0;\n",
        "    const hs = g.teams.home.score || 0;\n",
        "    if (s === 'Live') {\n",
        "      b.innerHTML = '🔴 <span style=\"color:#dc2626;font-weight:700;\">LIVE:</span> ' +\n",
        "        a + ' ' + as + ' @ ' + h + ' ' + hs;\n",
        "    } else if (s === 'Final') {\n",
        "      b.innerHTML = '🏁 <strong>FINAL:</strong> ' +\n",
        "        a + ' ' + as + ' - ' + h + ' ' + hs;\n",
        "    }