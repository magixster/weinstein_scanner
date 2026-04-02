import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime, time
import pytz
from indicators import get_squeeze_status

# ================== SETTINGS ==================
LOG_DIR = "squeeze/logs"
INITIAL_BALANCE = 100000
RISK_PER_TRADE = 0.005 
TP_ATR_MULT = 1.5
SL_ATR_MULT = 1.0
MAX_OPEN_PER_MARKET = 5 
# ==============================================

class MultiMarketTrader:
    def __init__(self, market_name):
        self.market_name = market_name
        self.log_path = f"{LOG_DIR}/{market_name.lower()}.json"
        os.makedirs(LOG_DIR, exist_ok=True)
        self.data = self.load_logs()
        self.balance = self.data.get("balance", INITIAL_BALANCE)
        self.active_positions = self.data.get("active_positions", {})
        self.history = self.data.get("history", [])

    def load_logs(self):
        if os.path.exists(self.log_path):
            with open(self.log_path, 'r') as f:
                return json.load(f)
        return {"balance": INITIAL_BALANCE, "active_positions": {}, "history": []}

    def save_logs(self):
        with open(self.log_path, 'w') as f:
            json.dump({"balance": self.balance, "active_positions": self.active_positions, "history": self.history}, f, indent=4)

    def is_market_open_for_entry(self):
        """Prevents entries in the last 30 mins of trade to avoid overnight risk."""
        now_utc = datetime.now(pytz.utc)
        if self.market_name == "INDIA":
            ist = now_utc.astimezone(pytz.timezone('Asia/Kolkata')).time()
            return time(9, 15) <= ist <= time(15, 0) # Close at 15:30, so stop at 15:00
        elif self.market_name == "US_STOCKS":
            est = now_utc.astimezone(pytz.timezone('US/Eastern')).time()
            return time(9, 30) <= est <= time(15, 30) # Close at 16:00
        return True # Forex is 24/5

    def calculate_atr(self, df, period=14):
        tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    async def run_market_session(self, tickers, bot, chat_id):
        if not tickers: return
        data = yf.download(tickers, period='2d', interval='1h', group_by='ticker', progress=False, threads=True)
        
        # 1. CHECK EXITS (Simulating OCO Orders: One-Cancels-the-Other)
        for ticker in list(self.active_positions.keys()):
            df = data[ticker].dropna()
            if df.empty: continue
            
            # We check High/Low of the last candle to see if SL/TP was triggered mid-hour
            last_h, last_l = df['High'].iloc[-1], df['Low'].iloc[-1]
            pos = self.active_positions[ticker]
            price = df['Close'].iloc[-1] # Current price for logging
            
            exit_type = None
            if pos['type'] == 'BUY':
                if last_l <= pos['sl']: exit_type = "SL"
                elif last_h >= pos['tp']: exit_type = "TP"
            else: # SELL
                if last_h >= pos['sl']: exit_type = "SL"
                elif last_l <= pos['tp']: exit_type = "TP"

            if exit_type:
                exit_price = pos['sl'] if exit_type == "SL" else pos['tp']
                pnl = (exit_price - pos['entry_price']) * pos['units'] if pos['type'] == 'BUY' else (pos['entry_price'] - exit_price) * pos['units']
                self.balance += pnl
                self.history.append({"ticker": ticker, "pnl": round(pnl, 2), "result": exit_type, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
                del self.active_positions[ticker]
                await bot.send_message(chat_id=chat_id, text=f"🏁 {self.market_name} {exit_type}: {ticker}\nPnL: ${pnl:,.2f}")

        # 2. CHECK ENTRIES
        if not self.is_market_open_for_entry() or len(self.active_positions) >= MAX_OPEN_PER_MARKET:
            return

        potential = []
        for ticker in tickers:
            if ticker in self.active_positions: continue
            status, mom = get_squeeze_status(data[ticker].dropna())
            if status == "RELEASED":
                potential.append({'ticker': ticker, 'mom': abs(mom), 'side': "BUY" if mom > 0 else "SELL", 'df': data[ticker]})

        potential.sort(key=lambda x: x['mom'], reverse=True)

        for entry in potential:
            if len(self.active_positions) >= MAX_OPEN_PER_MARKET: break
            df, ticker, side = entry['df'], entry['ticker'], entry['side']
            price, atr = float(df['Close'].iloc[-1]), self.calculate_atr(df)
            sl_dist = atr * SL_ATR_MULT
            units = (self.balance * RISK_PER_TRADE) / sl_dist if sl_dist > 0 else 0

            if units > 0:
                self.active_positions[ticker] = {
                    "type": side, "entry_price": price, "units": units,
                    "sl": price - sl_dist if side == "BUY" else price + sl_dist,
                    "tp": price + (atr * TP_ATR_MULT) if side == "BUY" else price - (atr * TP_ATR_MULT),
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                await bot.send_message(chat_id=chat_id, text=f"🚀 {self.market_name} ENTRY: {ticker}\nPrice: {price:.2f} | SL: {self.active_positions[ticker]['sl']:.2f}")
        
        self.save_logs()
