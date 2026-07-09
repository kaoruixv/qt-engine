import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 1. Credentials Setup
API_KEY = 'REDACTED'
SECRET_KEY = 'REDACTED'
BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)
SYMBOL = 'SPY'

# Optimal parameters from previous Grid Search
FAST_WINDOW = 30
SLOW_WINDOW = 200
ATR_WINDOW = 14

print(f"Initializing Multi-Factor Engine (SMA + ATR) for {SYMBOL}...")

try:
    # 2. Download Data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1825)
    
    bars = api.get_bars(
        SYMBOL, tradeapi.TimeFrame.Day, 
        start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex'
    ).df

    # 3. Factor 1: Moving Averages
    bars['SMA_Fast'] = bars['close'].rolling(window=FAST_WINDOW).mean()
    bars['SMA_Slow'] = bars['close'].rolling(window=SLOW_WINDOW).mean()
    
    # 4. Factor 2: Average True Range (ATR) Calculus
    # True Range = Max(H-L, |H-Cp|, |L-Cp|)
    high_low = bars['high'] - bars['low']
    high_close = np.abs(bars['high'] - bars['close'].shift())
    low_close = np.abs(bars['low'] - bars['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    bars['True_Range'] = np.max(ranges, axis=1)
    bars['ATR'] = bars['True_Range'].rolling(window=ATR_WINDOW).mean()
    
    # Calculate a 50-day rolling average of the ATR to determine if current volatility is "High" or "Low"
    bars['ATR_Baseline'] = bars['ATR'].rolling(window=50).mean()

    # 5. Signal Generation (The Logic Gate)
    # 1 if Fast > Slow AND Current Volatility is BELOW the baseline (Calm). Otherwise 0 (Cash).
    bars['Signal'] = np.where(
        (bars['SMA_Fast'] > bars['SMA_Slow']) & (bars['ATR'] < bars['ATR_Baseline']), 
        1, 0
    )
    
    # 6. Performance Calculus
    bars['Asset_Return'] = bars['close'].pct_change()
    bars['Strategy_Return'] = bars['Asset_Return'] * bars['Signal'].shift(1)
    
    initial_capital = 10000
    final_asset = (1 + bars['Asset_Return']).cumprod().iloc[-1] * initial_capital
    final_strategy = (1 + bars['Strategy_Return']).cumprod().iloc[-1] * initial_capital
    
    print("\n--- 5-YEAR MULTI-FACTOR RESULTS ---")
    print(f"Buy & Hold Final Value: ${final_asset:,.2f}")
    print(f"Filtered Strategy Value: ${final_strategy:,.2f}")
    
    # Count how many days the bot was forced into cash by the volatility filter
    days_in_cash = (bars['Signal'] == 0).sum()
    total_days = len(bars)
    print(f"\nCapital Protection Metric:")
    print(f"The ATR filter kept you safely in cash for {days_in_cash} out of {total_days} trading days.")

except Exception as e:
    print(f"\nExecution Failed: {e}")