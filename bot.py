import yfinance as yf
import pandas as pd
import os
import asyncio
from telegram import Bot
from tickers import FOREX, CRYPTO, INDIA, US_STOCKS

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

BENCHMARKS = {"FOREX": "DX-Y.NYB", "CRYPTO": "BTC-USD", "INDIA": "^NSEI", "US": "^GSPC"}

async def analyze_category(name, tickers, benchmark_ticker):
    data = yf.download(tickers + [benchmark_ticker], interval='1wk', period='2y', group_by='ticker', progress=False)
    
    category_signals = []
    bench_df = data[benchmark_ticker].dropna()

    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 35: continue
            
            # Weinstein Metrics
            df['SMA30'] = df['Close'].rolling(window=30).mean()
            curr, prev = df.iloc[-1], df.iloc[-2]
            sma_slope = (curr['SMA30'] - df['SMA30'].iloc[-5]) / 5
            
            # Mansfield RS Calculation
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(window=52).mean()
            mrs = ((df['Base_RS'].iloc[-1] / df['Avg_RS'].iloc[-1]) - 1) * 100
            
            vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]
            is_bullish = curr['Close'] > curr['Open']
            clean_name = ticker.replace('.NS', '').replace('=X', '')

            # --- STAGE 2 BREAKOUT (BUY) ---
            if prev['Close'] <= prev['SMA30'] and curr['Close'] > curr['SMA30'] and is_bullish:
                if sma_slope > -0.0005 and mrs > 0 and vol_ratio >= 1.5:
                    category_signals.append({
                        "type": "BUY",
                        "name": clean_name,
                        "mrs": mrs,
                        "text": f"🚀 *STAGE 2 (Advancing)*\nAsset: {clean_name}\nVerdict: **BUY**\nDetails: Vol {vol_ratio:.1f}x | RS {mrs:.1f}%"
                    })

            # --- STAGE 4 BREAKDOWN (SELL) ---
            elif prev['Close'] >= prev['SMA30'] and curr['Close'] < curr['SMA30']:
                verdict = "SELL/EXIT ONLY" if name == "INDIA" else "SELL / SHORT"
                category_signals.append({
                    "type": "SELL",
                    "name": clean_name,
                    "mrs": mrs,
                    "text": f"🛑 *STAGE 4 (Declining)*\nAsset: {clean_name}\nVerdict: **{verdict}**\nDetails: Trend Broken"
                })
        except: continue
    return category_signals

async def main():
    bot = Bot(token=TOKEN)
    categories = [("FOREX", FOREX, BENCHMARKS["FOREX"]), 
                  ("CRYPTO", CRYPTO, BENCHMARKS["CRYPTO"]), 
                  ("INDIA", INDIA, BENCHMARKS["INDIA"]), 
                  ("US STOCKS", US_STOCKS, BENCHMARKS["US"])]
    
    all_buys = []
    all_sells = []
    full_body = ""

    for name, tickers, bench in categories:
        sigs = await analyze_category(name, tickers, bench)
        if sigs:
            cat_buys = [s for s in sigs if s['type'] == "BUY"]
            cat_sells = [s for s in sigs if s['type'] == "SELL"]
            all_buys.extend(cat_buys)
            all_sells.extend(cat_sells)
            
            full_body += f"\n🏢 *{name} MARKET* 🤵‍♂️\n" + "\n\n".join([s['text'] for s in sigs]) + "\n"

    # --- TOP 5 LEADERS RANKING ---
    all_buys.sort(key=lambda x: x['mrs'], reverse=True)
    top_hits = all_buys[:5]
    
    leaderboard = "🏆 *TOP A+ LEADERS (Highest RS)*\n"
    if top_hits:
        for i, hit in enumerate(top_hits, 1):
            leaderboard += f"{i}. {hit['name']} (RS: {hit['mrs']:.1f}%)\n"
    else:
        leaderboard += "No new leaders this week.\n"

    # --- FINAL HEADER & SUMMARY ---
    header = f"🤵‍♂️ *STAN WEINSTEIN WEEKLY SCAN* 🤵‍♂️\n"
    header += f"━━━━━━━━━━━━━━━━━━━━\n"
    header += f"🚀 Total Buy: {len(all_buys)} | 🛑 Total Sell: {len(all_sells)}\n"
    header += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    await bot.send_message(chat_id=CHAT_ID, text=header + leaderboard + full_body, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(main())
