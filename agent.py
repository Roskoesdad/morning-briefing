def get_catalysts():
    """
    Value-Investing Catalyst Engine (Buffett, Graham, Lynch):
    1. Holds quality businesses; ignores short-term dips and cyclical pullbacks.
    2. Flags a 'SELL' only under genuine fundamental impairment (consensus 'Underperform'/'Sell')
       or extreme valuation expansion (>20% above consensus intrinsic target).
    3. Recommends rotation ONLY when the alternative provides a superior margin of safety (+25%+ upside).
    """
    signals = []
    candidates_pool = []
    
    # 1. Evaluate Portfolio Holdings
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
                # Upside spread relative to consensus intrinsic value
                upside = ((target - price) / price) * 100.0
                analysis_url = f"https://finance.yahoo.com/quote/{tkr}/analysis"
                
                # Rule 1: Fundamental Impairment (Wall Street consensus downgraded to Sell)
                is_fundamental_downgrade = rec in ["sell", "strong_sell", "underperform"]
                
                # Rule 2: Extreme Valuation Cap (Trading > 20% premium above 12-month value target)
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

    # 2. Identify High Margin-of-Safety Opportunities for Capital Rotation
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
            price = fi.last_price if fi and fi.last_price else info.get("currentPrice")
            target = info.get("targetMeanPrice")
            rec = str(info.get("recommendationKey", "")).lower()
            if price and target and target > 0 and price > 0:
                upside = ((target - price) / price) * 100.0
                # Graham Margin of Safety threshold: Strong consensus + at least 25% upside
                if rec in ["buy", "strong_buy"] and upside >= 25.0:
                    candidates_pool.append({
                        "ticker": tkr,
                        "name": COMPANY_NAMES.get(tkr, tkr),
                        "rec": rec,
                        "upside": upside,
                        "price": price,
                        "target": target,
                        "url": f"https://finance.yahoo.com/quote/{tkr}/analysis"
                    })
        except Exception:
            pass

    candidates_pool.sort(key=lambda x: x["upside"], reverse=True)
    best_replacement = candidates_pool[0] if candidates_pool else None
    
    # 3. Pair Sell Signals with High-Conviction Rotation Assets
    for s in signals:
        if best_replacement:
            s["replacement_ticker"] = best_replacement["ticker"]
            s["replacement_name"] = best_replacement["name"]
            s["replacement_url"] = best_replacement["url"]
            s["replacement_text"] = f"{best_replacement['name']} (+{best_replacement['upside']:.0f}% upside)"
            buy_reasons_list = generate_reasons(best_replacement["ticker"], "BUY", best_replacement["price"], best_replacement["target"], best_replacement["upside"], best_replacement["rec"])
            s["replacement_reasons_encoded"] = urllib.parse.quote(json.dumps(buy_reasons_list))

    signals.sort(key=lambda x: x.get("upside_num", 0), reverse=True)
    return filter_active_catalysts(signals[:4])