import asyncio
import yfinance as yf
from telegram import Bot
import os
import sys
import importlib.util
from datetime import datetime

# --- 1. DYNAMIC PATHING ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from paper_trader import MultiMarketTrader
from indicators import get_squeeze_status

# --- 2. LOAD TICKERS.PY FROM ROOT ---
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
tickers_path = os.path.join(root_dir, "tickers.py")

try:
    spec = importlib.util.spec_from_file_location("tickers", tickers_path)
    tickers_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tickers_mod)
    print("✅ Tickers loaded.")
except Exception as e:
    print(f"❌ Error loading tickers.py: {e}")
    sys.exit(1)

# --- 3. CONFIG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def run_squeeze_monitor():
    if not TOKEN or not CHAT_ID:
        print("❌ Credentials missing.")
        return

    bot = Bot(token=TOKEN)
    print(f"--- Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    # Initialize Market Traders
    markets = {
        "INDIA": (tickers_mod.INDIA, MultiMarketTrader("INDIA")),
        "US_STOCKS": (tickers_mod.US_STOCKS, MultiMarketTrader("US_STOCKS")),
        "FOREX": (tickers_mod.FOREX, MultiMarketTrader("FOREX")),
        "CRYPTO": (tickers_mod.CRYPTO, MultiMarketTrader("CRYPTO")) # Added Crypto
    }

    # Process each market individually for cleaner logs and specific trading hours
    for market_name, (symbols, trader) in markets.items():
        print(f"\n📡 Scanning {market_name}...")
        
        # This function now handles:
        # 1. Checking Exits (TP/SL)
        # 2. Sending General Alerts for ALL releases
        # 3. Taking new trades if < 5 slots are open
        await trader.run_market_session(symbols, bot, CHAT_ID)

    # --- 4. DAILY EOD REPORT TRIGGER ---
    # 16:00 UTC (~9:30 PM IST)
    if datetime.utcnow().hour == 16:
        report = "🏁 **DAILY PERFORMANCE SUMMARY**\n"
        report += "━━━━━━━━━━━━━━━━━━\n"
        for market_name, (_, trader) in markets.items():
            report += f"\n{trader.get_report()}"
        
        await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
        print("✅ EOD Report sent.")

if __name__ == "__main__":
    asyncio.run(run_squeeze_monitor())
