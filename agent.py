import os, re, time, urllib.request, json, feedparser
import yfinance as yf
from bs4 import BeautifulSoup
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Portfolio Configuration, Exact Holdings & Institutional UC Retirement
PORTFOLIO_CONFIG = {
    "net_deposits": 6654.74,
    "cash": 3.56,  # $3.13 Robinhood cash + $0.43 E*TRADE cash
    "equities": {
        "AAPL": 2.02,
        "AMZN": 1.02,
        "BRK-B": 1.55,
        "COST": 0.18714,
        "DLTR": 1.02,
        "EQIX": 0.310956,
        "GOOGL": 1.46,
        "HOOD": 2.00,
        "META": 0.154687,
        "MSFT": 2.37,
        "NVDA": 5.03,
        "ORCL": 0.379276,
        "PLTR": 1.00,
        "TMO": 0.108713,
        "TSM": 0.127575,
        "VLO": 1.02,
        "VOO": 0.142004,
        "WDC": 0.140095,
        "WMT": 3.79,
    },
    "crypto": {
        "BTC-USD": 0.04313012,
        "DOGE-USD": 73.62,
        "SOL-USD": 0.02192,
        "XRP-USD": 47.055,
    },
    "retirement": {
        "as_of": "Oct 19, 2026",
        "combined_balance": 36087.69,
        "total_cost_basis": 30115.61,
        "total_unrealized_gain": 5972.08,
        "total_unrealized_gain_pct": 19.83,
        "ytd_contributions": 11250.00,
        "ytd_roi": "+8.89%",
        "plans": {
            "403b": {
                "name": "UC 403(B) PLAN (56016)",
                "fund": "UC PATHWAY 2040",
                "balance": 20654.70,
                "cost_basis": 16953.11,
                "unrealized_gain": 3701.59,
                "unrealized_pct": 21.83,
                "ytd_return": "+8.89%",
                "ytd_contrib": 5700.00,
                "per_paycheck": 300.00
            },
            "457b": {
                "name": "UC 457(B) PLAN (65270)",
                "fund": "UC PATHWAY 2040",
                "balance": 15432.99,
                "cost_basis": 13162.50,
                "unrealized_gain": 2270.49,
                "unrealized_pct": 17.25,
                "ytd_return": "+8.89%",
                "ytd_contrib": 5550.00,
                "per_paycheck": 250.00
            }
        }
    }
}

HOLDINGS = list(PORTFOLIO_CONFIG["equities"].keys()) + list(PORTFOLIO_CONFIG["crypto"].keys())

# Active Watchlist
WATCHLIST = ["USAR", "ISRG", "LMT", "MU", "ANET", "CSCO", "VRT", "AVGO"]

