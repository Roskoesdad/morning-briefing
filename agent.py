import os, re, time, urllib.request, json, feedparser, yfinance as yf
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
WATCHLIST = ["USAR", "ISRG", "LMT", "MU", "WDC", "CSCO", "VRT", "AVGO"]
DISCOVERY_TICKERS = ["RTX", "NOC", "GD", "BA"]

ENTITY_MAP = {
    "PLTR": ["palantir"], "MSFT": ["microsoft"], "NVDA": ["nvidia"],
    "AMZN": ["amazon", "aws"], "EQIX": ["equinix"], "LMT": ["lockheed martin"],
    "USAR": ["usa rare earth"], "VRT": ["vertiv"], "AVGO": ["broadcom"],
    "MU": ["micron"], "CSCO": ["cisco"], "RTX": ["raytheon", "rtx"],
    "NOC": ["northrop grumman"], "GD": ["general dynamics"],
    "TMO": ["thermo fisher"]
}

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"
PADRES_KEYS = ["padres", "san diego", "friars", "petco", "cassavell", "lin", "tatis", "machado", "merrill", "cease"]

DEFAULT_JS_CONTENT = """async function updateWeather() {
  const c = document.getElementById('weather-forecast-list');
  if (!c) return;
  try {
    const u = 'https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles&forecast_days=14';
    const r = await fetch(u); const d = await r.json(); let h = '';
    const codes = {0:'☀️ Clear',1:'🌤️ Mostly Clear',2:'⛅ Pt Cloudy',3:'☁️ Overcast',45:'🌫️ Fog',51:'🌦️ Light Drizzle',61:'🌧️ Light Rain',63:'🌧️ Rain',80:'🌦️ Showers',95:'⛈️ Storm'};
    for (let i = 0; i < d.daily.time.length; i++) {
      const dt = new Date(d.daily.time[i] + 'T12:00:00');
      const day = i === 0 ? 'Today' : dt.toLocaleDateString('en-US', {weekday:'short'});
      const md = (dt.getMonth()+1) + '/' + dt.getDate();
      const max = Math.round(d.daily.temperature_2m_max[i]), min = Math.round(d.daily.temperature_2m_min[i]);
      const prob = d.daily.precipitation_probability_max ? d.daily.precipitation_probability_max[i] : 0;
      let desc = codes[d.daily.weathercode[i]] || '🌤️ Fair';
      if (prob >= 35) desc = '🌦️ Rain (' + prob + '%)';
      h += '<div style="display:flex;justify-content:space-between;align-items:center;padding:14px 6px;border-bottom:1px solid #f1f5f9;font-size:14px;"><div><strong>' + day + '</strong> <span style="font-size:11px;color:#94a3b8;">' + md + '</span></div><span style="color:#64748b;font-size:13px;">' + desc + '</span><strong>' + max + '° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ ' + min + '°</span></strong></div>';
    }
    c.innerHTML = h;
  } catch(e) { c.innerHTML = '<div style="color:#94a3b8;">Weather syncing...</div>'; }
}
async function updatePadres() {
  const b = document.getElementById('padres-live-box');
  if (!b) return;
  try {
    const r = await fetch('https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore');
    const d = await r.json();
    if (!d.dates || !d.dates[0] || !d.dates[0].games[0]) {
      b.innerHTML = '⚾ <strong>Padres:</strong> Offseason / No game scheduled today.'; return;
    }
    const g = d.dates[0].games[0], s = g.status.abstractGameState;
    const a = g.teams.away.team.name, h = g.teams.home.team.name;
    const as = g.teams.away.score || 0, hs = g.teams.home.score || 0;
    if (s === 'Live') b.innerHTML = '🔴 <span style="color:#dc2626;font-weight:700;">LIVE:</span> ' + a + ' ' + as + ' @ ' + h + ' ' + hs;
    else if (s === 'Final') b.innerHTML = '🏁 <strong>FINAL:</strong> ' + a + ' ' + as + ' - ' + h + ' ' + hs;
    else b.innerHTML = '⚾ <strong>Upcoming:</strong> ' + a + ' @ ' + h;
  } catch(e) { b.innerHTML = 'Padres live feed standby.'; }
}
updateWeather(); updatePadres(); setInterval(updatePadres, 30000);
"""

def get_fin_url(t):
    return f"https://finance.yahoo.com/quote/{t}/"

