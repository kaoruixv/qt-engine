import os
from dotenv import load_dotenv
_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_dir, ".env"), override=True)
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

import alpaca_trade_api as tradeapi
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
from datetime import datetime, timedelta
import sys

# 1. Terminal Argument Checker
if len(sys.argv) != 3:
    print("❌ ERROR: You must provide exactly two tickers.")
    print("Example usage: python3 pair_data.py XOM CVX")
    sys.exit()

# 2. Credentials Setup
BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

# 3. Dynamic Pair Definition from Terminal
ASSET_1 = sys.argv[1].upper()
ASSET_2 = sys.argv[2].upper()

print(f"Initializing Statistical Arbitrage Data Engine for {ASSET_1} & {ASSET_2}...")

try:
    # 4. Download Historical Data (2 Years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    
    bars_1 = api.get_bars(ASSET_1, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
    bars_2 = api.get_bars(ASSET_2, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
    
    data = pd.DataFrame({
        ASSET_1: bars_1['close'],
        ASSET_2: bars_2['close']
    }).dropna()
    
    # 5. Statistical Cointegration Test
    score, p_value, _ = coint(data[ASSET_1], data[ASSET_2])
    
    print(f"\nTest Score: {score:.4f}")
    print(f"P-Value:    {p_value:.4f}")

    # 6. The Logic Gate
    if p_value < 0.05:
        print(f"\n+++ CONCLUSION: SUCCESS +++")
        print(f"{ASSET_1} and {ASSET_2} are statistically cointegrated.")
    else:
        print(f"\n--- CONCLUSION: FAILED ---")
        print(f"{ASSET_1} and {ASSET_2} are NOT currently cointegrated.")

except Exception as e:
    print(f"\nExecution Failed: {e}")