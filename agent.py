def get_catalysts():
    signals = []
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
                
                # Active Market Timing Check:
                avg_v = float(h["Volume"].iloc[:-1].mean())
                tod_v = float(h["Volume"].iloc[-1])
                vr = (tod_v / avg_v) if avg_v > 0 else 1.0
                day_pct = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100.0
                
                # Dynamic Buy Alert Rules:
                # 1. Fundamental setup: Wall St Buy/Strong Buy + >= 20% upside + off highs
                # 2. Timing trigger: Institutional volume surge (vr >= 1.35x) OR solid up-day (day_pct >= +1.5%)
                has_fundamental_value = rec in ["buy", "strong_buy"] and upside >= 20.0 and pullback >= 5.0
                has_active_catalyst = (vr >= 1.35 and day_pct > 0) or day_pct >= 2.0
                
                if has_fundamental_value and has_active_catalyst:
                    if tkr in HOLDINGS:
                        grp = "Current Portfolio"
                    elif tkr in WATCHLIST:
                        grp = "Active Watchlist"
                    else:
                        grp = "Broad Market Opportunity"
                    
                    analysis_url = f"https://finance.yahoo.com/quote/{tkr}/analysis"
                    signals.append({
                        "ticker": tkr,
                        "group": grp,
                        "type": "Expert Buy Window",
                        "upside_num": upside,
                        "vol_ratio": f"+{upside:.0f}% Up",
                        "pct": f"${price:.2f}",
                        "consensus": rec.upper().replace('_', ' '),
                        "target_price": f"${target:.2f}",
                        "current_price": f"${price:.2f}",
                        "analysts": num_analysts,
                        "summary": f"{tkr} Consensus {rec.upper().replace('_', ' ')} at ${price:.2f} (Target ${target:.2f}, +{upside:.1f}% upside, {vr:.1f}x Vol)",
                        "url": analysis_url
                    })
        except Exception:
            pass
            
    signals.sort(key=lambda x: x["upside_num"], reverse=True)
    return signals[:2]