def extract_thumb(e, cat="general"):
    for key in ["media_content", "enclosures"]:
        if key in e and e[key]:
            for item in e[key]:
                u = item.get("url") or item.get("href") or ""
                if any(x in u.lower() for x in [".jpg", ".jpeg", ".png", ".webp"]):
                    return u
    if "media_thumbnail" in e and e.media_thumbnail:
        return e.media_thumbnail[0].get("url", "")
    desc = e.get("content", [{}])[0].get("value", "") or e.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m:
        return m.group(1)
    return PADRES_LOGO if cat == "padres" else (MLB_LOGO if cat == "mlb" else TECH_LOGO)

def fetch_rss(url, limit=10, cat="general"):
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
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
            for a in BeautifulSoup(h, "html.parser").find_all("a", href=True):
                href, title = a["href"], a.get_text(strip=True)
                if "/news/" in href and len(title) > 20 and title not in seen:
                    seen.add(title)
                    link = href if href.startswith("http") else f"https://www.mlb.com{href}"
                    is_p = any(k in title.lower() for k in PADRES_KEYS) or "padres" in href
                    (padres if is_p else mlb).append({"title": title, "link": link, "image": PADRES_LOGO if is_p else MLB_LOGO})
        except Exception:
            pass
    return padres, mlb

def fetch_padres_stories():
    p_scraped, mlb = scrape_mlb()
    p_final, seen = [p for p in p_scraped[:2]], {p["title"] for p in p_scraped[:2]}
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    for it in fetch_rss("https://www.mlbtraderumors.com/san-diego-padres/feed", 8, "padres"):
        if len(p_final) >= 5: break
        if it["title"] not in seen and it.get("pub"):
            try:
                if datetime(*it["pub"][:6], tzinfo=timezone.utc) >= cutoff:
                    seen.add(it["title"]); p_final.append(it)
            except Exception: pass
    if len(p_final) < 5:
        for it in fetch_rss("https://gaslampball.com/rss/index.xml", 8, "padres"):
            if len(p_final) >= 5: break
            if it["title"] not in seen:
                seen.add(it["title"]); p_final.append(it)
    return p_final[:5], mlb[:5]

def fetch_fox5_news():
    seen, items = set(), []
    for u in ["https://fox5sandiego.com/news/feed/", "https://fox5sandiego.com/feed/"]:
        for it in fetch_rss(u, 8, "general"):
            if it["title"] not in seen and len(it["title"]) > 10:
                seen.add(it["title"]); items.append(it)
                if len(items) >= 5: return items
    return items[:5]

def fetch_tech_and_industry_articles():
    s = fetch_rss("https://sherwood.news/rss.xml", 6, "ai")[:4]
    d = fetch_rss("https://the-decoder.com/feed/", 6, "ai")[:4]
    tc = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 4, "ai")[:2]
    return (s + d + tc)[:10]

