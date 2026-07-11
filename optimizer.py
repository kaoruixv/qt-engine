import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timedelta

# 1. Credentials Setup
from config import API_KEY, SECRET_KEY, BASE_URL
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)
SYMBOL = 'SPY'

print("Initializing Grid Search Optimizer...")

try:
    # 2. Download Data ONCE to save API bandwidth
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1825)
    
    print(f"Downloading 5-year data array for {SYMBOL}...")
    bars = api.get_bars(
        SYMBOL, 
        tradeapi.TimeFrame.Day, 
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        feed='iex'
    ).df

    # Calculate baseline Buy & Hold Return
    bars['Asset_Return'] = bars['close'].pct_change()
    buy_and_hold_return = (1 + bars['Asset_Return']).prod() - 1
    
    print(f"Baseline Buy & Hold Return: {buy_and_hold_return * 100:.2f}%\n")
    print("Running vector simulations across 150 parameter combinations...")

    # 3. Define the Grid boundaries
    fast_windows = range(5, 35, 5)   # Tests 5, 10, 15, 20, 25, 30
    slow_windows = range(40, 220, 20) # Tests 40, 60, 80 ... 200
    
    results = []

    # 4. The Brute Force Loop
    for fast, slow in itertools.product(fast_windows, slow_windows):
        # We don't test invalid combinations where fast is slower than slow
        if fast >= slow:
            continue
            
        # Create temporary columns for this specific loop
        bars['SMA_Fast'] = bars['close'].rolling(window=fast).mean()
        bars['SMA_Slow'] = bars['close'].rolling(window=slow).mean()
        
        # Generate Signal and calculate strategy return
        bars['Signal'] = np.where(bars['SMA_Fast'] > bars['SMA_Slow'], 1, 0)
        bars['Strategy_Return'] = bars['Asset_Return'] * bars['Signal'].shift(1)
        
        # Calculate final compounded return
        strategy_total_return = (1 + bars['Strategy_Return']).prod() - 1
        
        # Store the result
        results.append({
            'Fast_SMA': fast,
            'Slow_SMA': slow,
            'Return': strategy_total_return
        })

    # 5. Data Analysis: Sort the results to find the highest returns
    results_df = pd.DataFrame(results)
    top_strategies = results_df.sort_values(by='Return', ascending=False).head(5)

    print("--- TOP 5 OPTIMIZED PARAMETERS ---")
    for index, row in top_strategies.iterrows():
        fast_val = int(row['Fast_SMA'])
        slow_val = int(row['Slow_SMA'])
        ret_val = row['Return'] * 100
        
        # Did it beat the market?
        outperformed = "🏆 BEAT MARKET" if row['Return'] > buy_and_hold_return else "📉 UNDERPERFORMED"
        print(f"Fast: {fast_val:02d} | Slow: {slow_val:03d} | Return: {ret_val:>6.2f}% | {outperformed}")

except Exception as e:
    print(f"\nExecution Failed: {e}")
