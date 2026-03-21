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
    signals = []
    bench_df = data[benchmark_ticker].dropna()

    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 35: continue
            
            # Weinstein Core
            df['SMA30'] = df['Close'].rolling(window=30).mean()
            curr, prev = df.iloc[-1], df.iloc[-2]
            sma_slope = (curr['SMA30'] - df['SMA30'].iloc[-5]) / 5
            
            # Mansfield RS
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(window=52).mean()
            mrs = ((df['Base_RS'].iloc[-1] / df['Avg_RS'].iloc[-1]) - 1) * 100
            
            # Volume & Bullishness
            vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]
            is_bullish = curr['Close'] > curr['Open']
            
            # Clean Name
            clean_name = ticker.replace('.NS', '').replace('=X', '')
            
            # --- STAGE CLASSIFICATION ---
            
            # STAGE 2 BREAKOUT (BUY)
            if prev['Close'] <= prev['SMA30'] and curr['Close'] > curr['SMA30'] and is_bullish:
                if sma_slope > -0.0005 and mrs > 0 and vol_ratio >= 1.5:
                    signals.append(f"🚀 *STAGE 2 (Advancing)*\nAsset: {clean_name}\nVerdict: **STRONG BUY**\nDetails: Vol {vol_ratio:.1f}x | RS Positive")

            # STAGE 4 BREAKDOWN (SELL/SHORT)
            elif prev['Close'] >= prev['SMA30'] and curr['Close'] < curr['SMA30'] and sma_slope < 0.0005:
                # SKIP SHORTS FOR INDIA
                if name == "INDIA": continue 
                
                signals.append(f"🛑 *STAGE 4 (Declining)*\nAsset: {clean_name}\nVerdict: **SELL / SHORT**\nDetails: Trend Broken")

        except: continue
    return signals

async def main():
    bot = Bot(token=TOKEN)
    categories = [("FOREX", FOREX, BENCHMARKS["FOREX"]), 
                  ("CRYPTO", CRYPTO, BENCHMARKS["CRYPTO"]), 
                  ("INDIA", INDIA, BENCHMARKS["INDIA"]), 
                  ("US STOCKS", US_STOCKS, BENCHMARKS["US"])]
    
    for name, tickers, bench in categories:
        sigs = await analyze_category(name, tickers, bench)
        if sigs:
            await bot.send_message(chat_id=CHAT_ID, text=f"🏢 *{name} MARKET UPDATE* 🤵‍♂️\n\n" + "\n\n".join(sigs), parse_mode='Markdown')
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
