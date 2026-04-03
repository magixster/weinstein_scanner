import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime
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
        self.ist = pytz.timezone('Asia/Kolkata')

    def get_ist_now(self):
        """Returns current time in IST string format."""
        return datetime.now(pytz.utc).astimezone(self.ist).strftime("%Y-%m-%d %H:%M")

    def load_logs(self):
        if os.path.exists(self.log_path):
            with open(self.log_path, 'r') as f:
                return json.load(f)
        return {"balance": INITIAL_BALANCE, "active_positions": {}, "history": []}

    def save_logs(self):
        with open(self.log_path, 'w') as f:
            json.dump({
                "balance": self.balance, 
                "active_positions": self.active_positions, 
                "history": self.history
            }, f, indent=4)

    def calculate_atr(self, df, period=14):
        tr = pd.concat([
            df['High']-df['Low'], 
            abs(df['High']-df['Close'].shift()), 
            abs(df['Low']-df['Close'].shift())
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    async def run_market_session(self, tickers, bot, chat_id):
        if not tickers: return
        
        # Sanitize tickers (Remove spaces and empty strings)
        clean_tickers = [t.strip().replace(" ", "") for t in tickers if t]
        
        # Fetch data with enough history for ATR and Squeeze
        data = yf.download(clean_tickers, period='5d', interval='1h', group_by='ticker', progress=False, threads=True)
        
        # 1. CHECK EXITS
        for ticker in list(self.active_positions.keys()):
            try:
                df = data[ticker].dropna()
                if df.empty: continue
                
                last_h, last_l = df['High'].iloc[-1], df['Low'].iloc[-1]
                pos = self.active_positions[ticker]
                exit_type = None
                
                if pos['type'] == 'BUY':
                    if last_l <= pos['sl']: exit_type = "SL"
                    elif last_h >= pos['tp']: exit_type = "TP"
                else: # SELL Side
                    if last_h >= pos['sl']: exit_type = "SL"
                    elif last_l <= pos['tp']: exit_type = "TP"

                if exit_type:
                    exit_price = pos['sl'] if exit_type == "SL" else pos['tp']
                    pnl = (exit_price - pos['entry_price']) * pos['units'] if pos['type'] == 'BUY' else (pos['entry_price'] - exit_price) * pos['units']
                    
                    self.balance += pnl
                    self.history.append({
                        "ticker": ticker,
                        "side": pos['type'],
                        "entry_time": pos['entry_time'],
                        "exit_time": self.get_ist_now(),
                        "entry_price": round(pos['entry_price'], 4),
                        "exit_price": round(exit_price, 4),
                        "result": exit_type,
                        "pnl": round(pnl, 2)
                    })
                    del self.active_positions[ticker]
                    await bot.send_message(chat_id=chat_id, text=f"🏁 {self.market_name} {exit_type}: {ticker} ({pos['type']})\nPnL: ${pnl:,.2f} | Time: {self.get_ist_now()}")
            except: continue

        # 2. CHECK ENTRIES
        potential = []
        for ticker in clean_tickers:
            if ticker in self.active_positions: continue
            try:
                df = data[ticker].dropna()
                if len(df) < 35: continue
                status, mom = get_squeeze_status(df)
                if status == "RELEASED":
                    potential.append({'ticker': ticker, 'mom': abs(mom), 'side': "BUY" if mom > 0 else "SELL", 'df': df})
            except: continue

        potential.sort(key=lambda x: x['mom'], reverse=True)

        for entry in potential:
            if len(self.active_positions) >= MAX_OPEN_PER_MARKET: break
            
            ticker, side, df = entry['ticker'], entry['side'], entry['df']
            price = float(df['Close'].iloc[-1])
            atr = self.calculate_atr(df)
            sl_dist = atr * SL_ATR_MULT
            units = (self.balance * RISK_PER_TRADE) / sl_dist if sl_dist > 0 else 0

            if units > 0:
                self.active_positions[ticker] = {
                    "type": side,
                    "entry_price": price,
                    "units": units,
                    "sl": price - sl_dist if side == "BUY" else price + sl_dist,
                    "tp": price + (atr * TP_ATR_MULT) if side == "BUY" else price - (atr * TP_ATR_MULT),
                    "entry_time": self.get_ist_now()
                }
                msg = f"🚀 {self.market_name} {side} ENTRY: {ticker}\nPrice: {price:.2f} | Time (IST): {self.get_ist_now()}"
                await bot.send_message(chat_id=chat_id, text=msg)
        
        self.save_logs()

    def get_report(self):
        if not self.history: 
            return f"📊 **{self.market_name}**: No trades in history."
        
        df = pd.DataFrame(self.history)
        
        # 1. Overall Stats
        total_trades = len(df)
        wins = df[df['result'] == "TP"]
        overall_win_rate = (len(wins) / total_trades) * 100
        total_pnl = df['pnl'].sum()
        
        # 2. Pair-wise Performance
        # Grouping by ticker to find your "Star" performers
        pair_stats = []
        for ticker, group in df.groupby('ticker'):
            p_wins = len(group[group['result'] == "TP"])
            p_total = len(group)
            p_wr = (p_wins / p_total) * 100
            p_pnl = group['pnl'].sum()
            pair_stats.append({
                'ticker': ticker, 
                'wr': p_wr, 
                'pnl': p_pnl, 
                'trades': p_total
            })
        
        # Sort by PnL to show best on top
        pair_stats.sort(key=lambda x: x['pnl'], reverse=True)
        
        # 3. Build the Message
        report = (
            f"🏆 **{self.market_name} OVERALL SUMMARY**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Balance: ${self.balance:,.2f}\n"
            f"📈 Win Rate: {overall_win_rate:.1f}%\n"
            f"💵 Total P&L: ${total_pnl:,.2f}\n"
            f"🔄 Total Trades: {total_trades}\n\n"
            f"🔍 **PAIR-WISE BREAKDOWN**\n"
        )
        
        for p in pair_stats:
            icon = "✅" if p['pnl'] > 0 else "❌"
            report += (
                f"{icon} `{p['ticker']}`: ${p['pnl']:,.2f} | "
                f"WR: {p['wr']:.0f}% ({p['trades']}T)\n"
            )
            
        return report