def get_catalyst_alerts():
    signals, dod_text = [], ""
    try:
        req = urllib.request.Request("https://www.defense.gov/News/Contracts/", headers={"User-Agent": "Mozilla/5.0"})
        dod_text = BeautifulSoup(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"), "html.parser").get_text().lower()
    except Exception: pass
    seen = set()
    for tkr in (HOLDINGS + WATCHLIST + DISCOVERY_TICKERS):
        if "-USD" in tkr or tkr in seen: continue
        seen.add(tkr)
        has_contract = any(a in dod_text for a in ENTITY_MAP.get(tkr, [tkr.lower()]))
        try:
            t = yf.Ticker(tkr)
            h = t.history(period="1mo")
            if len(h) >= 15:
                avg_v = float(h["Volume"].iloc[:-1].mean())
                tod_v = float(h["Volume"].iloc[-1])
                c_prev, c_last = float(h["Close"].iloc[-2]), float(h["Close"].iloc[-1])
                pct = ((c_last - c_prev) / c_prev) * 100.0
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                grp = "Current Portfolio" if tkr in HOLDINGS else ("Active Watchlist" if tkr in WATCHLIST else "Discovery Opportunity")
                if has_contract and pct >= 0:
                    signals.append({"ticker": tkr, "group": grp, "type": "DoD Procurement Award", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Federal contract identified. Volume: {vr:.1f}x.", "url": get_fin_url(tkr)})
                elif vr >= 1.75 and pct >= 2.0:
                    signals.append({"ticker": tkr, "group": grp, "type": "Institutional Volume Breakout", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Volume breakout ({vr:.1f}x avg) on upward expansion.", "url": get_fin_url(tkr)})
        except Exception: continue
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
                    chg = ((p - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
        except Exception: pass
        out.append({"ticker": sym, "price": f"${p:,.2f}" if p else "N/A", "pct_num": chg, "pct": f"{chg:+.2f}%", "positive": chg >= 0, "url": get_fin_url(sym)})
    out.sort(key=lambda x: x["pct_num"], reverse=True)
    return out

def get_available_flash_models():
    priority = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    discovered = []
    try:
        for m in client.models.list():
            nm = m.name.replace("models/", "")
            if "flash" in nm.lower() and not nm.endswith("-exp") and "tts" not in nm.lower():
                discovered.append(nm)
    except Exception: pass
    ordered = [m for m in priority if m in discovered]
    for d in discovered:
        if d not in ordered: ordered.append(d)
    return ordered if ordered else ["gemini-3.8-flash", "gemini-2.0-flash"]

def get_js():
    if os.path.exists("widget.js"):
        with open("widget.js", "r", encoding="utf-8") as f: code = f.read().strip()
    else:
        code = DEFAULT_JS_CONTENT.strip()
        with open("widget.js", "w", encoding="utf-8") as f: f.write(code)
    return f"<script>\n{code}\n</script>"

def run_agent():
    world = fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml", 5)
    sd = fetch_fox5_news()
    padres, mlb = fetch_padres_stories()
    ai_tech_items = fetch_tech_and_industry_articles()
    catalysts = get_catalyst_alerts()
    holdings = get_quotes(HOLDINGS)
    watchlist = get_quotes(WATCHLIST)

    prompt_data = {
        "catalysts": catalysts, "padres": padres, "mlb": mlb,
        "world": world, "sd": sd, "ai": ai_tech_items,
        "holdings": holdings, "watchlist": watchlist
    }

    instruction = (
        "Generate a complete, single-page HTML executive briefing dashboard.\n"
        "Data payload JSON:\n" + json.dumps(prompt_data) + "\n\n"
        "MANDATORY DESIGN AND STRUCTURE REQUIREMENTS:\n"
        "1. NO TABS. Display all content in open, simultaneous side-by-side split panels.\n"
        "2. FULL-WIDTH LAYOUT: width 98vw; max-width: 1820px; margin 0 auto; page background #f1f5f9; cards #ffffff with 1px solid #e2e8f0, border-radius 12px, padding 18px. Start at top edge.\n"
        "3. CSS KEYFRAME: @keyframes pulse-alert { 0%{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);} 50%{border-color:#b91c1c;box-shadow:0 0 18px 5px rgba(239,68,68,0.55);} 100%{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);} }\n"
        "4. CATALYST RADAR BANNER: If 'catalysts' array is non-empty, render an alert container spanning full width above the three columns (padding 18px 26px, margin-bottom 22px, border 3px solid #ef4444, background #fff5f5, animation pulse-alert 1.5s infinite, display flex, align-items center, justify-content space-between). If empty, render nothing.\n"
        "5. THREE-COLUMN TOP LEVEL LAYOUT:\n"
        "   - LEFT (270px width): 'Spring Valley 14-Day Forecast' card. Vertically expand card downward alongside center feed. Contains <div id='weather-forecast-list' style='display:flex;flex-direction:column;justify-content:space-between;height:100%;'>Loading forecast...</div>\n"
        "   - CENTER (flex: 1): Top card 'Sports Desk: San Diego Padres & MLB' with 2 simultaneous side-by-side columns (left: Padres with <div id='padres-live-box'></div> and 5 Padres links with 46x46 SD logo; right: 5 MLB links with 46x46 MLB logo). Middle card 'Executive News (World & San Diego)' with 2 simultaneous side-by-side columns (left: Top 5 World Headlines; right: Top 5 FOX 5 San Diego Local News with story image thumbnails). Bottom card 'AI, Big Tech & Industry Breakthroughs' (2-column card grid of exactly 10 items from 'ai': 4 from Snacks, 4 from The Decoder, 2 from TechCrunch, each with 50x50 thumbnail and clickable title).\n"
        "   - RIGHT (330px width): Top card 'Portfolio Pulse' with NO INTERNAL SCROLLBAR (no max-height, no overflow-y: auto) listing ALL items in 'holdings' sorted descending with ticker, price, and % badge. Directly below sits 'Watchlist Catalyst Radar' card listing all items in 'watchlist'.\n"
        "6. Insert marker [[WEATHER_AND_PADRES_JS]] immediately before </body>.\n"
        "7. Return ONLY clean