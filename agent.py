import os, re, time, urllib.request, json, feedparser
import yfinance as yf
from bs4 import BeautifulSoup
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 22 Active Assets
HOLDINGS = [
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT",
    "AAPL", "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD",
    "META", "GOOGL", "EQIX", "PLTR", "TSM", "VOO", "TMO", "WDC"
]

# Active Watchlist
WATCHLIST = ["USAR", "ISRG", "LMT", "MU", "ORCL", "CSCO", "VRT", "AVGO"]

# Broad-Market Scanner (S&P 500 & Nasdaq leaders)
BROAD_MARKET = [
    "AMD", "INTC", "QCOM", "ARM", "SMCI", "PANW", "CRWD", "NOW",
    "CRM", "SNOW", "DELL", "HPE", "ANET", "UBER", "ABNB",
    "NFLX", "DIS", "TSLA", "LLY", "UNH", "JNJ", "ABBV", "CAT",
    "DE", "GE", "HON", "RTX", "NOC", "GD", "BA", "JPM", "GS", "MS"
]

P_KEYS = ["padres", "san diego", "friars", "petco", "tatis", "machado", "merrill", "cease"]
P_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
M_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
T_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"

DEFAULT_JS = """function toggleWeatherDetail(idx){
  const el = document.getElementById('w-detail-' + idx);
  if(!el) return;
  const isHidden = el.style.display === 'none' || el.style.display === '';
  document.querySelectorAll('[id^="w-detail-"]').forEach(d => d.style.display = 'none');
  if(isHidden){
    el.style.display = 'block';
  }
}

async function updateWeather(){
  const c=document.getElementById('weather-forecast-list');if(!c)return;
  try{
    const now = new Date();
    const cutoff = new Date('2026-10-25T23:59:59-07:00');
    const isSantee = now <= cutoff;
    const lat = isSantee ? '32.8384' : '32.7448';
    const lon = isSantee ? '-116.9739' : '-116.9989';
    const titleEl = document.getElementById('weather-card-title');
    if(titleEl){
      titleEl.innerHTML = isSantee ? '🏕️ Santee 14-Day' : '📍 Spring Valley 14-Day';
    }
    const u = 'https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon + '&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,windgusts_10m_max&temperature_unit=fahrenheit&precipitation_unit=inch&wind_speed_unit=mph&timezone=America%2FLos_Angeles&forecast_days=14';
    const r=await fetch(u);
    const d=await r.json();let h='';
    const codes={0:'☀️ Clear',1:'🌤️ Mostly Clear',2:'⛅ Pt Cloudy',3:'☁️ Overcast',45:'🌫️ Fog',51:'🌦️ Light Drizzle',61:'🌧️ Light Rain',63:'🌧️ Rain',65:'🌧️ Heavy Rain',80:'🌦️ Showers',95:'⛈️ Storm'};
    for(let i=0;i<d.daily.time.length;i++){
      const dt=new Date(d.daily.time[i]+'T12:00:00');
      const day=i===0?'Today':dt.toLocaleDateString('en-US',{weekday:'short'});
      const md=(dt.getMonth()+1)+'/'+dt.getDate();
      const max=Math.round(d.daily.temperature_2m_max[i]),min=Math.round(d.daily.temperature_2m_min[i]);
      const prob=d.daily.precipitation_probability_max ? d.daily.precipitation_probability_max[i] : 0;
      const inch=(d.daily.precipitation_sum && d.daily.precipitation_sum[i] !== undefined) ? d.daily.precipitation_sum[i] : 0.0;
      const gust=(d.daily.windgusts_10m_max && d.daily.windgusts_10m_max[i] !== undefined) ? Math.round(d.daily.windgusts_10m_max[i]) : 0;
      let desc=codes[d.daily.weathercode[i]]||'🌤️ Fair';
      if(prob>=35 || inch > 0.01) desc='🌦️ Rain ('+prob+'%)';
      
      h+='<div style="border-bottom:1px solid #f1f5f9;">';
      h+='<div onclick="toggleWeatherDetail('+i+')" style="display:flex;justify-content:space-between;align-items:center;padding:17px 4px;font-size:14px;line-height:1.4;cursor:pointer;transition:background 0.15s;" onmouseover="this.style.background=\\'#f8fafc\\'" onmouseout="this.style.background=\\'transparent\\'">';
      h+='<div><strong style="font-size:15px;">'+day+'</strong> <span style="font-size:12px;color:#94a3b8;margin-left:5px;">'+md+'</span></div>';
      h+='<span style="color:#64748b;font-size:13px;">'+desc+'</span>';
      h+='<strong style="font-size:15px;">'+max+'° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ '+min+'°</span></strong>';
      h+='</div>';
      
      h+='<div id="w-detail-'+i+'" style="display:none;background:#f8fafc;padding:10px 14px;border-radius:8px;margin-bottom:8px;font-size:12px;color:#334155;border-left:3px solid #3b82f6;">';
      h+='<div style="font-weight:700;margin-bottom:4px;color:#1e293b;">📅 Details for '+day+' ('+md+')</div>';
      h+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">';
      h+='<div>🌧️ <strong>Total Rain:</strong> '+(inch > 0 ? inch + ' in' : '0.00 in')+'</div>';
      h+='<div>🎯 <strong>Rain Chance:</strong> '+prob+'%</div>';
      h+='<div>💨 <strong>Max Gusts:</strong> '+gust+' mph</div>';
      h+='<div>🌡️ <strong>Spread:</strong> '+min+'°F to '+max+'°F</div>';
      h+='</div></div>';
      
      h+='</div>';
    }
    c.innerHTML=h;
  }catch(e){c.innerHTML='<div style="color:#94a3b8;font-size:13px;">Weather syncing...</div>';}
}

async function updatePadres(){
  const b=document.getElementById('padres-live-box');if(!b)return;
  try{
    const r=await fetch('https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=135&hydrate=linescore');
    const d=await r.json();
    if(!d.dates||!d.dates[0]||!d.dates[0].games[0]){b.innerHTML='⚾ <strong>Padres:</strong> Offseason / No game scheduled today.';return;}
    const g=d.dates[0].games[0],s=g.status.abstractGameState,a=g.teams.away.team.name,h=g.teams.home.team.name;
    const as=g.teams.away.score||0,hs=g.teams.home.score||0;
    if(s==='Live')b.innerHTML='🔴 <span style="color:#dc2626;font-weight:700;">LIVE:</span> '+a+' '+as+' @ '+h+' '+hs;
    else if(s==='Final')b.innerHTML='🏁 <strong>FINAL:</strong> '+a+' '+as+' - '+h+' '+hs;
    else b.innerHTML='⚾ <strong>Upcoming:</strong> '+a+' @ '+h;
  }catch(e){b.innerHTML='Padres live feed standby.';}
}
updateWeather();updatePadres();setInterval(updatePadres,30000);"""

