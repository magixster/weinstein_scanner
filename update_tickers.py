import yfinance as yf
import requests
import concurrent.futures
import os

# --- CONFIG ---
TICKER_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
MIN_MARKET_CAP = 200_000_000  # 200 Million

def get_market_cap(ticker):
    """Fetch market cap using fast_info (optimized)."""
    try:
        t = yf.Ticker(ticker)
        # fast_info is much quicker than .info
        mkt_cap = t.fast_info['market_cap']
        if mkt_cap >= MIN_MARKET_CAP:
            return ticker
    except:
        return None
    return None

def refresh_us_tickers():
    print("Fetching raw ticker list from GitHub...")
    response = requests.get(TICKER_URL)
    raw_tickers = [t.strip() for t in response.text.split('\n') if t.strip()]
    
    # LIMIT: For testing, you might want to slice this: raw_tickers[:500]
    # To process all 10k+, use higher thread count
    print(f"Processing {len(raw_tickers)} tickers. This may take a while...")
    
    valid_tickers = []
    
    # Use ThreadPoolExecutor for concurrent I/O bound requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(get_market_cap, raw_tickers))
        valid_tickers = [r for r in results if r is not None]

    # Save to a python file for the main bot to import
    with open("generated_tickers.py", "w") as f:
        f.write(f"US_STOCKS = {valid_tickers}")
    
    print(f"✅ Success! Kept {len(valid_tickers)} stocks with Cap > $200M.")

if __name__ == "__main__":
    refresh_us_tickers()
