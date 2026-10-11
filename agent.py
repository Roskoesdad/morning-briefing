import os
import re
import time
import urllib.request
import json
import base64
import feedparser
import yfinance as yf
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

HOLDINGS = [
    "BTC-USD", "XRP-USD", "DOGE-USD", "SOL-USD", "BRK-B", "WMT", "AAPL",
    "AMZN", "MSFT", "NVDA", "DLTR", "VLO", "COST", "HOOD", "META",
    "GOOGL", "EQIX", "PLTR", "TSM", "VOO"
]
WATCHLIST = ["USAR", "ISRG", "LMT", "TMO", "MU", "WDC", "CSCO", "VRT", "AVGO"]
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
    "GD": ["general dynamics"]
}

PADRES_LOGO = "https://www.mlbstatic.com/team-logos/135.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"
TECH_LOGO = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&auto=format&fit=crop&q=60"
PADRES_KEYS = ["padres", "san diego", "friars", "petco", "cassavell", "lin", "morejon", "king", "france", "tatis", "machado", "merrill", "cease"]

def get_fin_url(t):
    return "https://finance.yahoo.com/quote/" + str(t) + "/"

def extract_thumb(e, cat="general"):
    if "media_thumbnail" in e and e.media_thumbnail:
        return e.media_thumbnail[0].get("url", "")
    if "media_content" in e and e.media_content:
        return e.media_content[0].get("url", "")
    c = e.get("content", [{}])[0].get("value", "") or e.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', c)
    if m:
        return m.group(1)
    return PADRES_LOGO if cat == "padres" else (MLB_LOGO if cat == "mlb" else TECH_LOGO)

def fetch_rss(url, limit=10, cat="general"):
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
            soup = BeautifulSoup(h, "html.parser")
            for a in soup.find_all("a", href=True):
                href, title = a["href"], a.get_text(strip=True)
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
    for item in fetch_rss("https://www.mlbtraderumors.com/san-diego-padres/feed", 8, "padres"):
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
        for item in fetch_rss("https://gaslampball.com/rss/index.xml", 8, "padres"):
            if len(p_final) >= 5:
                break
            if item["title"] not in seen:
                seen.add(item["title"])
                p_final.append(item)
    return p_final[:5], mlb[:5]

def get_catalyst_alerts():
    signals = []
    dod_text = ""
    try:
        url = "https://www.defense.gov/News/Contracts/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
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

                grp = "Current Portfolio" if ticker in HOLDINGS else ("Active Watchlist" if ticker in WATCHLIST else "Discovery Opportunity")

                if has_contract and pct_val >= 0:
                    signals.append({
                        "ticker": ticker,
                        "group": grp,
                        "type": "DoD Procurement / Defense Contract Award",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_val:+.2f}%",
                        "summary": "Confirmed federal procurement award or contract modification identified. Volume running " + f"{vol_ratio:.1f}x average.",
                        "url": get_fin_url(ticker)
                    })
                elif vol_ratio >= 1.75 and pct_val >= 2.0:
                    signals.append({
                        "ticker": ticker,
                        "group": grp,
                        "type": "Institutional Volume Breakout",
                        "vol_ratio": f"{vol_ratio:.1f}x",
                        "pct": f"{pct_val:+.2f}%",
                        "summary": "Aggressive institutional accumulation detected (" + f"{vol_ratio:.1f}x normal volume) alongside strong price expansion.",
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
    b64_script = (
        "PHNjcmlwdD4KYXN5bmMgZnVuY3Rpb24gdXBkYXRlV2VhdGhlcigpIHsKICBjb25zdCBjID0g"
        "ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3dlYXRoZXItZm9yZWNhc3QtbGlzdCcpOwogIGlm"
        "ICghYykgcmV0dXJuOwogIHRyeSB7CiAgICBjb25zdCByID0gYXdhaXQgZmV0Y2goJ2h0dHBz"
        "Oi8vYXBpLm9wZW4tbWV0ZW8uY29tL3YxL2ZvcmVjYXN0P2xhdGl0dWRlPTMyLjc0NDgmbG9u"
        "Z2l0dWRlPS0xMTYuOTk4OSZkYWlseT13ZWF0aGVyY29kZSx0ZW1wZXJhdHVyZV8ybV9tYXgs"
        "dGVtcGVyYXR1cmVfMm1fbWluJnRlbXBlcmF0dXJlX3VuaXQ9ZmFocmVuaGVpdCZ0aW1lem9u"
        "ZT1BbWVyaWNhJTJGTG9zX0FuZ2VsZXMmZm9yZWNhc3RfZGF5cz0xNCcpOwogICAgY29uc3Qg"
        "ZCA9IGF3YWl0IHIuanNvbigpOwogICAgbGV0IGggPSAnJzsKICAgIGNvbnN0IGNvZGVzID0g"
        "ezA6J+KYgCBDbGVhcicsIDE6J/CfjKQgQ2xlYXInLCAyOifwn4ylIFB0IENsb3VkeScsIDM6"
        "J+KYge+4jyBPdmVyY2FzdCcsIDQ1Oifwn4yrIEZvZycsIDUxOifwn4ymIERyaXp6bGUnLCA2"
        "MTon8J+MpyBSYWluJywgODA6J/CfjKYgU2hvd2VycycsIDk1Oifim8ggU3Rvcm0nfTsKICAg"
        "IGZvciAobGV0IGkgPSAwOyBpIDwgZC5kYWlseS50aW1lLmxlbmd0aDsgaSsrKSB7CiAgICAg"
        "IGNvbnN0IGR0ID0gbmV3IERhdGUoZC5kYWlseS50aW1lW2ldICsgJ1QxMjowMDowMCcpOwog"
        "ICAgICBjb25zdCBkYXkgPSBpID09PSAwID8gJ1RvZGF5JyA6IGR0LnRvTG9jYWxlRGF0ZVN0"
        "cmluZygndW4tVVMnLCB7d2Vla2RheTonc2hvcnQnfSk7CiAgICAgIGNvbnN0IG1kID0gKGR0"
        "LmdldE1vbnRoKCkgKyAxKSArICcvJyArIGR0LmdldERhdGUoKTsKICAgICAgY29uc3QgbWF4"
        "ID0gTWF0aC5yb3VuZChkLmRhaWx5LnRlbXBlcmF0dXJlXzJtX21heFtpXSk7CiAgICAgIGNv"
        "bnN0IG1pbiA9IE1hdGgucm91bmQoZC5kYWlseS50ZW1wZXJhdHVyZV8ybV9taW5baV0pOwog"
        "ICAgICBjb25zdCBkZXNjID0gY29kZXNbZC5kYWlseS53ZWF0aGVyY29kZVtpaV0gfHwgJ/Cf"
        "jKQgRmFpcic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5"
        "LWNvbnRlbnQ6c3BhY2UtYmV0d2V