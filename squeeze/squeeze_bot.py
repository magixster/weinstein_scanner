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
    
    # Merge all lists into one master list for the scan
    ALL_TICKERS = (
        tickers_mod.FOREX + 
        tickers_mod.CRYPTO + 
        tickers_mod.INDIA + 
        tickers_mod.US_STOCKS
    )
    # Remove duplicates just in case
    ALL_TICKERS = list(dict.fromkeys(ALL_TICKERS))
    
    print(f"✅ Successfully loaded {len(ALL_TICKERS)} total tickers from tickers.py")
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
    
    # Download data in one go (yfinance is efficient with lists)
    # We use 1h interval. Note: Indian stocks only update during IST market hours.
    try:
        data = yf.download(ALL_TICKERS, period='5d', interval='1h', group_by='ticker', progress=False)
    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        return
    
    alerts = []
    
    for ticker in ALL_TICKERS:
        try:
            # Handle cases where yfinance might return an empty DF for a specific ticker
            if ticker not in data or data[ticker].empty:
                continue
                
            df = data[ticker].dropna()
            if len(df) < 22: continue # Need enough for 20 SMA + 2 prev bars
            
            status, momentum = get_squeeze_status(df)
            
            if status == "RELEASED":
                bias = "🟢 BULLISH" if momentum > 0 else "🔴 BEARISH"
                # Clean up name (remove .NS or =X for the alert)
                clean_name = ticker.replace('=X', '').replace('.NS', '')
                
                alerts.append(
                    f"🚀 *SQZ RELEASE:* `{clean_name}`\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔹 *Momentum:* {bias}\n"
                    f"🔹 *Price:* {df['Close'].iloc[-1]:.2f}\n"
                    f"🔹 *Symbol:* `{ticker}`"
                )
        except Exception as e:
            # Skip tickers with errors (e.g. delisted or no 1h data)
            continue

    # --- 3. SEND ALERTS (Batching messages to avoid Telegram limits) ---
    if alerts:
        # Telegram has a 4096 character limit per message
        # We send in batches of 10 alerts per message
        for i in range(0, len(alerts), 10):
            batch = alerts[i:i+10]
            final_msg = "📉 *SQUEEZE MOMENTUM ALERTS* 📈\n\n" + "\n\n".join(batch)
            await bot.send_message(chat_id=CHAT_ID, text=final_msg, parse_mode='Markdown')
            await asyncio.sleep(1) # Small sleep to avoid Telegram flood limits
        print(f"✅ Sent {len(alerts)} alerts.")
    else:
        print("ℹ️ No new squeeze releases detected.")

if __name__ == "__main__":
    asyncio.run(run_squeeze_monitor())
