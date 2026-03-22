import yfinance as yf
import pandas as pd
import os
import asyncio
import time
from telegram import Bot

# --- CONFIG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Major & Minor Forex Pairs
FOREX_PAIRS = [
    'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
    'EURGBP=X', 'EURJPY=X', 'GBPJPY=X', 'EURCHF=X', 'AUDJPY=X'
]

async def fetch_with_retry(tickers, retries=3, delay=5):
    """Downloads data with a retry loop to handle API flickers."""
    for i in range(retries):
        try:
            # Using 2y to ensure enough data for 200 SMA calculation
            data = yf.download(tickers, interval='1d', period='2y', group_by='ticker', progress=False)
            if not data.empty:
                return data
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(delay)
    return None

async def run_crossover_scan():
    print("🚀 Starting 200/50 Daily Crossover Scan...")
    
    data = await fetch_with_retry(FOREX_PAIRS)
    
    if data is None or data.empty:
        print("❌ Failed to download data after multiple attempts.")
        return

    signals = []

    for pair in FOREX_PAIRS:
        try:
            # Extract individual ticker data
            df = data[pair].dropna()
            
            # Ensure we have at least 200 days of data
            if len(df) < 205:
                print(f"⚠️ {pair}: Not enough data ({len(df)} days). Skipping.")
                continue
            
            # 1. Calculate Moving Averages (50 and 200 Day)
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            pair_label = pair.replace('=X', '')

            # 2. Logic: Golden Cross (Bullish)
            # 50 SMA crosses ABOVE 200 SMA
            if prev['SMA50'] <= prev['SMA200'] and curr['SMA50'] > curr['SMA200']:
                signals.append(
                    f"✨ *GOLDEN CROSS (Bullish)*\n"
                    f"Pair: {pair_label}\n"
                    f"Verdict: **LONG ENTRY**\n"
                    f"Price: {curr['Close']:.4f}"
                )

            # 3. Logic: Death Cross (Bearish)
            # 50 SMA crosses BELOW 200 SMA
            elif prev['SMA50'] >= prev['SMA200'] and curr['SMA50'] < curr['SMA200']:
                signals.append(
                    f"💀 *DEATH CROSS (Bearish)*\n"
                    f"Pair: {pair_label}\n"
                    f"Verdict: **SHORT ENTRY**\n"
                    f"Price: {curr['Close']:.4f}"
                )
                
            # 4. Logic: Support/Resistance Test (Bonus)
            # Price hitting the 200 SMA while the SMA is trending
            elif abs(curr['Close'] - curr['SMA200']) / curr['SMA200'] < 0.002: # Within 0.2%
                trend = "Rising" if curr['SMA200'] > df['SMA200'].iloc[-10] else "Falling"
                signals.append(
                    f"🛡️ *200-DAY SMA TEST*\n"
                    f"Pair: {pair_label}\n"
                    f"Status: Price testing {trend} 200 SMA\n"
                    f"Price: {curr['Close']:.4f}"
                )

        except Exception as e:
            print(f"Error analyzing {pair}: {e}")
            continue

    # --- TELEGRAM DELIVERY ---
    if signals:
        bot = Bot(token=TOKEN)
        report = "📈 *200/50 DAILY CROSSOVER REPORT* 📉\n\n" + "\n\n".join(signals)
        await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
        print("✅ Report sent to Telegram.")
    else:
        print("ℹ️ No new crossovers detected today.")

if __name__ == "__main__":
    asyncio.run(run_crossover_scan())
