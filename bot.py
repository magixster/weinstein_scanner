import yfinance as yf
import pandas as pd
import numpy as np
import os
import asyncio
import csv
from datetime import datetime
from telegram import Bot
from tickers import FOREX, CRYPTO, INDIA, US_STOCKS

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

ACCOUNT_SIZE = 10000
RISK_PER_TRADE = 0.01
LOG_FILE = "trade_log.csv"

BENCHMARKS = {
    "FOREX": "DX-Y.NYB",
    "CRYPTO": "BTC-USD",
    "INDIA": "^NSEI",
    "US": "^GSPC"
}

# -----------------------------
# HELPERS
# -----------------------------

def trend_structure_up(df):
    return df['Close'].iloc[-1] > df['Close'].iloc[-5] > df['Close'].iloc[-10]

def trend_structure_down(df):
    return df['Close'].iloc[-1] < df['Close'].iloc[-5] < df['Close'].iloc[-10]

def breakout(df, lookback=20):
    recent_high = df['High'].rolling(lookback).max().iloc[-2]
    return df['Close'].iloc[-1] > recent_high

def breakdown(df, lookback=20):
    recent_low = df['Low'].rolling(lookback).min().iloc[-2]
    return df['Close'].iloc[-1] < recent_low

def get_position_size(entry, sl):
    risk_amount = ACCOUNT_SIZE * RISK_PER_TRADE
    risk_per_unit = abs(entry - sl)
    if risk_per_unit == 0:
        return 0
    return int(risk_amount / risk_per_unit)

def log_trade(symbol, entry, sl, qty, category):
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "Date", "Symbol", "Category",
                "Entry", "SL", "Qty",
                "Exit", "Result_R", "Status"
            ])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d"),
            symbol,
            category,
            entry,
            sl,
            qty,
            "", "", "OPEN"
        ])

# -----------------------------
# MAIN ANALYZER
# -----------------------------

async def analyze_category(name, tickers, benchmark_ticker):
    data = yf.download(
        tickers + [benchmark_ticker],
        interval='1wk',
        period='2y',
        group_by='ticker',
        progress=False
    )

    signals = []
    bench_df = data[benchmark_ticker].dropna()

    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 60:
                continue

            df['SMA30'] = df['Close'].rolling(30).mean()
            curr = df.iloc[-1]

            sma_slope = df['SMA30'].iloc[-1] - df['SMA30'].iloc[-5]

            # RS
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(52).mean()
            mrs = ((df['Base_RS'].iloc[-1] / df['Avg_RS'].iloc[-1]) - 1) * 100

            # Volume
            vol_ratio = 1 if name == "FOREX" else curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]

            clean_name = ticker.replace('.NS', '').replace('=X', '')

            # Distance from 30W SMA
            distance = ((curr['Close'] - curr['SMA30']) / curr['SMA30']) * 100

            # -----------------------------
            # STAGE 2 (YOUR ORIGINAL LOGIC)
            # -----------------------------
            if (
                curr['Close'] > curr['SMA30'] and
                sma_slope > 0 and
                trend_structure_up(df) and
                breakout(df) and
                mrs > 0 and
                vol_ratio >= 1.5
            ):

                # Entry classification
                if distance <= 5:
                    entry_type = "EARLY"
                elif distance <= 10:
                    entry_type = "NORMAL"
                elif distance <= 20:
                    entry_type = "EXTENDED"
                else:
                    entry_type = "OVEREXTENDED (AVOID)"

                # Skip bad trades
                if distance > 20:
                    continue

                entry = curr['Close']
                sl = df['Low'].rolling(10).min().iloc[-1]
                qty = get_position_size(entry, sl)

                log_trade(clean_name, entry, sl, qty, name)

                signals.append({
                    "type": "BUY",
                    "name": clean_name,
                    "mrs": mrs,
                    "text": (
                        f"🚀 *STAGE 2*\n"
                        f"{clean_name}\n"
                        f"Entry: {entry:.2f} | SL: {sl:.2f}\n"
                        f"Qty: {qty}\n"
                        f"Type: {entry_type}\n"
                        f"Dist: {distance:.1f}%\n"
                        f"RS: {mrs:.1f}% | Vol: {vol_ratio:.1f}x"
                    )
                })

            # -----------------------------
            # STAGE 4 (UNCHANGED)
            # -----------------------------
            elif (
                curr['Close'] < curr['SMA30'] and
                sma_slope < 0 and
                trend_structure_down(df) and
                breakdown(df)
            ):
                verdict = "SELL/EXIT ONLY" if name == "INDIA" else "SELL / SHORT"

                signals.append({
                    "type": "SELL",
                    "name": clean_name,
                    "mrs": mrs,
                    "text": (
                        f"🛑 *STAGE 4*\n"
                        f"{clean_name}\n"
                        f"{verdict}\n"
                        f"Trend Weak"
                    )
                })

        except:
            continue

    return signals
