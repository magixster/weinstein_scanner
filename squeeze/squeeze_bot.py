import asyncio
import yfinance as yf
from telegram import Bot
import os
import sys
import importlib.util

# --- 1. FORCE-LOAD TICKERS.PY FROM ROOT ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
tickers_path = os.path.join(root_dir, "tickers.py")

try:
    spec = importlib.util.spec_from_file_location("tickers", tickers_path)
    tickers_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tickers_mod)
    
    # Merge and SANITIZE Tickers (Removes spaces and duplicates)
    RAW_LIST = (
        tickers_mod.FOREX + 
        tickers_mod.CRYPTO + 
        tickers_mod.INDIA + 
        tickers_mod.US_STOCKS
    )
    # yfinance fails on symbols with spaces like 'DATA PATTERNS.NS'
    ALL_TICKERS = [t.strip().replace(" ", "") for t in RAW_LIST if t]
    ALL_TICKERS = list(dict.fromkeys(ALL_TICKERS))
    
    print(f"✅ Loaded {len(ALL_TICKERS)} tickers. (Sanitized symbols with spaces)")
except Exception as e:
    print(f"❌ Error loading tickers.py: {e}")
    sys.exit(1)

from indicators import get_squeeze_status

# --- 2. CONFIG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def run_squeeze_monitor():
    if not TOKEN or not CHAT_ID:
        print("❌ Telegram credentials missing.")
        return

    bot = Bot(token=TOKEN)
    print(f"🔎 Scanning {len(ALL_TICKERS)} tickers for Squeeze Release...")
    
    # Download data
    try:
        # We use threads=True to speed up the 400+ ticker download
        data = yf.download(ALL_TICKERS, period='5d', interval='1h', group_by='ticker', progress=False, threads=True)
    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        return
    
    alerts = []
    for ticker in ALL_TICKERS:
        try:
            # Skip if ticker failed to download
            if ticker not in data or data[ticker].empty or data[ticker].isna().all().all():
                continue
                
            df = data[ticker].dropna()
            if len(df) < 35: continue 
            
            status, val = get_squeeze_status(df)
            
            if status == "RELEASED":
                # Determine Color/Direction
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
                    f"🔹 *Price:* {df['Close'].iloc[-1]:.2f}\n"
                    f"🔹 *Symbol:* `{ticker}`"
                )
        except:
            continue

    if alerts:
        # Batching to stay under Telegram limits
        for i in range(0, len(alerts), 10):
            batch = alerts[i:i+10]
            msg = "📉 *LAZYBEAR SQUEEZE ALERTS* 📈\n\n" + "\n\n".join(batch)
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
            await asyncio.sleep(1)
        print(f"✅ {len(alerts)} alerts sent.")
    else:
        print("ℹ️ No new squeeze releases detected.")

if __name__ == "__main__":
    asyncio.run(run_squeeze_monitor())
