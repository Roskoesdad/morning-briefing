import os, re, time, urllib.request, json, base64, feedparser
import yfinance as yf
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
      h+='<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #f1f5f9;font-size:12px;line-height:1.2;"><div><strong>'+day+'</strong> <span style="font-size:10px;color:#94a3b8;">'+md+'</span></div><span style="color:#64748b;font-size:11px;">'+desc+'</span><strong style="font-size:12px;">'+max+'° <span style="font-weight:400;color:#94a3b8;font-size:10px;">/ '+min+'°</span></strong></div>';
    }
    c.innerHTML=h;
  }catch(e){c.innerHTML='<div style="color:#94a3b8;font-size:12px;">Weather syncing...</div>';}
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
    "cHggc29saWQgI2UyZThmMCwgYm9yZGVyLXJhZGl1cyAxMnB4LCBwYWRkaW5nIDE2cHguIFN0YXJ0"
    "IGF0IHRvcCBlZGdlLgozLiBDU1MgS0VZRlJBTUU6IEBrZXlmcmFtZXMgcHVsc2UtYWxlcnQgeyAw"
    "JXtib3JkZXItY29sb3I6I2VmNDQ0NDtib3gtc2hhZG93OjAgMCAwIDAgcmdiYSgyMzksNjgsNjgs"
    "MC42NSk7fSA1MCUre2JvcmRlci1jb2xvcjojYjkxYzFjO2JveC1zaGFkb3c6MCAwIDE4cHggNXB4"
    "IHJnYmEoMjM5LDY4LDY4LDAuNTUpO30gMTAwJXtib3JkZXItY29sb3I6I2VmNDQ0NDtib3gtc2hh"
    "ZG93OjAgMCAwIDAgcmdiYSgyMzksNjgsNjgsMC42NSk7fSB9CjQuIENBVEFMWVNUIFJBREFSIEJB"
    "Tk5FUjogSWYgJ2NhdGFseXN0cycgYXJyYXkgaXMgbm9uLWVtcHR5LCByZW5kZXIgYW4gYWxlcnQg"
    "Y29udGFpbmVyIHNwYW5uaW5nIGZ1bGwgd2lkdGggYWJvdmUgdGhlIHRocmVlIGNvbHVtbnMgKHBh"
    "ZGRpbmcgMTZweCAyNHB4LCBtYXJnaW4tYm90dG9tIDIwcHgsIGJvcmRlciAzcHggc29saWQgI2Vm"
    "NDQ0NCwgYmFja2dyb3VuZCAjZmZmNWY1LCBhbmltYXRpb24gcHVsc2UtYWxlcnQgMS41cyBpbmZp"
    "bml0ZSwgZGlzcGxheSBmbGV4LCBhbGlnbi1pdGVtcyBjZW50ZXIsIGp1c3RpZnktY29udGVudCBz"
    "cGFjZS1iZXR3ZWVuKS4gSWYgZW1wdHksIHJlbmRlciBub3RoaW5nLgo1LiBUSFJFRS1DT0xVTU4g"
    "VE9QIExFVkVMIExBWU9VVDoKICAgLSBMRUZUICgyNDBweCB3aWR0aCwgYWxpZ24tc2VsZjogZmxl"
    "eC1zdGFydCk6ICdTcHJpbmcgVmFsbGV5IDE0LURheScgY2FyZC4gS2VlcCB0aWdodCwgZG8gTk9U"
    "IHN0cmV0Y2ggdmVydGljYWxseSwgc28gaXQgZml0cyBuZWF0bHkgb24gcGFnZSAxLiBDb250YWlu"
    "cyA8ZGl2IGlkPSd3ZWF0aGVyLWZvcmVjYXN0LWxpc3QnPkxvYWRpbmcgZm9yZWNhc3QuLi48L2Rp"
    "dj4KICAgLSBDRU5URVIgKGZsZXg6IDEpOiBUb3AgY2FyZCAnU3BvcnRzIERlc2s6IFNhbiBEaWVn"
    "byBQYWRyZXMgJiBNTEInIHdpdGggMiBzaW11bHRhbmVvdXMgc2lkZS1ieS1zaWRlIGNvbHVtbnMg"
    "KGxlZnQ6IFBhZHJlcyB3aXRoIDxkaXYgaWQ9J3BhZHJlcy1saXZlLWJveCc+PC9kaXY+IGFuZCA1"
    "IFBhZHJlcyBsaW5rcyB3aXRoIDQ2eDQ2IFNEIGxvZ287IHJpZ2h0OiA1IE1MQiBsaW5rcyB3aXRo"
    "IDQ2eDQ2IE1MQiBsb2dvKS4gTWlkZGxlIGNhcmQgJ0V4ZWN1dGl2ZSBOZXdzIChXb3JsZCAmIFNh"
    "biBEaWVnbyknIHdpdGggMiBzaW11bHRhbmVvdXMgc2lkZS1ieS1zaWRlIGNvbHVtbnMgKGxlZnQ6"
    "IFRvcCA1IFdvcmxkIEhlYWRsaW5lczsgcmlnaHQ6IFRvcCA1IEZPWCBRUjUgU2FuIERpZWdvIExv"
    "Y2FsIE5ld3Mgd2l0aCBzdG9yeSBpbWFnZSB0aHVtYm5haWxzKS4gQm90dG9tIGNhcmQgJ0FJLCBC"
    "aWcgVGVjaCAmIEluZHVzdHJ5IEJyZWFrdGhyb3VnaHMnICgyLWNvbHVtbiBjYXJkIGdyaWQgb2Yg"
    "ZXhhY3RseSAxMCBpdGVtcyBmcm9tICdhaSc6IDQgZnJvbSBBcnMgVGVjaG5pY2EsIDQgZnJvbSBU"
    "aGUgRGVjb2RlciwgMiBmcm9tIFRlY2hDcnVuY2gsIGVhY2ggd2l0aCA1MHg1MCB0aHVtYm5haWwg"
    "YW5kIGNsaWNrYWJsZSB0aXRsZSkuCiAgIC0gUklHSFQgKDM1MHB4IHdpZHRoKTogVG9wIGNhcmQg"
    "J1BvcnRmb2xpbyBQdWxzZScgd2l0aCBOTyBJTlRFUk5BTCBTQ1JPTExCQVIgKG5vIG1heC1oZWln"
    "aHQsIG5vIG92ZXJmbG93LXk6IGF1dG8pLiBFYWNoIGhvbGRpbmcgaXRlbSBNVVNUIGJlIGFuIGFj"
    "dGl2ZSBjbGlja2FibGUgaHlwZXJsaW5rIDxhIGhyZWY9J3VybCcgdGFyZ2V0PSdfYmxhbmsnIHJl"
    "bD0nbm9vcGVuZXIgbm9yZWZlcnJlcicgc3R5bGU9J2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRl"
    "bnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMDtib3JkZXIt"
    "Ym90dG9tOjFweCBzb2xpZCAjZjFmNWY5O3RleHQtZGVjb3JhdGlvbjpub25lO2NvbG9yOmluaGVy"
    "aXQ7Jz4uIFNob3cgdGlja2VyLCBwcmljZSwgYW5kICUgYmFkZ2UuIERpcmVjdGx5IGJlbG93IHNp"
    "dHMgJ1dhdGNobGlzdCBDYXRhbHlzdCBSYWRhcicgY2FyZCB3aXRoIHRoZSBzYW1lIGNsaWNrYWJs"
    "ZSBzdHlsZS4KNi4gSW5zZXJ0IG1hcmtlciBbW1dFQVRIRVJfQU5EX1BBRFJFU19KU11dIGltbWVk"
    "aWF0ZWx5IGJlZm9yZSA8L2JvZHk+Lgo3LiBSZXR1cm4gT05MWSBjbGVhbiwgdmFsaWQgcmF3IEhU"
    "TUwgc3RhcnRpbmcgd2l0aCA8IURPQ1RZUEUgaHRtbD4gYW5kIGVuZGluZyB3aXRoIDwvaHRtbD4u"
    "IERvIG5vdCBpbmNsdWRlIG1hcmtkb3duIGNvZGUgYmxvY2sgYmFja3RpY2tzLg=="
)

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
    signals, dod = [], ""
    try:
        req = urllib.request.Request("https://www.defense.gov/News/Contracts/", headers={"User-Agent": "Mozilla/5.0"})
        dod = BeautifulSoup(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"), "html.parser").get_text().lower()
    except Exception:
        pass
    seen = set()
    for tkr in (HOLDINGS + WATCHLIST + DISCOVERY):
        if "-USD" in tkr or tkr in seen:
            continue
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
                url = f"https://finance.yahoo.com/quote/{tkr}"
                if has_c and pct >= 0:
                    signals.append({"ticker": tkr, "group": grp, "type": "DoD Award", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Federal award identified. Volume: {vr:.1f}x.", "url": url})
                elif vr >= 1.75 and pct >= 2.0:
                    signals.append({"ticker": tkr, "group": grp, "type": "Volume Breakout", "vol_ratio": f"{vr:.1f}x", "pct": f"{pct:+.2f}%", "summary": f"Volume breakout ({vr:.1f}x) on upward move.", "url": url})
        except Exception:
            pass
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
    template = base64.b64decode(PROMPT_B64.encode("ascii")).decode("utf-8")
    instruction = template.replace("__DATA_JSON__", json.dumps(payload))
    
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