def extract_thumb(e, cat="general"):
    for k in ["media_content", "enclosures"]:
        if k in e and e[k]:
            for it in e[k]:
                u = it.get("url") or it.get("href") or ""
                if any(x in u.lower() for x in [".jpg", ".jpeg", ".png", ".webp"]):
                    return u
    if "media_thumbnail" in e and e.media_thumbnail:
        return e.media_thumbnail[0].get("url", "")
    desc = e.get("content", [{}])[0].get("value", "") or e.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    return m.group(1) if m else (P_LOGO if cat == "padres" else (M_LOGO if cat == "mlb" else T_LOGO))

def fetch_rss(url, limit=10, cat="general"):
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        f = feedparser.parse(urllib.request.urlopen(req, timeout=8).read())
        for e in f.entries[:limit]:
            t = e.get("title", "").strip()
            if t:
                out.append({"title": t, "link": e.get("link", "#"), "image": extract_thumb(e, cat)})
    except Exception:
        pass
    return out

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
                    is_p = any(k in title.lower() for k in P_KEYS) or "padres" in href
                    (padres if is_p else mlb).append({"title": title, "link": link, "image": P_LOGO if is_p else M_LOGO})
        except Exception:
            pass
    return padres, mlb

def fetch_padres_stories():
    p_scraped, mlb = scrape_mlb()
    p_final, seen = [p for p in p_scraped[:2]], {p["title"] for p in p_scraped[:2]}
    feed_url = "https://www.mlbtraderumors.com/san-diego-padres/feed"
    for it in fetch_rss(feed_url, 8, "padres"):
        if len(p_final) >= 5:
            break
        if it["title"] not in seen:
            seen.add(it["title"])
            p_final.append(it)
    if len(p_final) < 5:
        for it in fetch_rss("https://gaslampball.com/rss/index.xml", 8, "padres"):
            if len(p_final) >= 5:
                break
            if it["title"] not in seen:
                seen.add(it["title"])
                p_final.append(it)
    return p_final[:5], mlb[:5]

