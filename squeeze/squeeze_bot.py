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
    FOREX_PAIRS = tickers_mod.FOREX_PAIRS
    print(f"✅ Successfully loaded {len(FOREX_PAIRS)} pairs from root/tickers.py")
except Exception as e:
    print(f"❌ Error loading tickers.py at {tickers_path}: {e}")
    sys.exit(1)

# Import local indicator file (must be in the same 'squeeze' folder)
from indicators import get_squeeze_status

# --- 2. CONFIG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def run_squeeze_monitor():
    if not TOKEN or not CHAT_ID:
        print("❌ Telegram credentials missing in Environment Variables.")
        return

    bot = Bot(token=TOKEN)
    print(f"🔎 Scanning for Squeeze Release (Black ➡️ Gray)...")
    
    # Download 1H data
    data = yf.download(FOREX_PAIRS, period='5d', interval='1h', group_by='ticker', progress=False)
    
    alerts = []
    for ticker in FOREX_PAIRS:
        try:
            df = data[ticker].dropna() if len(FOREX_PAIRS) > 1 else data.dropna()
            
            # Status from indicators.py
            status, momentum = get_squeeze_status(df)
            
            if status == "RELEASED":
                bias = "🟢 BULLISH" if momentum > 0 else "🔴 BEARISH"
                pair_name = ticker.replace('=X', '')
                
                alerts.append(
                    f"🚀 *SQUEEZE RELEASED: {pair_name}*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔸 *Transition:* Black ➡️ Gray Cross\n"
                    f"🔸 *Momentum:* {bias}\n"
                    f"🔸 *Price:* {df['Close'].iloc[-1]:.5f}"
                )
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    if alerts:
        final_msg = "📉 *SQZ_MOM HOURLY UPDATE* 📈\n\n" + "\n\n".join(alerts)
        await bot.send_message(chat_id=CHAT_ID, text=final_msg, parse_mode='Markdown')
        print(f"✅ Sent {len(alerts)} alerts to Telegram.")
    else:
        print("ℹ️ No new squeeze releases detected this hour.")

if __name__ == "__main__":
    asyncio.run(run_squeeze_monitor())
