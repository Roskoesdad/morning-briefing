import os, re, time, urllib.request, json, feedparser
from datetime import datetime, date
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
        "benchmark_date": "2026-10-21",
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
                "base_service_credit": 12.6114,
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

# Active Watchlist (High secular contract / infrastructure candidates)
WATCHLIST = ["USAR", "ISRG", "LMT", "MU", "ANET", "CSCO", "VRT", "AVGO"]

# Broad-Market Scanner (S&P 500 & Nasdaq Leaders)
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
    reasons = ["Secular growth driver acceleration.", "Substantial valuation discount against institutional price targets.", "Expanding capital efficiency and market share."];
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
  const toggleBtnSub = document.getElementById('wealth-toggle-subtext');
  if(!row || !cardsContainer) return;
  
  const isCurrentlyShown = cardsContainer.style.display === 'grid';
  if(isCurrentlyShown){
    row.style.display = 'none';
    cardsContainer.style.display = 'none';
    for(let i=1; i<=4; i++){
      const c = document.getElementById('kpi-card-' + i);
      if(c) c.style.display = 'none';
    }
    if(toggleBtnSub) toggleBtnSub.innerText = '(Click to reveal summary)';
  } else {
    row.style.display = 'flex';
    cardsContainer.style.display = 'grid';
    for(let i=1; i<=4; i++){
      const c = document.getElementById('kpi-card-' + i);
      if(c) c.style.display = 'block';
    }
    if(toggleBtnSub) toggleBtnSub.innerText = '(Click to hide summary)';
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
        prompt = f"""Provide exactly 3 concise, highly actionable institutional reasons why an investor would choose to {action_type.upper()} {company_name} ({ticker}) right now.
Current Price: ${price:.2f}, Target Price: ${target:.2f}, Upside: {upside:.1f}%, Consensus: {rec}.
Highlight fundamental catalysts: expanding government contracts, secular AI/defense tailwinds, massive backlogs, or margin multiple expansion.
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
            f"Government Contract & Defense Tailwind: Expanding federal mission awards and infrastructure spend provide guaranteed multi-year backlog for {company_name}.",
            f"Substantial Margin of Safety: Consensus 12-month mean target offers +{upside:.0f}% upside with high institutional backing.",
            "Accelerating Secular Demand: Operating leverage and expanding commercial penetration drive multiple expansion."
        ]
    return [
        f"Valuation Cap: Current market price (${price:.2f}) leaves limited upside against the 12-month mean target.",
        f"Sector Rebalancing: Multiple expansion for {company_name} creates potential for capital rotation into discounted opportunities.",
        "Capital Efficiency: Reallocating proceeds into higher upside holdings offers improved risk-adjusted growth."
    ]

def calculate_portfolio_summary():
    """Calculates all-time returns, day gains, dynamic service credit counter, and total valuation."""
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

    bench_date = datetime.strptime(ret_data.get("benchmark_date", "2026-10-21"), "%Y-%m-%d").date()
    today = date.today()
    days_elapsed = max(0, (today - bench_date).days)
    dynamic_service = ucrp["base_service_credit"] + (days_elapsed / 365.25)

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
        "ucrp_service": f"{dynamic_service:.2f} yrs",
        "service_counter_display": f"{dynamic_service:.2f}",
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
    """Reads persistent catalyst history embedded directly into index.html across GitHub Actions runs."""
    html_file = "index.html"
    if os.path.exists(html_file):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
                m = re.search(r'<script id="catalyst-tracker-data" type="application/json">\s*({.*?})\s*</script>', content, re.DOTALL)
                if m:
                    return json.loads(m.group(1))
        except Exception:
            pass
    return {}

def filter_active_catalysts(raw_signals):
    """
    Suppresses any stock alert that has triggered across 2 days.
    History is tracked by the specific primary ticker and saved into index.html metadata.
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

    stale_keys = [k for k in list(history.keys()) if k not in current_keys]
    for k in stale_keys:
        del history[k]

    return active_signals, history

def get_catalysts():
    """
    Value-Investing & High-Probability Growth Catalyst Engine:
    1. SELL: Flags portfolio holdings ONLY if fundamentally downgraded or trading >20% above consensus intrinsic target.
    2. STANDALONE BUY: Identifies secular breakout / contract winners (+3.5%+ volume surge or +25%+ margin of safety).
    """
    signals = []
    candidates_pool = []
    
    # 1. Evaluate Portfolio Holdings (Conservative Value Standard - No Dip Selling)
    for tkr in PORTFOLIO_CONFIG["equities"].keys():
        try:
            t = yf.Ticker(tkr)
            fi = getattr(t, "fast_info", None)
            info = getattr(t, "info", {}) or {}
            
            price = fi.last_price if fi and fi.last_price else info.get("currentPrice")
            target = info.get("targetMeanPrice")
            rec = str(info.get("recommendationKey", "")).lower()
            num_analysts = info.get("numberOfAnalystOpinions", 0)
            c_name = COMPANY_NAMES.get(tkr, tkr)
            
            if price and target and target > 0 and price > 0:
                upside = ((target - price) / price) * 100.0
                analysis_url = f"https://finance.yahoo.com/quote/{tkr}/analysis"
                
                is_fundamental_downgrade = rec in ["sell", "strong_sell", "underperform"]
                is_severely_overvalued = upside <= -20.0
                
                if is_fundamental_downgrade or is_severely_overvalued:
                    badge = "STRONG SELL" if (rec == "strong_sell" or upside <= -25.0) else "SELL"
                    reasons_list = generate_reasons(tkr, "SELL", price, target, upside, rec)
                    reasons_encoded = urllib.parse.quote(json.dumps(reasons_list))
                    
                    signals.append({
                        "ticker": tkr,
                        "name": c_name,
                        "type": badge,
                        "upside_num": upside,
                        "current_price": f"${price:.2f}",
                        "analysts": num_analysts,
                        "url": analysis_url,
                        "reasons_encoded": reasons_encoded,
                        "is_sell": True
                    })
        except Exception:
            pass

    # 2. Scan Watchlist and Broad Leaders for Standalone High-Probability "BUY" Catalysts
    scan_buy_pool = WATCHLIST + BROAD_MARKET + list(PORTFOLIO_CONFIG["equities"].keys())
    seen_buy = set()
    for tkr in scan_buy_pool:
        if tkr in seen_buy or "-USD" in tkr:
            continue
        seen_buy.add(tkr)
        try:
            t = yf.Ticker(tkr)
            fi = getattr(t, "fast_info", None)
            info = getattr(t, "info", {}) or {}
            h = t.history(period="1mo")
            
            price = fi.last_price if fi and fi.last_price else info.get("currentPrice")
            target = info.get("targetMeanPrice")
            rec = str(info.get("recommendationKey", "")).lower()
            c_name = COMPANY_NAMES.get(tkr, tkr)
            
            if price and target and target > 0 and price > 0 and len(h) >= 15:
                upside = ((target - price) / price) * 100.0
                avg_v = float(h["Volume"].iloc[:-1].mean())
                tod_v = float(h["Volume"].iloc[-1])
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                day_pct = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100.0
                
                # Standalone BUY Criteria:
                # 1. Institutional surge: +3.5% day with heavy volume (1.4x+) and strong upside
                # 2. Or massive secular discount: Consensus Buy with >= 28% upside
                is_breakout_surge = day_pct >= 3.5 and vr >= 1.4 and upside >= 15.0
                is_high_margin_buy = rec in ["buy", "strong_buy"] and upside >= 28.0
                
                if is_breakout_surge or is_high_margin_buy:
                    candidates_pool.append({
                        "ticker": tkr,
                        "name": c_name,
                        "rec": rec,
                        "upside": upside,
                        "price": price,
                        "target": target,
                        "day_pct": day_pct,
                        "vr": vr,
                        "is_surge": is_breakout_surge,
                        "url": f"https://finance.yahoo.com/quote/{tkr}/analysis"
                    })
        except Exception:
            pass

    # Sort candidates by upside spread
    candidates_pool.sort(key=lambda x: x["upside"], reverse=True)
    best_replacement = candidates_pool[0] if candidates_pool else None
    
    # Pair any SELL alerts with the top replacement candidate
    for s in signals:
        if best_replacement:
            s["replacement_ticker"] = best_replacement["ticker"]
            s["replacement_name"] = best_replacement["name"]
            s["replacement_url"] = best_replacement["url"]
            s["replacement_text"] = f"{best_replacement['name']} (+{best_replacement['upside']:.0f}% upside)"
            buy_reasons_list = generate_reasons(best_replacement["ticker"], "BUY", best_replacement["price"], best_replacement["target"], best_replacement["upside"], best_replacement["rec"])
            s["replacement_reasons_encoded"] = urllib.parse.quote(json.dumps(buy_reasons_list))

    # 3. Add Standalone "BUY NOW" Catalysts (Independent of Sells)
    # If a high-probability breakout or government contract winner emerges, prompt a BUY alert directly
    for top_buy in candidates_pool[:2]:
        # Only add standalone buy if it's not already linked as a replacement sell pair
        if not any(s.get("replacement_ticker") == top_buy["ticker"] for s in signals):
            badge = "BUY NOW" if top_buy.get("is_surge") else "STRONG BUY"
            buy_reasons = generate_reasons(top_buy["ticker"], "BUY", top_buy["price"], top_buy["target"], top_buy["upside"], top_buy["rec"])
            signals.append({
                "ticker": top_buy["ticker"],
                "name": top_buy["name"],
                "type": badge,
                "upside_num": top_buy["upside"],
                "current_price": f"${top_buy['price']:.2f}",
                "url": top_buy["url"],
                "reasons_encoded": urllib.parse.quote(json.dumps(buy_reasons)),
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
        img_html = f'<img src="{it["image"]}" class="news-thumb" onerror="this.src=\'{T_LOGO}\'" />' if it.get("image") else ""
        out += f"""<a href="{it['link']}" target="_blank" rel="noopener noreferrer" class="news-link">
          {img_html}
          <span class="news-title">{it['title']}</span>
        </a>"""
    return out

def render_stock_list(quotes):
    out = ""
    for q in quotes:
        color = "#15803d" if q["positive"] else "#dc2626"
        badge_bg = "#dcfce7" if q["positive"] else "#fee2e2"
        out += f"""<a href="{q['url']}" target="_blank" rel="noopener noreferrer" style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #f1f5f9;text-decoration:none;color:inherit;">
          <div>
            <div style="font-weight:700;font-size:14px;color:#0f172a;">{q['name']}</div>
            <div style="font-size:12px;color:#64748b;">{q['ticker']}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:700;font-size:14px;color:#0f172a;">{q['price']}</div>
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700;color:{color};background:{badge_bg};margin-top:2px;">{q['pct']}</span>
          </div>
        </a>"""
    return out

def run_agent():
    print("Calculating portfolio metrics and syncing market data...")
    summary = calculate_portfolio_summary()

    ars = fetch_rss("https://feeds.arstechnica.com/arstechnica/technology-lab", 5, "ai")[:3]
    decoder = fetch_rss("https://the-decoder.com/feed/", 5, "ai")[:3]
    tc = fetch_rss("https://techcrunch.com/category/artificial-intelligence/feed/", 4, "ai")[:2]
    tech_all = (ars + decoder + tc)
    tech_left = tech_all[:4]
    tech_right = tech_all[4:8]

    padres, mlb = fetch_padres_stories()
    world_news = fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml", 5)
    sd_news = fetch_fox5()
    holdings_quotes = get_quotes(HOLDINGS)
    watchlist_quotes = get_quotes(WATCHLIST)

    catalysts, history_state = get_catalysts()
    day_color = "#00c805" if summary["is_day_positive"] else "#ef4444"

    # Format the catalyst alert banner
    catalyst_banner_html = ""
    if catalysts:
        items_html = ""
        for item in catalysts:
            if item.get("is_sell"):
                # SELL ALERT with paired replacement
                items_html += f"""<div class="alert-pill">
                  <span style="background:#991b1b;color:#ffffff;font-size:11px;font-weight:700;padding:3px 7px;border-radius:4px;">{item['type']}</span>
                  <strong>{item['name']}</strong>
                  <button onclick="openReasonsModal('{item['name']}', 'SELL', '{item['reasons_encoded']}')" style="background:none;border:none;color:#dc2626;font-weight:700;font-size:13px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                  <span class="buy-section">
                    🔄 Buy: <a href="{item.get('replacement_url', '#')}" target="_blank" rel="noopener noreferrer" style="color:#15803d;font-weight:700;text-decoration:none;">{item.get('replacement_text', '')} ↗</a>
                    <button onclick="openReasonsModal('{item.get('replacement_name', '')}', 'BUY', '{item.get('replacement_reasons_encoded', '')}')" style="background:none;border:none;color:#15803d;font-weight:700;font-size:13px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                  </span>
                </div>"""
            else:
                # STANDALONE BUY ALERT (Breakout, contract momentum, high secular upside)
                items_html += f"""<div class="alert-pill" style="border-color:#bbf7d0;background:#f0fdf4;">
                  <span style="background:#15803d;color:#ffffff;font-size:11px;font-weight:700;padding:3px 7px;border-radius:4px;">{item['type']}</span>
                  <strong style="color:#14532d;">{item['name']}</strong>
                  <button onclick="openReasonsModal('{item['name']}', 'BUY', '{item['reasons_encoded']}')" style="background:none;border:none;color:#15803d;font-weight:700;font-size:13px;cursor:pointer;text-decoration:underline;padding:0;">↗ 3 reasons why</button>
                </div>"""
        
        catalyst_banner_html = f"""<div class="catalyst-container">
          <div style="display:inline-flex;align-items:center;background:#0f172a;color:#ffffff;font-weight:700;padding:7px 14px;border-radius:6px;font-size:13px;flex-shrink:0;">⚡ CATALYST RADAR</div>
          <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;flex:1;">{items_html}</div>
        </div>"""

    padres_html = render_news_items(padres)
    mlb_html = render_news_items(mlb)
    world_html = render_news_items(world_news)
    sd_html = render_news_items(sd_news)
    
    tech_html = f"""<div class="grid-2">
      <div>
        <div style="margin-bottom:10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;">AI Breakthroughs & Labs</div>
        {render_news_items(tech_left)}
      </div>
      <div>
        <div style="margin-bottom:10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;">Big Tech & Cloud Insights</div>
        {render_news_items(tech_right)}
      </div>
    </div>"""

    holdings_html = render_stock_list(holdings_quotes)
    watchlist_html = render_stock_list(watchlist_quotes)

    # Embed tracker state to ensure suppression across runs
    history_embed_tag = f'<script id="catalyst-tracker-data" type="application/json">\n{json.dumps(history_state, indent=2)}\n</script>'

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-status-bar-style" content="default"/>
  <title>Executive Briefing Dashboard</title>
  <style>
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{ margin: 0; background-color: #f1f5f9; color: #0f172a; padding: 16px; -webkit-text-size-adjust: 100%; }}
    @keyframes pulse-alert {{ 0%{{border-color:#3b82f6;box-shadow:0 0 0 0 rgba(59,130,246,0.65);}} 50%{{border-color:#1d4ed8;box-shadow:0 0 18px 5px rgba(59,130,246,0.45);}} 100%{{border-color:#3b82f6;box-shadow:0 0 0 0 rgba(59,130,246,0.65);}} }}
    
    .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }}
    
    /* Layout Containers */
    .dashboard-layout {{ display: flex; gap: 20px; width: 100%; align-items: flex-start; }}
    .col-left {{ width: 320px; flex-shrink: 0; }}
    .col-center {{ flex: 1; min-width: 0; }}
    .col-right {{ width: 350px; flex-shrink: 0; }}
    
    .kpi-grid {{ display: grid; margin-top: 14px; margin-bottom: 20px; grid-template-columns: repeat(4, 1fr); gap: 16px; width: 100%; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    
    .news-link {{ display: flex; align-items: center; padding: 11px 0; border-bottom: 1px solid #f1f5f9; text-decoration: none; color: #1e293b; transition: background 0.15s ease; }}
    .news-thumb {{ width: 44px; height: 44px; border-radius: 6px; object-fit: cover; flex-shrink: 0; margin-right: 12px; }}
    .news-title {{ font-size: 13.5px; font-weight: 600; line-height: 1.45; }}
    
    .catalyst-container {{ margin-bottom: 20px; padding: 14px 20px; border: 2px solid #3b82f6; background: #eff6ff; animation: pulse-alert 2s infinite; display: flex; align-items: center; justify-content: flex-start; flex-wrap: wrap; gap: 12px; border-radius: 14px; }}
    .alert-pill {{ display: inline-flex; align-items: center; padding: 9px 14px; background: #ffffff; border: 1px solid #fecaca; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); flex-wrap: wrap; gap: 8px; }}
    .buy-section {{ padding-left: 10px; border-left: 1px solid #fca5a5; display: inline-flex; align-items: center; gap: 6px; }}
    
    /* Mobile / Safari iPhone Responsive Styles (< 900px) */
    @media screen and (max-width: 900px) {{
      body {{ padding: 10px; }}
      .dashboard-layout {{ display: flex; flex-direction: column; width: 100%; gap: 12px; }}
      .col-left, .col-center, .col-right {{ width: 100% !important; flex: none !important; }}
      
      .kpi-grid {{ grid-template-columns: 1fr 1fr !important; gap: 10px !important; }}
      .kpi-card {{ padding: 14px !important; }}
      .kpi-value {{ font-size: 20px !important; }}
      
      .grid-2 {{ grid-template-columns: 1fr !important; gap: 12px !important; }}
      
      .alert-pill {{ width: 100%; display: flex; justify-content: space-between; }}
      .buy-section {{ border-left: none; padding-left: 0; border-top: 1px dashed #fca5a5; padding-top: 6px; width: 100%; margin-top: 4px; }}
      
      .news-title {{ font-size: 14px !important; }}
      .card {{ padding: 14px !important; margin-bottom: 12px !important; }}
    }}
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

  <!-- Centered Executive Wealth Header (Open by Default on Launch) -->
  <div style="display:flex;flex-direction:column;align-items:center;gap:12px;width:100%;margin:10px auto 20px auto;">
    <button id="wealth-toggle-btn" onclick="toggleTabRow()" style="background:#ffffff;border:1px solid #cbd5e1;padding:9px 22px;border-radius:8px;font-size:13px;font-weight:700;color:#0f172a;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,0.05);display:inline-flex;align-items:center;gap:8px;">
      <span>💼 Executive Wealth Summary</span>
      <span id="wealth-toggle-subtext" style="font-size:11px;color:#64748b;font-weight:500;">(Click to hide summary)</span>
    </button>
    <div id="kpi-tab-bar" style="display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;">
      <button onclick="toggleKpiCard(1)" style="background:#0f172a;color:#ffffff;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Total Liquid</button>
      <button onclick="toggleKpiCard(2)" style="background:#0284c7;color:#ffffff;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Total UC Retirement</button>
      <button onclick="toggleKpiCard(3)" style="background:#059669;color:#ffffff;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Active Brokerage</button>
      <button onclick="toggleKpiCard(4)" style="background:#475569;color:#ffffff;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Today's Brokerage</button>
    </div>
  </div>

  <!-- Metric Cards Grid (Displayed by Default in 4 cols on Desktop, 2x2 on Phone) -->
  <div id="kpi-cards-grid" class="kpi-grid">
    <div id="kpi-card-1" class="kpi-card" style="display:block;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TOTAL LIQUID NET WORTH</div>
      <div class="kpi-value" style="font-size:26px;font-weight:800;color:#0f172a;margin-top:4px;">{summary['total_net_worth']}</div>
      <div style="font-size:12px;color:#64748b;font-weight:500;margin-top:4px;">Brokerage + Crypto + Full UC Benefits</div>
    </div>
    <div id="kpi-card-2" class="kpi-card" style="display:block;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TOTAL UC RETIREMENT & PENSION</div>
      <div class="kpi-value" style="font-size:26px;font-weight:800;color:#0284c7;margin-top:4px;">{summary['uc_total_balance']}</div>
      <div style="font-size:12px;color:#0284c7;font-weight:700;margin-top:4px;">UCRP ({summary['ucrp_balance']}) + DC Plans ({summary['uc_dc_balance']})</div>
    </div>
    <div id="kpi-card-3" class="kpi-card" style="display:block;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">ACTIVE BROKERAGE EQUITY</div>
      <div class="kpi-value" style="font-size:26px;font-weight:800;color:#059669;margin-top:4px;">{summary['brokerage_equity']}</div>
      <div style="font-size:12px;color:#059669;font-weight:700;margin-top:4px;">{summary['all_time_dollar']} ({summary['all_time_pct']} ROI)</div>
    </div>
    <div id="kpi-card-4" class="kpi-card" style="display:block;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">TODAY'S BROKERAGE GAIN</div>
      <div class="kpi-value" style="font-size:26px;font-weight:800;color:{day_color};margin-top:4px;">{summary['day_dollar']}</div>
      <div style="font-size:12px;color:{day_color};font-weight:700;margin-top:4px;">{summary['day_pct']} Intraday</div>
    </div>
  </div>

  <!-- Catalyst Alert Banner (Hidden if no active signals or suppressed) -->
  {catalyst_banner_html}

  <!-- Responsive 3-Column Desktop / 1-Column iPhone Layout -->
  <div class="dashboard-layout">
    
    <!-- LEFT: Weather -->
    <div class="col-left">
      <div class="card">
        <h2 id="weather-card-title" style="font-size:18px;margin-top:0;margin-bottom:12px;">Weather 14-Day</h2>
        <div id="weather-forecast-list">Loading forecast...</div>
      </div>
    </div>

    <!-- CENTER: Sports, Executive News, AI & Big Tech -->
    <div class="col-center">
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

      <!-- AI, Big Tech & Industry Breakthroughs -->
      <div class="card">
        <h2 style="font-size:18px;margin-top:0;margin-bottom:14px;">🤖 AI, Big Tech & Industry Breakthroughs</h2>
        {tech_html}
      </div>
    </div>

    <!-- RIGHT: Institutional UC Retirement & Live Portfolio Stock Quotes -->
    <div class="col-right">
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
        <!-- Enlarged Footer Row with "Total:" and dynamic "Years of Service:" counter -->
        <div style="margin-top:12px;padding:12px 14px;background:#f8fafc;border-radius:8px;display:flex;justify-content:space-between;align-items:center;font-size:13.5px;color:#1e293b;border:1px solid #e2e8f0;">
          <span><strong>Total:</strong> {summary['uc_total_balance']}</span>
          <span style="font-weight:800;color:#0284c7;font-size:14px;">Years of Service: {summary['service_counter_display']}</span>
        </div>
      </div>

      <!-- Active Portfolio Holdings Pulse -->
      <div class="card">
        <h2 style="font-size:16px;margin-top:0;margin-bottom:12px;">📊 Portfolio Pulse (Holdings)</h2>
        <div>{holdings_html}</div>
      </div>

      <!-- Watchlist Radar -->
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