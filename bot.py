import yfinance as yf
import pandas as pd
import os
import asyncio
from telegram import Bot
from tickers import FOREX, CRYPTO, INDIA, US_STOCKS  # Importing from your new file

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

BENCHMARKS = {
    "FOREX": "DX-Y.NYB",
    "CRYPTO": "BTC-USD",
    "INDIA": "^NSEI",
    "US": "^GSPC"
}

async def analyze_category(name, tickers, benchmark_ticker):
    print(f"--- Processing {name} ---")
    # Download everything in one batch for this category to save time/requests
    data = yf.download(tickers + [benchmark_ticker], interval='1wk', period='2y', group_by='ticker', progress=False)
    
    signals = []
    bench_df = data[benchmark_ticker].dropna()

    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 35: continue
            
            df['SMA30'] = df['Close'].rolling(window=30).mean()
            curr, prev = df.iloc[-1], df.iloc[-2]
            sma_slope = (curr['SMA30'] - df['SMA30'].iloc[-5]) / 5
            
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(window=52).mean()
            df['MRS'] = ((df['Base_RS'] / df['Avg_RS']) - 1) * 100
            
            # Stan Weinstein Strict Rules
            is_bullish = curr['Close'] > curr['Open']
            vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]
            
            # Stage 2 Breakout
            if prev['Close'] <= prev['SMA30'] and curr['Close'] > curr['SMA30'] and is_bullish:
                if sma_slope > -0.0005 and df['MRS'].iloc[-1] > 0 and vol_ratio >= 1.5:
                    clean_name = ticker.replace('.NS', '').replace('=X', '')
                    signals.append(f"🚀 *{clean_name}*: P:{curr['Close']:.2f} | V:{vol_ratio:.1f}x | RS:+")

            # Stage 4 Breakdown
            elif prev['Close'] >= prev['SMA30'] and curr['Close'] < curr['SMA30']:
                clean_name = ticker.replace('.NS', '').replace('=X', '')
                signals.append(f"🛑 *{clean_name}*: P:{curr['Close']:.2f} | CRASH")
                
        except: continue
        
    return signals

async def main():
    bot = Bot(token=TOKEN)
    categories = [
        ("FOREX", FOREX, BENCHMARKS["FOREX"]),
        ("CRYPTO", CRYPTO, BENCHMARKS["CRYPTO"]),
        ("INDIA", INDIA, BENCHMARKS["INDIA"]),
        ("US STOCKS", US_STOCKS, BENCHMARKS["US"])
    ]
    
    for name, tickers, bench in categories:
        sigs = await analyze_category(name, tickers, bench)
        if sigs:
            report = f"🏢 *{name} STAGE UPDATE*\n\n" + "\n".join(sigs)
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
            await asyncio.sleep(2) # Prevent Telegram rate limiting

if __name__ == "__main__":
    asyncio.run(main())
