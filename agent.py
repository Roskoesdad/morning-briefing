import os, re, time, urllib.request, json, feedparser
from datetime import datetime
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
        "VLO": 1.02487,
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
        "as_of": "Oct 21, 2026",
        "combined_balance": 172552.79,
        "dc_plans_balance": 36087.69,
        "total_cost_basis": 30115.61,
        "total_unrealized_gain": 5972.08,
        "total_unrealized_gain_pct": 19.83,
        "ytd_contributions": 11550.00,
        "ytd_roi": "+8.89%",
        "plans": {
            "ucrp": {
                "name": "UCRP Pension (2013 Tier)",
                "balance": 136465.10,
                "contributions": 99282.42,
                "interest": 37182.68,
                "service_credit": 12.6114,
                "health_service": 12.6114,
                "start_date": "02/2014"
            },
            "403b": {
                "name": "UC 403(B) (Pre-Tax)",
                "fund": "UC PATHWAY 2040",
                "balance": 20654.70,
                "cost_basis": 16953.11,
                "unrealized_gain": 3701.59,
                "unrealized_pct": 21.83,
                "ytd_return": "+8.89%",
                "ytd_contrib": 6000.00,
                "per_paycheck": 300.00
            },
            "457b": {
                "name": "UC 457(B) (Roth After-Tax)",
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

COMPANY_NAMES = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "BRK-B": "Berkshire Hathaway",
    "COST": "Costco",
    "DLTR": "Dollar Tree",
    "EQIX": "Equinix",
    "GOOGL": "Alphabet (Google)",
    "HOOD": "Robinhood",
    "META": "Meta",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "ORCL": "Oracle",
    "PLTR": "Palantir",
    "TMO": "Thermo Fisher",
    "TSM": "TSMC",
    "VLO": "Valero Energy",
    "VOO": "Vanguard S&P 500",
    "WDC": "Western Digital",
    "WMT": "Walmart",
    "BTC-USD": "Bitcoin",
    "DOGE-USD": "Dogecoin",
    "SOL-USD": "Solana",
    "XRP-USD": "XRP",
    "USAR": "USA Rare Earth",
    "ISRG": "Intuitive Surgical",
    "LMT": "Lockheed Martin",
    "MU": "Micron Technology",
    "ANET": "Arista Networks",
    "CSCO": "Cisco",
    "VRT": "Vertiv",
    "AVGO": "Broadcom",
    "AMD": "AMD",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "ARM": "Arm Holdings",
    "SMCI": "Super Micro",
    "PANW": "Palo Alto Networks",
    "CRWD": "CrowdStrike",
    "NOW": "ServiceNow",
    "CRM": "Salesforce",
    "SNOW": "Snowflake",
    "DELL": "Dell Technologies",
    "HPE": "Hewlett Packard Enterprise",
    "UBER": "Uber",
    "ABNB": "Airbnb",
    "NFLX": "Netflix",
    "DIS": "Disney",
    "TSLA": "Tesla",
    "LLY": "Eli Lilly",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson & Johnson",
    "ABBV": "AbbVie",
    "CAT": "Caterpillar",
    "DE": "Deere & Co",
    "GE": "GE Aerospace",
    "HON": "Honeywell",
    "RTX": "RTX",
    "NOC": "Northrop Grumman",
    "GD": "General Dynamics",
    "BA": "Boeing",
    "JPM": "JPMorgan Chase",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley"
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

function openReasonsModal(name, actionType, reasonsJson){
  const overlay = document.getElementById('reasons-modal-overlay');
  if(!overlay) return;
  document.getElementById('modal-title').innerText = name + ' (' + actionType + ') Analysis';
  
  let reasons = [];
  try {
    reasons = JSON.parse(decodeURIComponent(reasonsJson));
  } catch(e) {
    reasons = ["Strategic valuation considerations.", "Sector rebalancing and capital efficiency.", "Growth upside and risk-reward profile."];
  }
  
  const list = document.getElementById('modal-reasons-list');
  list.innerHTML = reasons.map(r => '<li style="margin-bottom:10px;line-height:1.45;color:#334155;">' + r + '</li>').join('');
  overlay.style.display = 'flex';
}

function closeReasonsModal(){
  const overlay = document.getElementById('reasons-modal-overlay');
  if(overlay) overlay.style.display = 'none';
}

function toggleTabRow(){
  const row = document.getElementById('kpi-tab-bar');
  const cardsContainer = document.getElementById('kpi-cards-grid');
  if(!row || !cardsContainer) return;
  
  const isHidden = row.style.display === 'none' || row.style.display === '';
  if(isHidden){
    row.style.display = 'flex';
    cardsContainer.style.display = 'grid';
    for(let i=1; i<=4; i++){
      const c = document.getElementById('kpi-card-' + i);
      if(c) c.style.display = 'block';
    }
  } else {
    row.style.display = 'none';
    cardsContainer.style.display = 'none';
    for(let i=1; i<=4; i++){
      const c = document.getElementById('kpi-card-' + i);
      if(c) c.style.display = 'none';
    }
  }
}

function toggleKpiCard(idx){
  const card = document.getElementById('kpi-card-' + idx);
  if(!card) return;
  const isHidden = card.style.display === 'none' || card.style.display === '';
  card.style.display = isHidden ? 'block' : 'none';
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

def generate_reasons(ticker, action_type, price, target, upside, rec):
    company_name = COMPANY_NAMES.get(ticker, ticker)
    try:
        prompt = f"""Provide exactly 3 concise, objective institutional reasons why an investor would choose to {action_type.upper()} {company_name} ({ticker}) at current levels.
Current Price: ${price:.2f}, Target Price: ${target:.2f}, Upside: {upside:.1f}%, Consensus: {rec}.
Focus on fundamentals (valuation multiple, margin trajectory, secular growth drivers, sector rotation, capital efficiency).
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
    if action_type.lower() == "buy":
        return [
            f"Attractive Upside Spread: Consensus price target offers superior projected return (+{upside:.0f}%) over the next 12 months.",
            f"Secular Growth Tailwind: Expanding enterprise demand and operating leverage support multiple expansion for {company_name}.",
            "Favorable Risk/Reward: High institutional conviction provides defensive support against broader market volatility."
        ]
    return [
        f"Valuation Cap: Current market price (${price:.2f}) leaves limited upside against the 12-month mean target.",
        f"Sector Rebalancing: Multiple expansion for {company_name} creates potential for capital rotation into discounted opportunities.",
        "Capital Efficiency: Reallocating proceeds into higher upside holdings offers improved risk-adjusted growth."
    ]

def calculate_portfolio_summary():
    """Calculates all-time returns, day gains, and total valuation across Brokerages, UCRP Pension, and UC Savings."""
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
    total_uc_retirement = ret_data["combined_balance"]
    total_net_worth = total_brokerage_equity + total_uc_retirement

    ucrp = ret_data["plans"]["ucrp"]

    return {
        "total_net_worth": f"${total_net_worth:,.2f}",
        "brokerage_equity": f"${total_brokerage_equity:,.2f}",
        "net_deposits": f"${net_deposits:,.2f}",
        "all_time_dollar": f"+${all_time_dollar:,.2f}" if all_time_dollar >= 0 else f"-${abs(all_time_dollar):,.2f}",
        "all_time_pct": f"{all_time_pct:+.2f}%",
        "day_dollar": f"+${day_dollar:,.2f}" if day_dollar >= 0 else f"-${abs(day_dollar):,.2f}",
        "day_pct": f"{day_pct:+.2f}%",
        "is_day_positive": day_dollar >= 0,
        "uc_total_balance": f"${total_uc_retirement:,.2f}",
        "ucrp_balance": f"${ucrp['balance']:,.2f}",
        "ucrp_service": f"{ucrp['service_credit']:.2f} yrs",
        "uc_dc_balance": f"${ret_data['dc_plans_balance']:,.2f}",
        "retirement_as_of": ret_data["as_of"],
        "plan_403b_bal": f"${ret_data['plans']['403b']['balance']:,.2f}",
        "plan_403b_gain": f"+${ret_data['plans']['403b']['unrealized_gain']:,.2f}",
        "plan_403b_pct": f"+{ret_data['plans']['403b']['unrealized_pct']:.2f}%",
        "plan_457b_bal": f"${ret_data['plans']['457b']['balance']:,.2f}",
        "plan_457b_gain": f"+${ret_data['plans']['457b']['unrealized_gain']:,.2f}",
        "plan_457b_pct": f"+{ret_data['plans']['457b']['unrealized_pct']:.2f}%"
    }

def read_embedded_history():
    """Reads persistent catalyst history from index.html so it survives GitHub Actions ephemeral runners."""
    html_file = "index.html"
    if os.path.exists(html_file):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
                m = re.search(r'<script id="catalyst-tracker-data" type="application/json">\s*({.*?})\s*</script>', content, re.DOTALL)
                if m:
                    return json.loads(m.group(1))
        except Exception as e:
            print("Note reading embedded history:", e)
    return {}

def filter_active_catalysts(raw_signals):
    """
    Suppresses any stock that has appeared across 2 days.
    History is embedded directly into index.html so state persists across runs.
    """
    history = read_embedded_history()
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_keys = set()
    active_signals = []

    for s in raw_signals:
        primary_stock = s.get("ticker", "")
        if not primary_stock:
            continue

        current_keys.add(primary_stock)
        entry = history.get(primary_stock)

        if entry:
            first_seen = entry.get("first_seen", today_str)
            last_seen = entry.get("last_seen", today_str)
            days_active = entry.get("days_active", 1)
            
            if last_seen != today_str:
                days_active += 1
                history[primary_stock] = {
                    "first_seen": first_seen,
                    "last_seen": today_str,
                    "days_active": days_active
                }
            
            # Allow strictly Day 1 and Day 2; suppress on Day 3+
            if days_active < 3:
                active_signals.append(s)
            else:
                print(f"Suppressing persistent alert for {primary_stock} (active for {days_active} days).")
        else:
            history[primary_stock] = {
                "first_seen": today_str,
                "last_seen": today_str,
                "days_active": 1
            }
            active_signals.append(s)

    # Clean up records for stocks no longer triggering
    stale_keys = [k for k in list(history.keys()) if k not in current_keys]
    for k in stale_keys:
        del history[k]

    return active_signals, history

def get_market_movement_triggers():
    triggers = []
    for idx_sym in ["SPY", "QQQ"]:
        try:
            t = yf.Ticker(idx_sym)
            fi = getattr(t, "fast_info", None)
            pct = 0.0
            if fi and fi.last_price and fi.previous_close:
                pct = ((fi.last_price - fi.previous_close) / fi.previous_close) * 100.0
            else:
                h = t.history(period="2d")
                if len(h) >= 2:
                    p = float(h["Close"].iloc[-1])
                    prev = float(h["Close"].iloc[-2])
                    pct = ((p - prev) / prev) * 100.0

            name = "S&P 500 (SPY)" if idx_sym == "SPY" else "Nasdaq-100 (QQQ)"
            if pct <= -1.50:
                triggers.append({
                    "type": "MARKET SELL-OFF",
                    "name": name,
                    "ticker": idx_sym,
                    "is_sell": True,
                    "reasons_encoded": urllib.parse.quote(json.dumps([
                        f"Broad Index Decline: {name} is experiencing an intraday decline of {pct:.2f}%.",
                        "Capital Preservation: Trimming extended high-beta positions reduces drawdown exposure during index-wide liquidity contractions.",
                        "Rebalancing Inflow: Raising cash during systemic dips creates dry powder to accumulate undervalued core equities."
                    ]))
                })
            elif pct >= 1.75:
                triggers.append({
                    "type": "MARKET BREAKOUT",
                    "name": name,
                    "ticker": idx_sym,
                    "is_sell": False,
                    "reasons_encoded": urllib.parse.quote(json.dumps([
                        f"Macro Upside Momentum: {name} is advancing +{pct:.2f}% with broad-based market breadth.",
                        "Risk-On Acceleration: Institutional liquidity is flowing into high-conviction growth and technology leaders.",
                        "Momentum Follow-Through: Heavy accumulation supports continuous multi-week target expansions."
                    ]))
                })
        except Exception:
            pass
    return triggers

def get_catalysts():
    signals = []
    candidates_pool = []
    seen = set()
    scan_universe = HOLDINGS + WATCHLIST + BROAD_MARKET
    
    market_events = get_market_movement_triggers()

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
            c_name = COMPANY_NAMES.get(tkr, tkr)
            
            if price and target and target > 0 and price > 0 and len(h) >= 15:
                upside = ((target - price) / price) * 100.0
                pullback = (((high_52 - price) / high_52) * 100.0) if high_52 else 0.0
                
                avg_v = float(h["Volume"].iloc[:-1].mean())
                tod_v = float(h["Volume"].iloc[-1])
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                day_pct = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100.0
                analysis_url = f"https://finance.yahoo.com/quote/{tkr}/analysis"
                
                is_official_sell = rec in ["sell", "strong_sell", "underperform"]
                is_target_inversion = upside <= -3.0 or (pullback >= 25.0 and day_pct <= -2.5 and vr >= 1.4)
                is_major_holding_selloff = tkr in HOLDINGS and day_pct <= -4.0 and vr >= 1.25
                
                if tkr in HOLDINGS and (is_official_sell or is_target_inversion or is_major_holding_selloff):
                    action_badge = "STRONG SELL" if (rec == "strong_sell" or day_pct <= -5.0) else "SELL"
                    reasons_list = generate_reasons(tkr, "SELL", price, target, upside, rec)
                    reasons_encoded = urllib.parse.quote(json.dumps(reasons_list))
                    
                    signals.append({
                        "ticker": tkr,
                        "name": c_name,
                        "group": "Current Holding",
                        "type": action_badge,
                        "upside_num": upside,
                        "vol_ratio": f"{upside:+.0f}% Target",
                        "pct": f"${price:.2f}",
                        "current_price": f"${price:.2f}",
                        "analysts": num_analysts,
                        "url": analysis_url,
                        "reasons_encoded": reasons_encoded,
                        "is_sell": True
                    })
                    continue
                
                is_major_buy_breakout = (day_pct >= 4.0 and vr >= 1.5) or (rec in ["buy", "strong_buy"] and upside >= 18.0)
                if is_major_buy_breakout:
                    candidates_pool.append({
                        "ticker": tkr,
                        "name": c_name,
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
            s["replacement_ticker"] = best_replacement["ticker"]
            s["replacement_name"] = best_replacement["name"]
            s["replacement_url"] = best_replacement["url"]
            s["replacement_text"] = f"{best_replacement['name']} (+{best_replacement['upside']:.0f}% upside)"
            buy_reasons_list = generate_reasons(best_replacement["ticker"], "BUY", best_replacement["price"], best_replacement["target"], best_replacement["upside"], best_replacement["rec"])
            s["replacement_reasons_encoded"] = urllib.parse.quote(json.dumps(buy_reasons_list))

    if market_events and best_replacement:
        for me in market_events:
            me["replacement_ticker"] = best_replacement["ticker"]
            me["replacement_name"] = best_replacement["name"]
            me["replacement_url"] = best_replacement["url"]
            me["replacement_text"] = f"{best_replacement['name']} (+{best_replacement['upside']:.0f}% upside)"
            buy_reasons_list = generate_reasons(best_replacement["ticker"], "BUY", best_replacement["price"], best_replacement["target"], best_replacement["upside"], best_replacement["rec"])
            me["replacement_reasons_encoded"] = urllib.parse.quote(json.dumps(buy_reasons_list))
            signals.insert(0, me)

    if not signals:
        for me in market_events:
            if not me.get("is_sell") and best_replacement:
                signals.append({
                    "ticker": best_replacement["ticker"],
                    "name": best_replacement["name"],
                    "group": "Major Market Breakout",
                    "type": "BUY NOW",
                    "upside_num": best_replacement["upside"],
                    "vol_ratio": f"+{best_replacement['upside']:.0f}% Up",
                    "pct": f"${best_replacement['price']:.2f}",
                    "current_price": f"${best_replacement['price']:.2f}",
                    "analysts": best_replacement["analysts"],
                    "url": best_replacement["url"],
                    "reasons_encoded": urllib.parse.quote(json.dumps(generate_reasons(best_replacement["ticker"], "BUY", best_replacement["price"], best_replacement["target"], best_replacement["upside"], best_replacement["rec"]))),
                    "is_sell": False
                })

    signals.sort(key=lambda x: x.get("upside_num", 0), reverse=True)
    return filter_active_catalysts(signals[:4])

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
            "name": COMPANY_NAMES.get(sym, sym),
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

def render_news_items(items):
    out = ""
    for it in items:
        img_html = f'<img src="{it["image"]}" style="width:44px;height:44px;border-radius:6px;object-fit:cover;flex-shrink:0;margin-right:12px;" onerror="this.src=\'{T_LOGO}\'" />' if it.get("image") else ""
        out += f"""<a href="{it['link']}" target="_blank" rel="noopener noreferrer" style="display:flex;align-items:center;padding:10px 0;border-bottom:1px solid #f1f5f9;text-decoration:none;color:#1e293b;transition:background 0.15s ease;">
          {img_html}
          <span style="font-size:13px;font-weight:600;line-height:1.4;">{it['title']}</span>
        </a>"""
    return out

def render_stock_list(quotes):
    out = ""
    for q in quotes:
        color = "#15803d" if q["positive"] else "#dc2626"
        badge_bg = "#dcfce7" if q["positive"] else "#fee2e2"
        out += f"""<a href="{q['url']}" target="_blank" rel="noopener noreferrer" style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #f1f5f9;text-decoration:none;color:inherit;">
          <div>
            <div style="font-weight:700;font-size:13px;color:#0f172a;">{q['name']}</div>
            <div style="font-size:11px;color:#64748b;">{q['ticker']}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:700;font-size:13px;color:#0f172a;">{q['price']}</div>
            <span style="display:inline-block;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:700;color:{color};background:{badge_bg};margin-top:2px;">{q['pct']}</span>
          </div>
        </a>"""
    return out

def run_agent():
    print("Calculating portfolio metrics and syncing market data...")
    summary = calculate_portfolio_summary()

    ars = fetch_rss("https://feeds.arstechnica.com/arstechnica/technology-lab", 6, "ai")[:4]
    decoder = fetch_rss("https://the-decoder.com/feed/", 6, "ai")[:4]
    tc = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 4, "ai")[:2]
    tech = (ars + decoder + tc)[:10]

    padres, mlb = fetch_padres_stories()
    world_news = fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml", 5)
    sd_news = fetch_fox5()
    holdings_quotes = get_quotes(HOLDINGS)
    watchlist_quotes = get_quotes(WATCHLIST)

    catalysts, history_state = get_catalysts()
    day_color = "#00c805" if summary["is_day_positive"] else "#ef4444"

    # Pre-render deterministic HTML components to prevent LLM omissions
    catalyst_banner_html = ""
    if catalysts:
        items_html = ""
        for item in catalysts:
            if item.get("is_sell"):
                items_html += f"""<div style="display:inline-flex;align-items:center;padding:8px 14px;background:#ffffff;border:1px solid #fecaca;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);flex-wrap:wrap;gap:8px;">
                  <span style="background:#991b1b;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">{item['type']}</span>
                  <strong>{item['name']}</strong>
                  <button onclick="openReasonsModal('{item['name']}', 'SELL', '{item['reasons_encoded']}')" style="background:none;border:none;color:#dc2626;font-weight:700;font-size:12px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                  <span style="padding-left:10px;border-left:1px solid #fca5a5;display:inline-flex;align-items:center;gap:6px;">
                    🔄 Buy: <a href="{item.get('replacement_url', '#')}" target="_blank" rel="noopener noreferrer" style="color:#15803d;font-weight:700;text-decoration:none;">{item.get('replacement_text', '')} ↗</a>
                    <button onclick="openReasonsModal('{item.get('replacement_name', '')}', 'BUY', '{item.get('replacement_reasons_encoded', '')}')" style="background:none;border:none;color:#15803d;font-weight:700;font-size:12px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                  </span>
                </div>"""
            else:
                items_html += f"""<div style="display:inline-flex;align-items:center;padding:8px 14px;background:#ffffff;border:1px solid #bbf7d0;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);flex-wrap:wrap;gap:8px;">
                  <span style="background:#15803d;color:#ffffff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">{item['type']}</span>
                  <strong>{item['name']}</strong>
                  <button onclick="openReasonsModal('{item['name']}', 'BUY', '{item['reasons_encoded']}')" style="background:none;border:none;color:#15803d;font-weight:700;font-size:12px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                </div>"""
        
        catalyst_banner_html = f"""<div style="margin-bottom:20px;padding:14px 22px;border:3px solid #ef4444;background:#fff5f5;animation:pulse-alert 1.5s infinite;display:flex;align-items:center;justify-content:flex-start;flex-wrap:wrap;gap:12px;border-radius:14px;">
          <div style="display:inline-flex;align-items:center;background:#ef4444;color:#ffffff;font-weight:700;padding:6px 14px;border-radius:6px;font-size:13px;flex-shrink:0;">🚨 CATALYST ALERT</div>
          <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;flex:1;">{items_html}</div>
        </div>"""

    padres_html = render_news_items(padres)
    mlb_html = render_news_items(mlb)
    world_html = render_news_items(world_news)
    sd_html = render_news_items(sd_news)
    tech_html = render_news_items(tech)
    holdings_html = render_stock_list(holdings_quotes)
    watchlist_html = render_stock_list(watchlist_quotes)

    # Embed persistent tracker metadata to enforce the strict 2-day rule in CI/CD
    history_embed_tag = f'<script id="catalyst-tracker-data" type="application/json">\n{json.dumps(history_state, indent=2)}\n</script>'

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Executive Briefing Dashboard</title>
  <style>
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{ margin: 0; background-color: #f1f5f9; color: #0f172a; padding: 16px; }}
    @keyframes pulse-alert {{ 0%{{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);}} 50%{{border-color:#b91c1c;box-shadow:0 0 18px 5px rgba(239,68,68,0.55);}} 100%{{border-color:#ef4444;box-shadow:0 0 0 0 rgba(239,68,68,0.65);}} }}
    .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  </style>
</head>
<body>

  <!-- Modal Dialog -->
  <div id="reasons-modal-overlay" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(15,23,42,0.65);z-index:9999;align-items:center;justify-content:center;backdrop-filter:blur(3px);">
    <div style="background:#ffffff;border-radius:14px;padding:24px;max-width:540px;width:90%;box-shadow:0 20px 25px -5px rgba(0,0,0,0.2);position:relative;border:1px solid #e2e8f0;">
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f1f5f9;padding-bottom:12px;margin-bottom:14px;">
        <h3 id="modal-title" style="margin:0;font-size:18px;color:#0f172a;font-weight:800;"></h3>
        <button onclick="closeReasonsModal()" style="background:transparent;border:none;font-size:20px;cursor:pointer;color:#64748b;font-weight:700;">✕</button>
      </div>
      <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:8px;">💡 Key Actionable Reasons:</div>
      <ul id="modal-reasons-list" style="padding-left:20px;margin-top:0;margin-bottom:18px;font-size:13px;"></ul>
      <div style="display:flex;justify-content:flex-end;">
        <button onclick="closeReasonsModal()" style="background:#0f172a;color:#ffffff;border:none;padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;">Understood</button>
      </div>
    </div>
  </div>

  <!-- Centered Privacy Executive Wealth Header -->
  <div style="display:flex;flex-direction:column;align-items:center;gap:12px;width:100%;margin:10px auto 20px auto;">
    <button id="wealth-toggle-btn" onclick="toggleTabRow()" style="background:#ffffff;border:1px solid #cbd5e1;padding:8px 20px;border-radius:8px;font-size:13px;font-weight:700;color:#0f172a;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,0.05);display:inline-flex;align-items:center;gap:8px;">
      <span>💼 Executive Wealth Summary</span>
      <span style="font-size:11px;color:#64748b;font-weight:500;">(Click to view tabs)</span>
    </button>
    <div id="kpi-tab-bar" style="display:none;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;">
      <button onclick="toggleKpiCard(1)" style="background:#0f172a;color:#ffffff;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Total Liquid</button>
      <button onclick="toggleKpiCard(2)" style="background:#0284c7;color:#ffffff;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Total UC Retirement</button>
      <button onclick="toggleKpiCard(3)" style="background:#059669;color:#ffffff;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Active Brokerage</button>
      <button onclick="toggleKpiCard(4)" style="background:#475569;color:#ffffff;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Today's Brokerage</button>
    </div>
  </div>

  <!-- Metric Cards Grid (Reveals All 4 Simultaneously) -->
  <div id="kpi-cards-grid" style="display:none;margin-top:14px;margin-bottom:20px;grid-template-columns:repeat(4,1fr);gap:16px;width:100%;">
    <div id="kpi-card-1" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TOTAL LIQUID NET WORTH</div>
      <div style="font-size:26px;font-weight:800;color:#0f172a;margin-top:4px;">{summary['total_net_worth']}</div>
      <div style="font-size:13px;color:#64748b;font-weight:500;margin-top:4px;">Brokerage + Crypto + Full UC Benefits</div>
    </div>
    <div id="kpi-card-2" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TOTAL UC RETIREMENT & PENSION</div>
      <div style="font-size:26px;font-weight:800;color:#0284c7;margin-top:4px;">{summary['uc_total_balance']}</div>
      <div style="font-size:13px;color:#0284c7;font-weight:700;margin-top:4px;">UCRP ({summary['ucrp_balance']}) + DC Plans ({summary['uc_dc_balance']})</div>
    </div>
    <div id="kpi-card-3" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">ACTIVE BROKERAGE EQUITY</div>
      <div style="font-size:26px;font-weight:800;color:#059669;margin-top:4px;">{summary['brokerage_equity']}</div>
      <div style="font-size:13px;color:#059669;font-weight:700;margin-top:4px;">{summary['all_time_dollar']} ({summary['all_time_pct']} ROI)</div>
    </div>
    <div id="kpi-card-4" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TODAY'S BROKERAGE GAIN</div>
      <div style="font-size:26px;font-weight:800;color:{day_color};margin-top:4px;">{summary['day_dollar']}</div>
      <div style="font-size:13px;color:{day_color};font-weight:700;margin-top:4px;">{summary['day_pct']} Intraday</div>
    </div>
  </div>

  <!-- Catalyst Alert Banner -->
  {catalyst_banner_html}

  <!-- 3-Column Executive Dashboard Body -->
  <div style="display:flex;gap:20px;width:100%;align-items:flex-start;">
    
    <!-- LEFT COLUMN: Weather -->
    <div style="width:320px;flex-shrink:0;">
      <div class="card">
        <h2 id="weather-card-title" style="font-size:18px;margin-top:0;margin-bottom:12px;">Weather 14-Day</h2>
        <div id="weather-forecast-list">Loading forecast...</div>
      </div>
    </div>

    <!-- CENTER COLUMN: Live Sports & Executive News -->
    <div style="flex:1;">
      <!-- Sports Desk -->
      <div class="card">
        <h2 style="font-size:18px;margin-top:0;margin-bottom:14px;">⚾ Sports Desk: San Diego Padres & MLB</h2>
        <div class="grid-2">
          <div>
            <div id="padres-live-box" style="margin-bottom:10px;font-size:13px;color:#475569;font-weight:600;"></div>
            {padres_html}
          </div>
          <div>
            <div style="margin-bottom:10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;">MLB League Stories</div>
            {mlb_html}
          </div>
        </div>
      </div>

      <!-- Executive News -->
      <div class="card">
        <h2 style="font-size:18px;margin-top:0;margin-bottom:14px;">🌐 Executive News (World & San Diego)</h2>
        <div class="grid-2">
          <div>
            <div style="margin-bottom:10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;">BBC World News</div>
            {world_html}
          </div>
          <div>
            <div style="margin-bottom:10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;">FOX 5 San Diego Local</div>
            {sd_html}
          </div>
        </div>
      </div>

      <!-- AI, Tech & Breakthroughs -->
      <div class="card">
        <h2 style="font-size:18px;margin-top:0;margin-bottom:14px;">🤖 AI, Big Tech & Industry Breakthroughs</h2>
        <div>{tech_html}</div>
      </div>
    </div>

    <!-- RIGHT COLUMN: Retirement Tracker & Portfolios -->
    <div style="width:350px;flex-shrink:0;">
      <!-- UC Retirement Card -->
      <div class="card">
        <div style="font-weight:800;font-size:15px;color:#0f172a;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
          <span>🏛️ UC Retirement & Pension</span>
          <span style="font-size:11px;font-weight:600;color:#64748b;">As of {summary['retirement_as_of']}</span>
        </div>
        <div style="padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-weight:700;font-size:13px;color:#1e293b;">UCRP Pension (2013 Tier)</div>
            <div style="font-size:11px;color:#64748b;">{summary['ucrp_service']} Service Credit</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:800;font-size:14px;color:#0f172a;">{summary['ucrp_balance']}</div>
            <div style="font-size:11px;color:#0284c7;font-weight:700;">Defined Benefit</div>
          </div>
        </div>
        <div style="padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-weight:700;font-size:13px;color:#1e293b;">UC 403(B) (Pre-Tax)</div>
            <div style="font-size:11px;color:#64748b;">UC Pathway 2040</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:800;font-size:14px;color:#0f172a;">{summary['plan_403b_bal']}</div>
            <div style="font-size:11px;color:#059669;font-weight:700;">{summary['plan_403b_gain']} ({summary['plan_403b_pct']})</div>
          </div>
        </div>
        <div style="padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-weight:700;font-size:13px;color:#1e293b;">UC 457(B) (Roth After-Tax)</div>
            <div style="font-size:11px;color:#64748b;">UC Pathway 2040</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:800;font-size:14px;color:#0f172a;">{summary['plan_457b_bal']}</div>
            <div style="font-size:11px;color:#059669;font-weight:700;">{summary['plan_457b_gain']} ({summary['plan_457b_pct']})</div>
          </div>
        </div>
        <div style="margin-top:10px;padding:8px;background:#f8fafc;border-radius:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#334155;">
          <span><strong>Total Institutional:</strong> {summary['uc_total_balance']}</span>
          <span style="font-weight:700;color:#0284c7;">Health & Welf: {summary['ucrp_service']}</span>
        </div>
      </div>

      <!-- Active Portfolio Holdings -->
      <div class="card">
        <h2 style="font-size:16px;margin-top:0;margin-bottom:12px;">📊 Portfolio Pulse (Holdings)</h2>
        <div>{holdings_html}</div>
      </div>

      <!-- Watchlist -->
      <div class="card">
        <h2 style="font-size:16px;margin-top:0;margin-bottom:12px;">🎯 Watchlist Catalyst Radar</h2>
        <div>{watchlist_html}</div>
      </div>
    </div>

  </div>

  {history_embed_tag}
  <script>
    {DEFAULT_JS}
  </script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("Dashboard build complete.")

if __name__ == "__main__":
    run_agent()