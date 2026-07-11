import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import statsmodels.api as sm
from datetime import datetime, timedelta
from config import API_KEY, SECRET_KEY, BASE_URL
import sys

print("Initializing connection...")
try:
    api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)
    account = api.get_account()
    print(f"Connection Successful! Account Status: {account.status}")
except Exception as e:
    print(f"Connection Failed: {e}")
    print("Check your keys and ensure no extra spaces are around them.")
    sys.exit()

if len(sys.argv) != 3:
    print("Usage: python3 backtest.py TICKER1 TICKER2")
    sys.exit()

ASSET_1, ASSET_2 = sys.argv[1].upper(), sys.argv[2].upper()
print(f"Running Institutional Backtest for {ASSET_1} & {ASSET_2}...")

start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
bars_1 = api.get_bars(ASSET_1, tradeapi.TimeFrame.Day, start=start_date).df
bars_2 = api.get_bars(ASSET_2, tradeapi.TimeFrame.Day, start=start_date).df
df = pd.DataFrame({'a1': bars_1['close'], 'a2': bars_2['close']}).dropna()

# 5. Walk-forward hedge ratio estimation (avoids look-ahead bias)
FORMATION_WINDOW = 60  # days of history used to estimate the hedge ratio at each point

hedge_ratios = [np.nan] * len(df)
for i in range(FORMATION_WINDOW, len(df)):
    train = df.iloc[i - FORMATION_WINDOW:i]
    X_train = sm.add_constant(train['a2'])
    model = sm.OLS(train['a1'], X_train).fit()
    hedge_ratios[i] = model.params.iloc[1]

df['hedge_ratio'] = hedge_ratios

# Spread & Z-Score, using only the hedge ratio known at each point in time
df['spread'] = df['a1'] - (df['hedge_ratio'] * df['a2'])
df['mean'] = df['spread'].rolling(window=30).mean()
df['std'] = df['spread'].rolling(window=30).std()
df['zscore'] = (df['spread'] - df['mean']) / df['std']

# Trading Rules
conditions = [
    (df['zscore'] > 3) | (df['zscore'] < -3),
    (df['zscore'] > 2),
    (df['zscore'] < -2)
]
choices = [0, -1, 1]
df['position'] = np.select(conditions, choices, default=np.nan)
df['position'] = df['position'].ffill().fillna(0)

# 6. PnL Calculation
df['spread_diff'] = df['spread'].diff()
df['returns'] = df['spread_diff'] * df['position'].shift(1)
df['cumulative_pnl'] = df['returns'].cumsum()

# 7. Metrics
sharpe = (df['returns'].mean() / df['returns'].std()) * np.sqrt(252)
drawdown = (df['cumulative_pnl'] - df['cumulative_pnl'].cummax()).min()
total_pnl = df['cumulative_pnl'].iloc[-1]

print(f"\n--- INSTITUTIONAL BACKTEST RESULTS ---")
print(f"Formation window: {FORMATION_WINDOW} days (hedge ratio re-estimated using only prior data)")
print(f"Sharpe Ratio: {sharpe:.2f}")
print(f"Max Drawdown: ${drawdown:.2f}")
print(f"Total Theoretical Profit: ${total_pnl:.2f}")
