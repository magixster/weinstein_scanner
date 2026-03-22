import asyncio
import yfinance as yf
from telegram import Bot
import os
import sys
import importlib.util

# Load tickers from root
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
tickers_path = os.path.join(root_dir, "tickers.py")

spec = importlib.util.spec_from_file_location("tickers", tickers_path)
tickers_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tickers_mod)

# Combine your specific lists
ALL_TICKERS = list(dict.fromkeys(tickers_mod.FOREX + tickers_mod.CRYPTO + tickers_mod.INDIA + tickers_mod.US_STOCKS))

from indicators import get_squeeze_status

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def run_squeeze_monitor():
    bot = Bot(token=TOKEN)
    print(f"🔎 Scanning {len(ALL_TICKERS)} tickers...")
    
    # Download 1h data
    data = yf.download(ALL_TICKERS, period='5d', interval='1h', group_by='ticker', progress=False)
    
    alerts = []
    for ticker in ALL_TICKERS:
        try:
            df = data[ticker].dropna()
            if len(df) < 40: continue
            
            status, val = get_squeeze_status(df)
            
            if status == "RELEASED":
                # Get direction and color strength (like Lime vs Green)
                prev_val = df['val'].iloc[-2]
                curr_val = df['val'].iloc[-1]
                
                if curr_val > 0:
                    bias = "🟢 BULLISH (Lime)" if curr_val > prev_val else "💹 BULLISH (Green)"
                else:
                    bias = "🔴 BEARISH (Red)" if curr_val < prev_val else "🔻 BEARISH (Maroon)"
                
                clean_name = ticker.replace('=X', '').replace('.NS', '')
                alerts.append(
                    f"🚀 *SQZ RELEASED: {clean_name}*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔹 *Status:* Black ➡️ Gray Cross\n"
                    f"🔹 *Momentum:* {bias}\n"
                    f"🔹 *Price:* {df['Close'].iloc[-1]:.2f}"
                )
        except:
            continue

    if alerts:
        for i in range(0, len(alerts), 10):
            msg = "📉 *LAZYBEAR SQUEEZE ALERTS* 📈\n\n" + "\n\n".join(alerts[i:i+10])
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_squeeze_monitor())
