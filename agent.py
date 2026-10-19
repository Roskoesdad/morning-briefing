import os, re, time, urllib.request, json, base64, feedparser, yfinance as yf
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

HOLDINGS = [
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT",
    "AAPL", "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD",
    "META", "GOOGL", "EQIX", "PLTR", "TSM", "VOO", "TMO"
]
WATCHLIST = ["USAR", "ISRG", "LMT", "MU", "WDC", "CSCO", "VRT", "AVGO"]
DISCOVERY = ["RTX", "NOC", "GD", "BA"]
ENTITY_MAP = {
    "PLTR": ["palantir"], "MSFT": ["microsoft"], "NVDA": ["nvidia"],
    "AMZN": ["amazon", "aws"], "EQIX": ["equinix"], "LMT": ["lockheed"],
    "USAR": ["usa rare earth"], "VRT": ["vertiv"], "AVGO": ["broadcom"],
    "MU": ["micron"], "CSCO": ["cisco"], "RTX": ["raytheon", "rtx"],
    "NOC": ["northrop"], "GD": ["general dynamics"], "TMO": ["thermo fisher"]
}
P_KEYS = ["padres", "san diego", "friars", "petco", "tatis", "machado", "merrill", "cease"]
P_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
M_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
T_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"

DEFAULT_JS = """async function updateWeather(){
  const c=document.getElementById('weather-forecast-list');if(!c)return;
  try{
    const r=await fetch('https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles&forecast_days=14');
    const d=await r.json();let h='';
    const codes={0:'☀️ Clear',1:'🌤️ Mostly Clear',2:'⛅ Pt Cloudy',3:'☁️ Overcast',45:'🌫️ Fog',51:'🌦️ Light Drizzle',61:'🌧️ Light Rain',63:'🌧️ Rain',80:'🌦️ Showers',95:'⛈️ Storm'};
    for(let i=0;i<d.daily.time.length;i++){
      const dt=new Date(d.daily.time[i]+'T12:00:00');
      const day=i===0?'Today':dt.toLocaleDateString('en-US',{weekday:'short'});
      const md=(dt.getMonth()+1)+'/'+dt.getDate();
      const max=Math.round(d.daily.temperature_2m_max[i]),min=Math.round(d.daily.temperature_2m_min[i]);
      const prob=d.daily.precipitation_probability_max?d.daily.precipitation_probability_max[i]:0;
      let desc=codes[d.daily.weathercode[i]]||'🌤️ Fair';
      if(prob>=35)desc='🌦️ Rain ('+prob+'%)';
      h+='<div style="display:flex;justify-content:space-between;align-items:center;padding:14px 6px;border-bottom:1px solid #f1f5f9;font-size:14px;"><div><strong>'+day+'</strong> <span style="font-size:11px;color:#94a3b8;">'+md+'</span></div><span style="color:#64748b;font-size:13px;">'+desc+'</span><strong>'+max+'° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ '+min+'°</span></strong></div>';
    }
    c.innerHTML=h;
  }catch(e){c.innerHTML='<div style="color:#94a3b8;">Weather syncing...</div>';}
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

PROMPT_B64 = (
    "R2VuZXJhdGUgYSBjb21wbGV0ZSwgc2luZ2xlLXBhZ2UgSFRNTCBleGVjdXRpdmUgYnJpZWZpbmcg"
    "ZGFzaGJvYXJkLgpEYXRhIHBheWxvYWQgSlNPTjoKX19EQVRBX0pTT05fXwoKTUFOREFUT1JZIERF"
    "U0lHTiBBTkQgU1RSVUNUVVJFIFJFUVVJUkVNRU5UUzoKMS4gTk8gVEFCUy4gRGlzcGxheSBhbGwg"
    "Y29udGVudCBpbiBvcGVuLCBzaW11bHRhbmVvdXMgc2lkZS1ieS1zaWRlIHNwbGl0IHBhbmVscy4K"
    "Mi4gRlVMTC1XSURUSCBMQVlPVVQ6IHdpZHRoIDk4dnc7IG1heC13aWR0aDogMTgyMHB4OyBtYXJn"
    "aW46IDAgYXV0bzsgcGFnZSBiYWNrZ3JvdW5kICNmMWY1Zjk7IGNhcmRzICNmZmZmZmYgd2l0aCAx"
    "cHggc29saWQgI2UyZThmMCwgYm9yZGVyLXJhZGl1cyAxMnB4LCBwYWRkaW5nIDE4cHguIFN0YXJ0"
    "IGF0IHRvcCBlZGdlLgozLiBDU1MgS0VZRlJBTUU6IEBrZXlmcmFtZXMgcHVsc2UtYWxlcnQgeyAw"
    "JXtib3JkZXItY29sb3I6I2VmNDQ0NDtib3gtc2hhZG93OjAgMCAwIDAgcmdiYSgyMzksNjgsNjgs"
    "MC42NSk7fSA1MCUre2JvcmRlci1jb2xvcjojYjkxYzFjO2JveC1zaGFkb3c6MCAwIDE4cHggNXB4"
    "IHJnYmEoMjM5LDY4LDY4LDAuNTUpO30gMTAwJXtib3JkZXItY29sb3I6I2VmNDQ0NDtib3gtc2hh"
    "ZG93OjAgMCAwIDAgcmdiYSgyMzksNjgsNjgsMC42NSk7fSB9CjQuIENBVEFMWVNUIFJBREFSIEJB"
    "Tk5FUjogSWYgJ2NhdGFseXN0cycgYXJyYXkgaXMgbm9uLWVtcHR5LCByZW5kZXIgYW4gYWxlcnQg"
    "Y29udGFpbmVyIHNwYW5uaW5nIGZ1bGwgd2lkdGggYWJvdmUgdGhlIHRocmVlIGNvbHVtbnMgKHBh"
    "ZGRpbmcgMThweCAyNnB4LCBtYXJnaW4tYm90dG9tIDIycHgsIGJvcmRlciAzcHggc29saWQgI2Vm"
    "NDQ0NCwgYmFja2dyb3VuZCAjZmZmNWY1LCBhbmltYXRpb24gcHVsc2UtYWxlcnQgMS41cyBpbmZp"
    "bml0ZSwgZGlzcGxheSBmbGV4LCBhbGlnbi1pdGVtcyBjZW50ZXIsIGp1c3RpZnktY29udGVudCBz"
    "cGFjZS1iZXR3ZWVuKS4gSWYgZW1wdHksIHJlbmRlciBub3RoaW5nLgo1LiBUSFJFRS1DT0xVTU4g"
    "VE9QIExFVkVMIExBWU9VVDoKICAgLSBMRUZUICgyNzBweCB3aWR0aCk6ICdTcHJpbmcgVmFsbGV5"
    "IDE0LURheSBGb3JlY2FzdCcgY2FyZC4gVmVydGljYWxseSBleHBhbmQgY2FyZCBkb3dud2FyZCBh"
    "bG9uZ3NpZGUgY2VudGVyIGZlZWQuIENvbnRhaW5zIDxkaXYgaWQ9J3dlYXRoZXItZm9yZWNhc3Qt"
    "bGlzdCcgc3R5bGU9J2Rpc3BsYXk6ZmxleDtmbGV4LWRpcmVjdGlvbjpjb2x1bW47anVzdGlmeS1j"
    "b250ZW50OnNwYWNlLWJldHdlZW47aGVpZ2h0OjEwMCU7Jz5Mb2FkaW5nIGZvcmVjYXN0Li4uPC9k"
    "aXY+CiAgIC0gQ0VOVEVSIChmbGV4OiAxKTogVG9wIGNhcmQgJ1Nwb3J0cyBEZXNrOiBTYW4gRGll"
    "Z28gUGFkcmVzICYgTUxCJyB3aXRoIDIgc2ltdWx0YW5lb3VzIHNpZGUtYnktc2lkZSBjb2x1bW5z"
    "IChsZWZ0OiBQYWRyZXMgd2l0aCA8ZGl2IGlkPSdwYWRyZXMtbGl2ZS1ib3gnPjwvZGl2PiBhbmQg"
    "NQogICAgIFBhZHJlcyBsaW5rcyB3aXRoIDQ2eDQ2IFNEIGxvZ287IHJpZ2h0OiA1IE1MQiBsaW5r"
    "cyB3aXRoIDQ2eDQ2IE1MQiBsb2dvKS4gTWlkZGxlIGNhcmQgJ0V4ZWN1dGl2ZSBOZXdzIChXb3Js"
    "ZCAmIFNhbiBEaWVnbyknIHdpdGggMiBzaW11bHRhbmVvdXMgc2lkZS1ieS1zaWRlIGNvbHVtbnMg"
    "KGxlZnQ6IFRvcCA1IFdvcmxkIEhlYWRsaW5lczsgcmlnaHQ6IFRvcCA1IEZPWCBRUjUgU2FuIERp"
    "ZWdvIExvY2FsIE5ld3Mgd2l0aCBzdG9yeSBpbWFnZSB0aHVtYm5haWxzKS4gQm90dG9tIGNhcmQg"
    "J0FJLCBCaWcgVGVjaCAmIEluZHVzdHJ5IEJyZWFrdGhyb3VnaHMnICgyLWNvbHVtbiBjYXJkIGdy"
    "aWQgb2YgZXhhY3RseSAxMCBpdGVtcyBmcm9tICdhaSc6IDQgZnJvbSBTbmFja3MsIDQgZnJvbSBU"
    "aGUgRGVjb2RlciwgMiBmcm9tIFRlY2hDcnVuY2gsIGVhY2ggd2l0aCA1MHg1MCB0aHVtYm5haWwg"
    "YW5kIGNsaWNrYWJsZSB0aXRsZSkuCiAgIC0gUklHSFQgKDMzMHB4IHdpZHRoKTogVG9wIGNhcmQg"
    "J1BvcnRmb2xpbyBQdWxzZScgd2l0aCBOTyBJTlRFUk5BTCBTQ1JPTExCQVIgKG5vIG1heC1oZWln"
    "aHQsIG5vIG92ZXJmbG93LXk6IGF1dG8pIGxpc3RpbmcgQUxMIGl0ZW1zIGluICdob2xkaW5ncycg"
    "c29ydGVkIGRlc2NlbmRpbmcgd2l0aCB0aWNrZXIsIHByaWNlLCBhbmQgJSBiYWRnZS4gRGlyZWN0"
    "bHkgYmVsb3cgc2l0cyAnV2F0Y2hsaXN0IENhdGFseXN0IFJhZGFyJyBjYXJkIGxpc3RpbmcgYWxs"
    "IGl0ZW1zIGluICd3YXRjaGxpc3QnLgo2LiBJbnNlcnQgbWFya2VyIFtbV0VBVEhFUl9BTkRfUEFE"
    "UkVTX0pTXV0gaW1tZWRpYXRlbHkgYmVmb3JlIDwvYm9keT4uCjcuIFJldHVybiBPTkxZIGNsZWFu"
    "LCB2YWxpZCByYXcgSFRNTCBzdGFydGluZyB3aXRoIDwhRE9DVFlQRSBodG1sPiBhbmQgZW5kaW5n"
    "IHdpdGggPC9odG1sPi4gRG8gbm90IGluY2x1ZGUgbWFya2Rvd24gY29kZSBibG9jayBiYWNrdGlj"
    "a3Mu"
)

def extract_thumb(e, cat="general"):
    for k in ["media_content", "enclosures"]:
        if k in e and e[k]:
            for it in e[k]:
                u = it.get("url") or it.get("href") or ""
                if any(x in u.lower() for x in [".jpg", ".jpeg", ".png", ".webp"]): return u
    if "media_thumbnail" in e and e.media_thumbnail: return e.media_thumbnail[0].get("url", "")
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
            if t: out.append({"title": t, "link": e.get("link", "#"), "image": extract_thumb(e, cat)})
    except Exception: pass
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
        except Exception: pass
    return padres, mlb

def fetch_padres_stories():
    p_scraped, mlb = scrape_mlb()
    p_final, seen = [p for p in p_scraped[:2]], {p["title"] for p in p_scraped[:2]}
    for it in fetch_rss("https://www.mlbtraderumors.com/san-diego-padres/feed", 8, "padres"):
        if len(p_final) >= 5: break
        if it["title"] not in seen: seen.add(it["title"]); p_final.append(it)
    if len(p_final) < 5:
        for it in fetch_rss("https://gaslampball.com/rss/index.xml", 8, "padres"):
            if len(p_final) >= 5: break
            if it["title"] not in seen: seen.add(it["title"]); p_final.append(it)
    return p_final[:5], mlb[:5]

def fetch_fox5():
    seen, out = set(), []
    for u in ["https://fox5sandiego.com/news/feed/", "https://fox5sandiego.com/feed/"]:
        for it in fetch_rss(u, 8, "general"):
            if it["title"] not in seen and len(it["title"]) > 10:
                seen.add(it["title"]); out.append(it)
                if len(out) >= 5: return out
    return out[:5]

def get_catalysts():
    signals, dod = [], ""
    try:
        req = urllib.request.Request("https://www.defense.gov/News/Contracts/", headers={"User-Agent": "Mozilla/5.0"})
        dod = BeautifulSoup(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"), "html.parser").get_text().lower()
    except Exception: pass
    seen = set()
    for tkr in (HOLDINGS + WATCHLIST + DISCOVERY):
        if "-USD" in tkr or tkr in seen: continue
        seen.add(tkr)
        has_c = any(a in dod for a in ENTITY_MAP.get(tkr, [tkr.lower()]))
        try:
            t = yf.Ticker(tkr)
            h = t.history(period="1mo")
            if len(h) >= 15:
                avg_v, tod_v = float(h["Volume"].iloc[:-1].mean()), float(h["Volume"].iloc[-1])
                pct = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100.0
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                grp = "Current Portfolio" if tkr in HOLDINGS else ("Active Watchlist" if tkr in WATCHLIST else "Discovery Opportunity")
                url = f"https://finance.yahoo.com/quote/{tkr}/"
                if has_c and pct >= 0:
                    signals.append({"ticker": tkr, "group": grp, "type": "DoD Award", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Federal award identified. Volume: {vr:.1f}x.", "url": url})
                elif vr >= 1.75 and pct >= 2.0:
                    signals.append({"ticker": tkr, "group": grp, "type": "Volume Breakout", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Volume breakout ({vr:.1f}x) on upward move.", "url": url})
        except Exception: pass
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
        except Exception: pass
        out