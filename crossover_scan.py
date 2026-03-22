import yfinance as yf
import pandas as pd
import os
import asyncio
from telegram import Bot

# --- CONFIG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Major & Minor Forex Pairs
FOREX_PAIRS = [
    'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
    'EURGBP=X', 'EURJPY=X', 'GBPJPY=X', 'EURCHF=X', 'AUDJPY=X'
]

async def run_crossover_scan():
    print("🚀 Running 200/50 Daily Crossover Scan...")
    # Download 1.5 years of daily data to ensure enough padding for 200 SMA
    data = yf.download(FOREX_PAIRS, interval='1d', period='1.5y', group_by='ticker', progress=False)
    
    signals = []

    for pair in FOREX_PAIRS:
        try:
            df = data[pair].dropna()
            if len(df) < 201: continue
            
            # 1. Calculate Moving Averages
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            pair_name = pair.replace('=X', '')

            # 2. Logic: Golden Cross (Buy)
            # 50 SMA crosses ABOVE 200 SMA
            if prev['SMA50'] <= prev['SMA200'] and curr['SMA50'] > curr['SMA200']:
                signals.append(f"✨ *GOLDEN CROSS (Bullish)*\nPair: {pair_name}\nVerdict: **LONG ENTRY**\nPrice: {curr['Close']:.4f}")

            # 3. Logic: Death Cross (Short)
            # 50 SMA crosses BELOW 200 SMA
            elif prev['SMA50'] >= prev['SMA200'] and curr['SMA50'] < curr['SMA200']:
                signals.append(f"💀 *DEATH CROSS (Bearish)*\nPair: {pair_name}\nVerdict: **SHORT ENTRY**\nPrice: {curr['Close']:.4f}")
                
            # 4. Logic: Trend Confirmation (Price vs SMA200)
            # Alert if price is pulling back to a rising 200 SMA (Support Check)
            elif curr['Close'] > curr['SMA200'] and prev['Close'] < curr['SMA200'] * 1.005:
                if curr['SMA200'] > df['SMA200'].iloc[-10]:
                    signals.append(f"🛡️ *SUPPORT TEST*\nPair: {pair_name}\nVerdict: **WATCH FOR REBOUND**\nDetails: Testing 200-Day SMA")

        except Exception as e:
            print(f"Error analyzing {pair}: {e}")
            continue

    # --- TELEGRAM DELIVERY ---
    if signals:
        bot = Bot(token=TOKEN)
        report = "📈 *200/50 DAILY CROSSOVER REPORT* 📉\n\n" + "\n\n".join(signals)
        await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
        print("Signals sent successfully.")
    else:
        print("No crossovers detected today.")

if __name__ == "__main__":
    asyncio.run(run_crossover_scan())