# Broad-Market Scanner (S&P 500 & Nasdaq leaders)
BROAD_MARKET = [
    "AMD", "INTC", "QCOM", "ARM", "SMCI", "PANW", "CRWD", "NOW",
    "CRM", "SNOW", "DELL", "HPE", "UBER", "ABNB",
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

function openReasonsModal(ticker, type, consensus, price, target, upside, reasonsJson){
  const overlay = document.getElementById('reasons-modal-overlay');
  if(!overlay) return;
  document.getElementById('modal-title').innerText = ticker + ' (' + type + ') Analysis';
  document.getElementById('modal-metrics').innerText = 'Consensus: ' + consensus + ' | Price: ' + price + ' | Target: ' + target + ' (' + upside + ')';
  
  let reasons = [];
  try {
    reasons = JSON.parse(decodeURIComponent(reasonsJson));
  } catch(e) {
    reasons = ["Valuation target compression.", "Capital rotation into secular growth opportunities.", "Margin headwind or technical momentum exhaustion."];
  }
  
  const list = document.getElementById('modal-reasons-list');
  list.innerHTML = reasons.map(r => '<li style="margin-bottom:10px;line-height:1.45;color:#334155;">' + r + '</li>').join('');
  overlay.style.display = 'flex';
}

function closeReasonsModal(){
  const overlay = document.getElementById('reasons-modal-overlay');
  if(overlay) overlay.style.display = 'none';
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

def generate_sell_reasons(ticker, current_price, target_price, upside, rec):
    try:
        prompt = f"""Provide exactly 3 concise, objective institutional reasons why an investor holding {ticker} would consider trimming, selling, or rotating out at current levels.
Current Price: ${current_price:.2f}, Target Price: ${target_price:.2f}, Analyst Upside: {upside:.1f}%, Consensus: {rec}.
Focus on fundamentals (valuation multiple, margin compression, sector rotation, regulatory/macro risks).
Output ONLY a JSON array containing exactly 3 strings without markdown."""
        models = get_candidate_models()
        for m in models:
            try:
                r = client.models.generate_content(model=m, contents=prompt)
                if r and r.text:
                    clean = r.text.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, list) and len(parsed) >= 3:
                        return parsed[:3]
            except Exception:
                continue
    except Exception:
        pass
    return [
        f"Valuation Target Inversion: Current price (${current_price:.2f}) leaves limited upside against the 12-month mean target (${target_price:.2f}).",
        "Sector Margin Compression: Cyclical refining margins (crack spreads) face normalization risks relative to peak levels.",
        "Capital Rotation Efficiency: Reallocating proceeds into higher secular upside holdings offers improved risk-adjusted growth."
    ]

def calculate_portfolio_summary():
    """Calculates all-time returns, day gains, and total valuation across Brokerages and UC Retirement."""
    total_brokerage_equity = PORTFOLIO_CONFIG["cash"]
    total_prev_close_equity = PORTFOLIO_CONFIG["cash"]

    all_symbols = list(PORTFOLIO_CONFIG["equities"].keys()) + list(PORTFOLIO_CONFIG["crypto"].keys())

    for sym in all_symbols:
        shares = PORTFOLIO_CONFIG["equities"].get(sym) or PORTFOLIO_CONFIG["crypto"].get(sym, 0.0)
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            p, prev = None, None
            if fi and fi.last_price and fi.previous_close:
                p = float(fi.last_price)
                prev = float(fi.previous_close)
            else:
                h = t.history(period="2d")
                if len(h) >= 2:
                    p = float(h["Close"].iloc[-1])
                    prev = float(h["Close"].iloc[-2])
                elif len(h) == 1:
                    p = float(h["Close"].iloc[-1])
                    prev = p

            if p is not None and prev is not None:
                total_brokerage_equity += p * shares
                total_prev_close_equity += prev * shares
        except Exception:
            pass

    net_deposits = PORTFOLIO_CONFIG["net_deposits"]
    all_time_dollar = total_brokerage_equity - net_deposits
    all_time_pct = (all_time_dollar / net_deposits) * 100.0 if net_deposits else 0.0

    day_dollar = total_brokerage_equity - total_prev_close_equity
    day_pct = (day_dollar / total_prev_close_equity) * 100.0 if total_prev_close_equity else 0.0

    ret_data = PORTFOLIO_CONFIG["retirement"]
    combined_retirement = ret_data["combined_balance"]
    total_net_worth = total_brokerage_equity + combined_retirement

    return {
        "total_net_worth": f"${total_net_worth:,.2f}",
        "brokerage_equity": f"${total_brokerage_equity:,.2f}",
        "net_deposits": f"${net_deposits:,.2f}",
        "all_time_dollar": f"+${all_time_dollar:,.2f}" if all_time_dollar >= 0 else f"-${abs(all_time_dollar):,.2f}",
        "all_time_pct": f"{all_time_pct:+.2f}%",
        "day_dollar": f"+${day_dollar:,.2f}" if day_dollar >= 0 else f"-${abs(day_dollar):,.2f}",
        "day_pct": f"{day_pct:+.2f}%",
        "is_day_positive": day_dollar >= 0,
        "retirement_balance": f"${combined_retirement:,.2f}",
        "retirement_cost_basis": f"${ret_data['total_cost_basis']:,.2f}",
        "retirement_gain": f"+${ret_data['total_unrealized_gain']:,.2f}",
        "retirement_gain_pct": f"+{ret_data['total_unrealized_gain_pct']:.2f}%",
        "retirement_ytd_roi": ret_data["ytd_roi"],
        "retirement_ytd_contrib": f"${ret_data['ytd_contributions']:,.2f}",
        "retirement_as_of": ret_data["as_of"],
        "plan_403b_bal": f"${ret_data['plans']['403b']['balance']:,.2f}",
        "plan_403b_gain": f"+${ret_data['plans']['403b']['unrealized_gain']:,.2f}",
        "plan_403b_pct": f"+{ret_data['plans']['403b']['unrealized_pct']:.2f}%",
        "plan_457b_bal": f"${ret_data['plans']['457b']['balance']:,.2f}",
        "plan_457b_gain": f"+${ret_data['plans']['457b']['unrealized_gain']:,.2f}",
        "plan_457b_pct": f"+{ret_data['plans']['457b']['unrealized_pct']:.2f}%"
    }

def get_catalysts():
    signals = []
    candidates_pool = []
    seen = set()
    scan_universe = HOLDINGS + WATCHLIST + BROAD_MARKET
    
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
                
                is_official_sell = rec in ["sell", "strong_sell", "underperform"]
                # Price target inversion or momentum breakdown
                is_target_inversion = upside <= -3.0 or (pullback >= 25.0 and day_pct <= -2.5 and vr >= 1.4)
                
                if tkr in HOLDINGS and (is_official_sell or is_target_inversion):
                    action_badge = "STRONG SELL" if rec == "strong_sell" else ("SELL" if is_official_sell else "ROTATE CAPITAL")
                    reasons_list = generate_sell_reasons(tkr, price, target, upside, rec)
                    reasons_encoded = urllib.parse.quote(json.dumps(reasons_list))
                    
                    signals.append({
                        "ticker": tkr,
                        "group": "Current Holding",
                        "type": action_badge,
                        "upside_num": upside,
                        "vol_ratio": f"{upside:+.0f}% Target",
                        "pct": f"${price:.2f}",
                        "consensus": rec.upper().replace('_', ' ') if is_official_sell else "TARGET INVERSION",
                        "target_price": f"${target:.2f}",
                        "current_price": f"${price:.2f}",
                        "analysts": num_analysts,
                        "url": analysis_url,
                        "reasons_encoded": reasons_encoded,
                        "is_sell": True
                    })
                    continue
                
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

    candidates_pool.sort(key=lambda x: x["upside"], reverse=True)
    best_replacement = candidates_pool[0] if candidates_pool else None
    
    for s in signals:
        if s.get("is_sell") and best_replacement:
            rep_type = "Holding" if best_replacement["in_holdings"] else "New"
            s["replacement_ticker"] = best_replacement["ticker"]
            s["replacement_url"] = best_replacement["url"]
            s["replacement_text"] = f"Rotate capital into {best_replacement['ticker']} ({rep_type}: {best_replacement['rec'].upper().replace('_', ' ')}, +{best_replacement['upside']:.0f}% upside)"

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
    print("Calculating portfolio metrics and syncing market data...")
    summary = calculate_portfolio_summary()

    day_color = "#00c805" if summary["is_day_positive"] else "#ef4444"

    ars = fetch_rss("https://feeds.arstechnica.com/arstechnica/technology-lab", 6, "ai")[:4]
    decoder = fetch_rss("https://the-decoder.com/feed/", 6, "ai")[:4]
    tc = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 4, "ai")[:2]
    tech = (ars + decoder + tc)[:10]

    padres, mlb = fetch_padres_stories()
    payload = {
        "portfolio_summary": summary,
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

4. MODAL DIALOG INJECTION (FOR 3 REASONS TO ROTATE/SELL):
   - Immediately before closing </body>, include this hidden modal HTML structure:
     <div id="reasons-modal-overlay" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(15,23,42,0.65);z-index:9999;align-items:center;justify-content:center;backdrop-filter:blur(3px);">
       <div style="background:#ffffff;border-radius:14px;padding:24px;max-width:540px;width:90%;box-shadow:0 20px 25px -5px rgba(0,0,0,0.2);position:relative;border:1px solid #e2e8f0;">
         <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f1f5f9;padding-bottom:12px;margin-bottom:14px;">
           <h3 id="modal-title" style="margin:0;font-size:18px;color:#0f172a;font-weight:800;"></h3>
           <button onclick="closeReasonsModal()" style="background:transparent;border:none;font-size:20px;cursor:pointer;color:#64748b;font-weight:700;">✕</button>
         </div>
         <div id="modal-metrics" style="font-size:12px;color:#64748b;margin-bottom:14px;font-weight:600;background:#f8fafc;padding:8px 12px;border-radius:6px;"></div>
         <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:8px;">💡 Key Actionable Reasons:</div>
         <ul id="modal-reasons-list" style="padding-left:20px;margin-top:0;margin-bottom:18px;font-size:13px;"></ul>
         <div style="display:flex;justify-content:flex-end;">
           <button onclick="closeReasonsModal()" style="background:#0f172a;color:#ffffff;border:none;padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;">Understood</button>
         </div>
       </div>
     </div>

5. EXECUTIVE WEALTH & RETIREMENT HEADER (FULL WIDTH AT TOP):
   - Directly below opening <body>, render a 4-card KPI row spanning full width (margin-bottom: 20px, display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px).
   - Card 1 (Liquid Net Worth): Label 'TOTAL LIQUID NET WORTH' (font-size: 11px, font-weight: 700, color: #64748b, text-transform: uppercase, letter-spacing: 0.5px). Main value '{summary['total_net_worth']}' (font-size: 26px, font-weight: 800, color: #0f172a). Sub-text: 'Combined Brokerage, Crypto & UC Plans' (font-size: 13px, color: #64748b, font-weight: 500, margin-top: 4px).
   - Card 2 (UC Retirement Combined): Label 'UC RETIREMENT (403b + 457b)' (font-size: 11px, font-weight: 700, color: #64748b, text-transform: uppercase, letter-spacing: 0.5px). Main value '{summary['retirement_balance']}' (font-size: 26px, font-weight: 800, color: #0284c7). Sub-text: '{summary['retirement_gain']} ({summary['retirement_gain_pct']} Return)' (font-size: 13px, color: #0284c7, font-weight: 700, margin-top: 4px).
   - Card 3 (Active Brokerage Trading): Label 'ACTIVE BROKERAGE EQUITY' (font-size: 11px, font-weight: 700, color: #64748b, text-transform: uppercase, letter-spacing: 0.5px). Main value '{summary['brokerage_equity']}' (font-size: 26px, font-weight: 800, color: #059669). Sub-text: '{summary['all_time_dollar']} ({summary['all_time_pct']} ROI)' (font-size: 13px, color: #059669, font-weight: 700, margin-top: 4px).
   - Card 4 (Today's Gain/Loss): Label 'TODAY\\'S BROKERAGE GAIN' (font-size: 11px, font-weight: 700, color: #64748b, text-transform: uppercase, letter-spacing: 0.5px). Main value '{summary['day_dollar']}' (font-size: 26px, font-weight: 800, color: {day_color}). Sub-text: '{summary['day_pct']} Intraday' (font-size: 13px, color: {day_color}, font-weight: 700, margin-top: 4px).

6. CATALYST RADAR BANNER:
   - If 'catalysts' array is non-empty, render an alert container spanning full width above the three columns (padding 14px 22px, margin-bottom: 20px, border: 3px solid #ef4444, background: #fff5f5, animation: pulse-alert 1.5s infinite, display: flex, align-items: center, justify-content: flex-start, border-radius: 14px).
   - LEFT SIDE of banner: Render red badge '🚨 CATALYST ALERT' (background: #ef4444, color: #ffffff, font-weight: 700, padding 6px 12px, border-radius 6px, font-size: 13px, margin-right: 20px; flex-shrink: 0).
   - CONTENT of banner:
     - For EACH item in 'catalysts':
       - If item.is_sell is True:
         Render a distinct pill: <div style='display:inline-flex;align-items:center;margin-right:16px;padding:6px 14px;background:#ffffff;border:1px solid #fecaca;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);'><span style='background:#991b1b;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;margin-right:8px;'>item.type</span> <strong>item.ticker:</strong> item.consensus at item.current_price (Target item.target_price, item.vol_ratio) <button onclick="openReasonsModal('item.ticker', 'item.type', 'item.consensus', 'item.current_price', 'item.target_price', 'item.vol_ratio', 'item.reasons_encoded')" style='background:none;border:none;color:#dc2626;font-weight:700;font-size:12px;cursor:pointer;margin-left:8px;text-decoration:underline;'>↗ View 3 Reasons</button> <span style='margin-left:10px;padding-left:10px;border-left:1px solid #fca5a5;'>🔄 Replacement: <a href='item.replacement_url' target='_blank' rel='noopener noreferrer' style='color:#15803d;font-weight:700;text-decoration:none;'>item.replacement_text ↗</a></span></div>.
       - Otherwise (BUY MORE or BREAKING OUT):
         Render: <a href='item.url' target='_blank' rel='noopener noreferrer' style='display:inline-flex;align-items:center;margin-right:16px;padding:6px 14px;background:#ffffff;border:1px solid #fecaca;border-radius:8px;text-decoration:none;color:#991b1b;font-weight:600;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,0.05);transition:all 0.15s ease;'><span style='background:#ef4444;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;margin-right:8px;'>item.type</span> <strong>item.ticker:</strong> item.consensus at item.current_price (Target item.target_price, item.vol_ratio) <span style='font-size:11px;margin-left:6px;opacity:0.75;'>↗ View Why</span></a>.
   - DO NOT render 'HIGH CONVICTION SETUP' text anywhere on the banner.
   - If 'catalysts' is empty, render nothing at all.

7. THREE-COLUMN TOP LEVEL LAYOUT:
   - LEFT (320px width, align-self: flex-start): Weather card. Must have <h2 id='weather-card-title' style='font-size:18px;margin-top:0;margin-bottom:12px;'>Weather 14-Day</h2> followed by <div id='weather-forecast-list'>Loading forecast...</div>. Sized to fill the left edge and reach downward flush with Executive News.
   - CENTER (flex: 1): Top card 'Sports Desk: San Diego Padres & MLB' with 2 simultaneous side-by-side columns (left: Padres with <div id='padres-live-box'></div> and 5 Padres links with 46x46 SD logo; right: 5 MLB links with 46x46 MLB logo). Middle card 'Executive News (World & San Diego)' with 2 simultaneous side-by-side columns (left: Top 5 World Headlines; right: Top 5 FOX 5 San Diego Local News with story image thumbnails). Bottom card 'AI, Big Tech & Industry Breakthroughs' (2-column card grid of exactly 10 items from 'ai': 4 from Ars Technica, 4 from The Decoder, 2 from TechCrunch, each with 50x50 thumbnail and clickable title).
   - RIGHT (350px width):
     - Top card: 'Institutional Retirement Tracker' with clean white background, border-radius 12px, border 1px solid #e2e8f0, padding 16px, margin-bottom 16px. Inside render:
       - Header: <div style='font-weight:800;font-size:15px;color:#0f172a;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;'><span>🏛️ UC Retirement Plans</span><span style='font-size:11px;font-weight:600;color:#64748b;'>As of {summary['retirement_as_of']}</span></div>
       - 403(b) Row: <div style='padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;'><div><div style='font-weight:700;font-size:13px;color:#1e293b;'>UC 403(B) (56016)</div><div style='font-size:11px;color:#64748b;'>UC Pathway 2040 (100%)</div></div><div style='text-align:right;'><div style='font-weight:800;font-size:14px;color:#0f172a;'>{summary['plan_403b_bal']}</div><div style='font-size:11px;color:#059669;font-weight:700;'>{summary['plan_403b_gain']} ({summary['plan_403b_pct']})</div></div></div>
       - 457(b) Row: <div style='padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;'><div><div style='font-weight:700;font-size:13px;color:#1e293b;'>UC 457(B) (65270)</div><div style='font-size:11px;color:#64748b;'>UC Pathway 2040 (100%)</div></div><div style='text-align:right;'><div style='font-weight:800;font-size:14px;color:#0f172a;'>{summary['plan_457b_bal']}</div><div style='font-size:11px;color:#059669;font-weight:700;'>{summary['plan_457b_gain']} ({summary['plan_457b_pct']})</div></div></div>
       - Footer Row: <div style='margin-top:10px;padding:8px;background:#f8fafc;border-radius:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#334155;'><span><strong>YTD Payroll Saved:</strong> {summary['retirement_ytd_contrib']}</span><span style='font-weight:700;color:#0284c7;'>YTD ROI: {summary['retirement_ytd_roi']}</span></div>
     - Middle card 'Portfolio Pulse' with NO INTERNAL SCROLLBAR (no max-height, no overflow-y: auto). Each holding item MUST be an active clickable hyperlink <a href='url' target='_blank' rel='noopener noreferrer' style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f1f5f9;text-decoration:none;color:inherit;'>. Show ticker, price, and % badge. Directly below sits 'Watchlist Catalyst Radar' card with the same clickable style.

8. Insert marker [[WEATHER_AND_PADRES_JS]] immediately before </body>.
9. Return ONLY clean, valid raw HTML starting with <!DOCTYPE html> and ending with </html>. Do not include markdown code block backticks."""

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