def fetch_fox5():
    seen, out = set(), []
    for u in ["https://fox5sandiego.com/news/feed/", "https://fox5sandiego.com/feed/"]:
        for it in fetch_rss(u, 8, "general"):
            if it["title"] not in seen and len(it["title"]) > 10:
                seen.add(it["title"])
                out.append(it)
                if len(out) >= 5:
                    return out
    return out[:5]

def get_catalysts():
    signals = []
    candidates_pool = []
    seen = set()
    scan_universe = HOLDINGS + WATCHLIST + BROAD_MARKET
    
    # Pass 1: Parse and categorize metrics across the universe
    for tkr in scan_universe:
        if "-USD" in tkr or tkr in seen:
            continue
        seen.add(tkr)
        try:
            t = yf.Ticker(tkr)
            fi = getattr(t, "fast_info", None)
            info = getattr(t, "info", {}) or {}
            h = t.history(period="1mo")
            
            price = fi.last_price if fi and fi.last_price else info.get("currentPrice")
            high_52 = fi.year_high if fi and fi.year_high else info.get("fiftyTwoWeekHigh")
            target = info.get("targetMeanPrice")
            rec = str(info.get("recommendationKey", "")).lower()
            num_analysts = info.get("numberOfAnalystOpinions", 0)
            
            if price and target and target > 0 and price > 0 and len(h) >= 15:
                upside = ((target - price) / price) * 100.0
                pullback = (((high_52 - price) / high_52) * 100.0) if high_52 else 0.0
                
                avg_v = float(h["Volume"].iloc[:-1].mean())
                tod_v = float(h["Volume"].iloc[-1])
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                day_pct = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100.0
                analysis_url = f"https://finance.yahoo.com/quote/{tkr}/analysis"
                
                # Check for Sell / Strong Sell triggers in existing portfolio
                is_sell_rating = rec in ["sell", "strong_sell", "underperform"]
                # Downside target or negative technical drift
                is_deteriorating = upside <= -5.0 or (pullback >= 25.0 and day_pct <= -2.5 and vr >= 1.4)
                
                if tkr in HOLDINGS and (is_sell_rating or is_deteriorating):
                    signals.append({
                        "ticker": tkr,
                        "group": "Current Holding",
                        "type": "SELL" if rec in ["sell", "underperform"] else "STRONG SELL",
                        "upside_num": upside,
                        "vol_ratio": f"{upside:+.0f}% Target",
                        "pct": f"${price:.2f}",
                        "consensus": rec.upper().replace('_', ' ') if rec else "BEARISH DOWNTREND",
                        "target_price": f"${target:.2f}",
                        "current_price": f"${price:.2f}",
                        "analysts": num_analysts,
                        "url": analysis_url,
                        "is_sell": True
                    })
                    continue
                
                # Identify valid candidates for Buy / Replacement
                if rec in ["buy", "strong_buy"] and upside >= 18.0:
                    candidates_pool.append({
                        "ticker": tkr,
                        "rec": rec,
                        "upside": upside,
                        "price": price,
                        "target": target,
                        "pullback": pullback,
                        "vr": vr,
                        "day_pct": day_pct,
                        "analysts": num_analysts,
                        "url": analysis_url,
                        "in_holdings": tkr in HOLDINGS
                    })
        except Exception:
            pass

    # Sort candidates by highest analyst upside
    candidates_pool.sort(key=lambda x: x["upside"], reverse=True)
    best_replacement = candidates_pool[0] if candidates_pool else None
    
    # Attach top replacement ticker to any Sell triggers
    for s in signals:
        if s.get("is_sell") and best_replacement:
            rep_type = "Holding" if best_replacement["in_holdings"] else "New"
            s["replacement_ticker"] = best_replacement["ticker"]
            s["replacement_url"] = best_replacement["url"]
            s["replacement_text"] = f"Rotate capital into {best_replacement['ticker']} ({rep_type}: {best_replacement['rec'].upper().replace('_', ' ')}, +{best_replacement['upside']:.0f}% upside)"

    # If no sell triggers fired, keep active Buy More and Breaking Out catalyst signals
    if not signals:
        for c in candidates_pool[:4]:
            if c["in_holdings"] and c["pullback"] >= 5.0:
                signals.append({
                    "ticker": c["ticker"],
                    "group": "Current Holding",
                    "type": "BUY MORE",
                    "upside_num": c["upside"],
                    "vol_ratio": f"+{c['upside']:.0f}% Up",
                    "pct": f"${c['price']:.2f}",
                    "consensus": c["rec"].upper().replace('_', ' '),
                    "target_price": f"${c['target']:.2f}",
                    "current_price": f"${c['price']:.2f}",
                    "analysts": c["analysts"],
                    "url": c["url"],
                    "is_sell": False
                })
            elif not c["in_holdings"] and ((c["vr"] >= 1.35 and c["day_pct"] > 0) or c["day_pct"] >= 2.0):
                signals.append({
                    "ticker": c["ticker"],
                    "group": "Active Watchlist" if c["ticker"] in WATCHLIST else "Broad Market Opportunity",
                    "type": "BREAKING OUT",
                    "upside_num": c["upside"],
                    "vol_ratio": f"+{c['upside']:.0f}% Up",
                    "pct": f"${c['price']:.2f}",
                    "consensus": c["rec"].upper().replace('_', ' '),
                    "target_price": f"${c['target']:.2f}",
                    "current_price": f"${c['price']:.2f}",
                    "analysts": c["analysts"],
                    "url": c["url"],
                    "is_sell": False
                })
                
    signals.sort(key=lambda x: x["upside_num"], reverse=True)
    return signals[:2]

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
            "url": f"https://finance.yahoo.com/quote/{sym}"
        })
    out.sort(key=lambda x: x["pct_num"], reverse=True)
    return out

