import yfinance as yf
import pandas as pd
import numpy as np
import os
import asyncio
from telegram import Bot
from tickers import FOREX, CRYPTO, INDIA, US_STOCKS

# -----------------------------
# CONFIG
# -----------------------------
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

ACCOUNT_SIZE = 10000        # change this
RISK_PER_TRADE = 0.01       # 1% risk

BENCHMARKS = {
    "FOREX": "DX-Y.NYB",
    "CRYPTO": "BTC-USD",
    "INDIA": "^NSEI",
    "US": "^GSPC"
}

# -----------------------------
# HELPERS
# -----------------------------

def trend_up(df):
    return df['Close'].iloc[-1] > df['Close'].iloc[-5] > df['Close'].iloc[-10]

def breakout(df, lookback=20):
    return df['Close'].iloc[-1] > df['High'].rolling(lookback).max().iloc[-2]

def get_position_size(entry, sl):
    risk_amount = ACCOUNT_SIZE * RISK_PER_TRADE
    risk_per_unit = abs(entry - sl)
    if risk_per_unit == 0:
        return 0
    qty = risk_amount / risk_per_unit
    return int(qty)

# -----------------------------
# ANALYSIS
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

            # Slope
            sma_slope = df['SMA30'].iloc[-1] - df['SMA30'].iloc[-5]

            # Mansfield RS
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(52).mean()
            mrs = ((df['Base_RS'].iloc[-1] / df['Avg_RS'].iloc[-1]) - 1) * 100

            # Volume
            if name == "FOREX":
                vol_ratio = 1
            else:
                vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]

            clean_name = ticker.replace('.NS', '').replace('=X', '')

            # -----------------------------
            # STAGE 2 CONDITIONS
            # -----------------------------
            if (
                curr['Close'] > curr['SMA30'] and
                sma_slope > 0 and
                trend_up(df) and
                breakout(df) and
                mrs > 0 and
                vol_ratio >= 1.5
            ):

                # -----------------------------
                # DISTANCE FILTER
                # -----------------------------
                distance = ((curr['Close'] - curr['SMA30']) / curr['SMA30']) * 100

                if distance > 15:
                    continue  # skip bad trades

                # -----------------------------
                # ENTRY TYPE
                # -----------------------------
                if distance <= 5:
                    entry_type = "EARLY BREAKOUT"
                elif distance <= 10:
                    entry_type = "NORMAL BREAKOUT"
                else:
                    entry_type = "EXTENDED"

                # -----------------------------
                # STOP LOSS (SWING LOW)
                # -----------------------------
                swing_low = df['Low'].rolling(10).min().iloc[-1]
                entry_price = curr['Close']
                sl_price = swing_low

                # Risk %
                risk_pct = ((entry_price - sl_price) / entry_price) * 100

                # -----------------------------
                # POSITION SIZE
                # -----------------------------
                qty = get_position_size(entry_price, sl_price)

                # R-Multiple levels
                one_r = entry_price - sl_price
                target_1R = entry_price + one_r
                target_2R = entry_price + (2 * one_r)

                signals.append({
                    "type": "BUY",
                    "name": clean_name,
                    "mrs": mrs,
                    "text": (
                        f"🚀 *STAGE 2 (Advancing)*\n"
                        f"Asset: {clean_name}\n"
                        f"Entry: {entry_price:.2f}\n"
                        f"SL: {sl_price:.2f}\n"
                        f"Position Size: {qty} units\n"
                        f"Risk: {risk_pct:.1f}%\n"
                        f"1R: {target_1R:.2f} | 2R: {target_2R:.2f}\n"
                        f"Type: {entry_type}\n"
                        f"Dist from 30W: {distance:.1f}%\n"
                        f"RS: {mrs:.1f}% | Vol: {vol_ratio:.1f}x"
                    )
                })

        except Exception as e:
            continue

    return signals


# -----------------------------
# MAIN
# -----------------------------

async def main():
    bot = Bot(token=TOKEN)

    categories = [
        ("FOREX", FOREX, BENCHMARKS["FOREX"]),
        ("CRYPTO", CRYPTO, BENCHMARKS["CRYPTO"]),
        ("INDIA", INDIA, BENCHMARKS["INDIA"]),
        ("US STOCKS", US_STOCKS, BENCHMARKS["US"])
    ]

    all_buys = []
    full_body = ""

    for name, tickers, bench in categories:
        sigs = await analyze_category(name, tickers, bench)

        if sigs:
            all_buys.extend(sigs)
            full_body += (
                f"\n🏢 *{name} MARKET*\n"
                + "\n\n".join([s['text'] for s in sigs])
                + "\n"
            )

    # -----------------------------
    # LEADERBOARD
    # -----------------------------
    all_buys.sort(key=lambda x: x['mrs'], reverse=True)
    top_hits = all_buys[:5]

    leaderboard = "🏆 *TOP LEADERS (RS)*\n"
    if top_hits:
        for i, hit in enumerate(top_hits, 1):
            leaderboard += f"{i}. {hit['name']} ({hit['mrs']:.1f}%)\n"
    else:
        leaderboard += "No strong setups.\n"

    # -----------------------------
    # HEADER
    # -----------------------------
    header = (
        "🤵‍♂️ *WEINSTEIN PRO TRADING SCAN* 🤵‍♂️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Total Trades: {len(all_buys)}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    await bot.send_message(
        chat_id=CHAT_ID,
        text=header + leaderboard + full_body,
        parse_mode='Markdown'
    )


if __name__ == "__main__":
    asyncio.run(main())
