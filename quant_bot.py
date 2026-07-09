import alpaca_trade_api as tradeapi
import pandas as pd
from datetime import datetime, timedelta

# 1. Credentials Setup
API_KEY = 'REDACTED'
SECRET_KEY = 'REDACTED'
BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

# 2. Strategy Parameters
SYMBOL = 'SPY' 
QUANTITY = 1
FAST_WINDOW = 9
SLOW_WINDOW = 21

print(f"Initializing Quant Engine for {SYMBOL}...")

try:
    # 3. Dynamic Time Window Configuration
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    
    # Ingest Historical Data (With explicit start and end dates)
    print(f"Downloading IEX price arrays from {start_date} to {end_date}...")
    bars = api.get_bars(
        SYMBOL, 
        tradeapi.TimeFrame.Day, 
        start=start_date,
        end=end_date,
        feed='iex'
    ).df
    
    # Safety Check: Did the exchange give us data?
    if bars.empty:
        raise Exception("The data array returned completely empty.")

    # 4. Mathematical Transformation
    bars['SMA_Fast'] = bars['close'].rolling(window=FAST_WINDOW).mean()
    bars['SMA_Slow'] = bars['close'].rolling(window=SLOW_WINDOW).mean()
    
    # Isolate the last two days of data
    yesterday = bars.iloc[-2]
    today = bars.iloc[-1]
    
    print(f"Yesterday's Fast SMA: {yesterday['SMA_Fast']:.2f} | Slow SMA: {yesterday['SMA_Slow']:.2f}")
    print(f"Today's Fast SMA: {today['SMA_Fast']:.2f} | Slow SMA: {today['SMA_Slow']:.2f}")

    # 5. Signal Generation & Execution
    if yesterday['SMA_Fast'] <= yesterday['SMA_Slow'] and today['SMA_Fast'] > today['SMA_Slow']:
        print(f"\n+++ BUY SIGNAL DETECTED for {SYMBOL} +++")
        print("Executing Market Buy Order...")
        api.submit_order(symbol=SYMBOL, qty=QUANTITY, side='buy', type='market', time_in_force='gtc')
        print("Trade executed successfully.")
        
    elif yesterday['SMA_Fast'] >= yesterday['SMA_Slow'] and today['SMA_Fast'] < today['SMA_Slow']:
        print(f"\n--- SELL SIGNAL DETECTED for {SYMBOL} ---")
        print("Liquidating position...")
        api.close_position(SYMBOL)
        print("Position closed.")
        
    else:
        print("\nNo crossover detected today. Holding current state.")

except Exception as e:
    print(f"\nExecution Failed: {e}")