def get_candidate_models():
    candidates = []
    try:
        for m in client.models.list():
            nm = m.name.replace("models/", "")
            if "flash" in nm.lower() and not nm.endswith("-exp") and "tts" not in nm.lower():
                candidates.append(nm)
    except Exception as e:
        print("Model discovery note:", e)
    for fallback in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates

def run_agent():
    ars = fetch_rss("https://feeds.arstechnica.com/arstechnica/technology-lab", 6, "ai")[:4]
    decoder = fetch_rss("https://the-decoder.com/feed/", 6, "ai")[:4]
    tc = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 4, "ai")[:2]
    tech = (ars + decoder + tc)[:10]

    padres, mlb = fetch_padres_stories()
    payload = {
        "catalysts": get_catalysts(), "padres": padres, "mlb": mlb,
        "world": fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml", 5),
        "sd": fetch_fox5(), "ai": tech,
        "holdings": get_quotes(HOLDINGS), "watchlist": get_quotes(WATCHLIST)
    }

    instruction = f"""Generate a complete, single-page HTML executive briefing dashboard.
Data payload JSON:
{json.dumps(payload)}

MANDATORY DESIGN AND STRUCTURE REQUIREMENTS:
1. NO TABS. Display all content in open, simultaneous side-by-side split panels.
2. FULL-WIDTH LAYOUT: width 98vw; max-width: 1820px; margin: 0 auto; page background #f1f5f9; cards #ffffff with 1px solid #e2e8f0, border-radius 12px, padding 18px. Start at top edge.
3. CSS KEYFRAME: @keyframes pulse-alert {{ 0%{{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);}} 50%{{border-color:#b91c1c;box-shadow:0 0 18px 5px rgba(239,68,68,0.55);}} 100%{{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);}} }}
4. CATALYST RADAR BANNER:
   - If 'catalysts' array is non-empty, render an alert container spanning full width above the three columns (padding 14px 22px, margin-bottom 20px, border 3px solid #ef4444, background #fff5f5, animation pulse-alert 1.5s infinite, display flex, align-items center, justify-content flex-start, border-radius 14px).
   - LEFT SIDE of banner: Render red badge '🚨 CATALYST ALERT' (background #ef4444, color #ffffff, font-weight 700, padding 6px 12px, border-radius 6px, font-size 13px, margin-right 20px; flex-shrink: 0).
   - CONTENT of banner:
     - For EACH item in 'catalysts':
       - If item.type is 'SELL' or 'STRONG SELL': Render a distinct pill with red styling. Inside show: <span style='background:#991b1b;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;margin-right:8px;'>item.type</span> <a href='item.url' target='_blank' rel='noopener noreferrer' style='text-decoration:none;color:#991b1b;font-weight:700;'>item.ticker: item.consensus at item.current_price ↗ View Why</a>. If 'replacement_ticker' is present, immediately follow with: <span style='margin-left:10px;padding-left:10px;border-left:1px solid #fca5a5;'>🔄 Replacement: <a href='item.replacement_url' target='_blank' rel='noopener noreferrer' style='color:#15803d;font-weight:700;text-decoration:none;'>item.replacement_text ↗</a></span>.
       - Otherwise (BUY MORE or BREAKING OUT): Render an individual, distinct clickable anchor tag <a href='item.url' target='_blank' rel='noopener noreferrer' style='display:inline-flex;align-items:center;margin-right:16px;padding:6px 14px;background:#ffffff;border:1px solid #fecaca;border-radius:8px;text-decoration:none;color:#991b1b;font-weight:600;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,0.05);transition:all 0.15s ease;'><span style='background:#ef4444;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;margin-right:8px;'>item.type</span> <strong>item.ticker:</strong> item.consensus at item.current_price (Target item.target_price, item.vol_ratio) <span style='font-size:11px;margin-left:6px;opacity:0.75;'>↗ View Why</span></a>. (CRITICAL: DO NOT output the word 'Consensus' anywhere).
   - DO NOT render 'HIGH CONVICTION SETUP' text anywhere on the banner.
   - If 'catalysts' is empty, render nothing at all.
5. THREE-COLUMN TOP LEVEL LAYOUT:
   - LEFT (320px width, align-self: flex-start): Weather card. Must have <h2 id='weather-card-title' style='font-size:18px;margin-top:0;margin-bottom:12px;'>Weather 14-Day</h2> followed by <div id='weather-forecast-list'>Loading forecast...</div>. Sized to fill the left edge and reach downward flush with Executive News.
   - CENTER (flex: 1): Top card 'Sports Desk: San Diego Padres & MLB' with 2 simultaneous side-by-side columns (left: Padres with <div id='padres-live-box'></div> and 5 Padres links with 46x46 SD logo; right: 5 MLB links with 46x46 MLB logo). Middle card 'Executive News (World & San Diego)' with 2 simultaneous side-by-side columns (left: Top 5 World Headlines; right: Top 5 FOX 5 San Diego Local News with story image thumbnails). Bottom card 'AI, Big Tech & Industry Breakthroughs' (2-column card grid of exactly 10 items from 'ai': 4 from Ars Technica, 4 from The Decoder, 2 from TechCrunch, each with 50x50 thumbnail and clickable title).
   - RIGHT (350px width): Top card 'Portfolio Pulse' with NO INTERNAL SCROLLBAR (no max-height, no overflow-y: auto). Each holding item MUST be an active clickable hyperlink <a href='url' target='_blank' rel='noopener noreferrer' style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f1f5f9;text-decoration:none;color:inherit;'>. Show ticker, price, and % badge. Directly below sits 'Watchlist Catalyst Radar' card with the same clickable style.
6. Insert marker [[WEATHER_AND_PADRES_JS]] immediately before </body>.
7. Return ONLY clean, valid raw HTML starting with <!DOCTYPE html> and ending with </html>. Do not include markdown code block backticks."""

    models = get_candidate_models()
    resp = None
    for m in models:
        for attempt in range(2):
            try:
                print(f"Generating with {m}...")
                resp = client.models.generate_content(model=m, contents=instruction)
                if resp and resp.text:
                    break
            except Exception as e:
                print(f"Notice on {m}: {e}")
                time.sleep(3)
        if resp and resp.text:
            break

    if not resp or not resp.text:
        raise RuntimeError("Generation failed across all models.")

    html = resp.text.replace("```html", "").replace("```", "").strip()
    js_tag = f"<script>\n{DEFAULT_JS}\n</script>"
    html = html.replace("[[WEATHER_AND_PADRES_JS]]", js_tag) if "[[WEATHER_AND_PADRES_JS]]" in html else (html.replace("</body>", f"{js_tag}</body>") if "</body>" in html else html + js_tag)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Dashboard build complete.")

if __name__ == "__main__":
    run_agent()