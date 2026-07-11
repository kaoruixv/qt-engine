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

    bars['Asset_Return'] = bars['close'].pct_change()

    # 2b. Train/test split: fit parameters on the first 80%, evaluate on the last 20%.
    # This is the fix — previously the grid search picked "winning" parameters
    # using the same data it was then evaluated on, which is look-ahead bias
    # baked into the parameter selection itself.
    split_idx = int(len(bars) * 0.8)
    train = bars.iloc[:split_idx].copy()
    test = bars.iloc[split_idx:].copy()

    train_buy_hold = (1 + train['Asset_Return']).prod() - 1
    test_buy_hold = (1 + test['Asset_Return']).prod() - 1

    print(f"Train period: {train.index[0].date()} to {train.index[-1].date()} ({len(train)} days)")
    print(f"Test period:  {test.index[0].date()} to {test.index[-1].date()} ({len(test)} days)")
    print(f"Train Buy & Hold Return: {train_buy_hold * 100:.2f}%")
    print(f"Test Buy & Hold Return:  {test_buy_hold * 100:.2f}%\n")
    print("Running grid search on TRAINING data only...")

    # 3. Define the Grid boundaries
    fast_windows = range(5, 35, 5)
    slow_windows = range(40, 220, 20)

    results = []

    # 4. The Brute Force Loop — fit and rank on TRAIN only
    for fast, slow in itertools.product(fast_windows, slow_windows):
        if fast >= slow:
            continue

        train['SMA_Fast'] = train['close'].rolling(window=fast).mean()
        train['SMA_Slow'] = train['close'].rolling(window=slow).mean()
        train['Signal'] = np.where(train['SMA_Fast'] > train['SMA_Slow'], 1, 0)
        train['Strategy_Return'] = train['Asset_Return'] * train['Signal'].shift(1)

        strategy_total_return = (1 + train['Strategy_Return']).prod() - 1
        strategy_std = train['Strategy_Return'].std()
        sharpe = (train['Strategy_Return'].mean() / strategy_std) * np.sqrt(252) if strategy_std > 0 else 0

        results.append({
            'Fast_SMA': fast,
            'Slow_SMA': slow,
            'Train_Return': strategy_total_return,
            'Train_Sharpe': sharpe
        })

    # 5. Rank by SHARPE (risk-adjusted), not raw return
    results_df = pd.DataFrame(results)
    top_strategies = results_df.sort_values(by='Train_Sharpe', ascending=False).head(5)

    print("--- TOP 5 PARAMETERS (RANKED BY TRAIN SHARPE) ---")
    for index, row in top_strategies.iterrows():
        fast_val = int(row['Fast_SMA'])
        slow_val = int(row['Slow_SMA'])
        print(f"Fast: {fast_val:02d} | Slow: {slow_val:03d} | Train Return: {row['Train_Return']*100:>6.2f}% | Train Sharpe: {row['Train_Sharpe']:.2f}")

    # 6. Evaluate the SINGLE best parameter set on the held-out TEST data
    best = top_strategies.iloc[0]
    fast, slow = int(best['Fast_SMA']), int(best['Slow_SMA'])

    test['SMA_Fast'] = test['close'].rolling(window=fast).mean()
    test['SMA_Slow'] = test['close'].rolling(window=slow).mean()
    test['Signal'] = np.where(test['SMA_Fast'] > test['SMA_Slow'], 1, 0)
    test['Strategy_Return'] = test['Asset_Return'] * test['Signal'].shift(1)

    test_total_return = (1 + test['Strategy_Return']).prod() - 1
    test_std = test['Strategy_Return'].std()
    test_sharpe = (test['Strategy_Return'].mean() / test_std) * np.sqrt(252) if test_std > 0 else 0

    print(f"\n--- OUT-OF-SAMPLE TEST: Fast={fast}, Slow={slow} ---")
    print(f"Test Return: {test_total_return*100:.2f}% | Test Sharpe: {test_sharpe:.2f}")
    outperformed = "🏆 BEAT MARKET" if test_total_return > test_buy_hold else "📉 UNDERPERFORMED"
    print(f"vs. Test Buy & Hold ({test_buy_hold*100:.2f}%): {outperformed}")

except Exception as e:
    print(f"\nExecution Failed: {e}")
