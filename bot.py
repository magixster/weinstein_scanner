import yfinance as yf
import pandas as pd
import numpy as np
import os
import asyncio
from telegram import Bot
from tickers import FOREX, CRYPTO, INDIA, US_STOCKS

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

BENCHMARKS = {
    "FOREX": "DX-Y.NYB",
    "CRYPTO": "BTC-USD",
    "INDIA": "^NSEI",
    "US": "^GSPC"
}

# -----------------------------
# Helper Functions
# -----------------------------

def trend_structure_up(df):
    return (
        df['Close'].iloc[-1] > df['Close'].iloc[-5] > df['Close'].iloc[-10]
    )

def trend_structure_down(df):
    return (
        df['Close'].iloc[-1] < df['Close'].iloc[-5] < df['Close'].iloc[-10]
    )

def breakout(df, lookback=20):
    recent_high = df['High'].rolling(lookback).max().iloc[-2]
    return df['Close'].iloc[-1] > recent_high

def breakdown(df, lookback=20):
    recent_low = df['Low'].rolling(lookback).min().iloc[-2]
    return df['Close'].iloc[-1] < recent_low

# -----------------------------
# Main Analyzer
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

            # -----------------------------
            # Indicators
            # -----------------------------
            df['SMA30'] = df['Close'].rolling(30).mean()
            curr = df.iloc[-1]

            # Slope (stronger)
            sma_slope = df['SMA30'].iloc[-1] - df['SMA30'].iloc[-5]

            # Mansfield RS
            df['Base_RS'] = df['Close'] / bench_df['Close']
            df['Avg_RS'] = df['Base_RS'].rolling(52).mean()
            mrs = ((df['Base_RS'].iloc[-1] / df['Avg_RS'].iloc[-1]) - 1) * 100

            # Volume (skip for forex)
            if name == "FOREX":
                vol_ratio = 1
            else:
                vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]

            clean_name = ticker.replace('.NS', '').replace('=X', '')

            # -----------------------------
            # STAGE 2 (ADVANCING)
            # -----------------------------
            if (
                curr['Close'] > curr['SMA30'] and
                sma_slope > 0 and
                trend_structure_up(df) and
                breakout(df) and
                mrs > 0 and
                vol_ratio >= 1.5
            ):
                signals.append({
                    "type": "BUY",
                    "name": clean_name,
                    "mrs": mrs,
                    "text": (
                        f"🚀 *STAGE 2 (Advancing)*\n"
                        f"Asset: {clean_name}\n"
                        f"Verdict: **BUY**\n"
                        f"Details: Breakout | Vol {vol_ratio:.1f}x | RS {mrs:.1f}%"
                    )
                })

            # -----------------------------
            # STAGE 4 (DECLINING)
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
                        f"🛑 *STAGE 4 (Declining)*\n"
                        f"Asset: {clean_name}\n"
                        f"Verdict: **{verdict}**\n"
                        f"Details: Breakdown | Weak Trend"
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
    all_sells = []
    full_body = ""

    for name, tickers, bench in categories:
        sigs = await analyze_category(name, tickers, bench)

        if sigs:
            cat_buys = [s for s in sigs if s['type'] == "BUY"]
            cat_sells = [s for s in sigs if s['type'] == "SELL"]

            all_buys.extend(cat_buys)
            all_sells.extend(cat_sells)

            full_body += (
                f"\n🏢 *{name} MARKET* 🤵‍♂️\n"
                + "\n\n".join([s['text'] for s in sigs])
                + "\n"
            )

    # -----------------------------
    # LEADERBOARD (STRONGEST RS)
    # -----------------------------
    all_buys.sort(key=lambda x: x['mrs'], reverse=True)
    top_hits = all_buys[:5]

    leaderboard = "🏆 *TOP A+ LEADERS (RS Strength)*\n"
    if top_hits:
        for i, hit in enumerate(top_hits, 1):
            leaderboard += f"{i}. {hit['name']} (RS: {hit['mrs']:.1f}%)\n"
    else:
        leaderboard += "No strong leaders this week.\n"

    # -----------------------------
    # HEADER
    # -----------------------------
    header = (
        "🤵‍♂️ *STAN WEINSTEIN PRO SCAN* 🤵‍♂️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Total Buy: {len(all_buys)} | 🛑 Total Sell: {len(all_sells)}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    await bot.send_message(
        chat_id=CHAT_ID,
        text=header + leaderboard + full_body,
        parse_mode='Markdown'
    )


if __name__ == "__main__":
    asyncio.run(main())
