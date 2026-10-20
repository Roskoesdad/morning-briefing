import os, re, time, urllib.request, json, feedparser
import yfinance as yf
from bs4 import BeautifulSoup
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Portfolio Configuration & Exact Holdings
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
    }
}

HOLDINGS = list(PORTFOLIO_CONFIG["equities"].keys()) + list(PORTFOLIO_CONFIG["crypto"].keys())

# Active Watchlist (ANET backfilled, ORCL graduated to Holdings)
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
    m = re.