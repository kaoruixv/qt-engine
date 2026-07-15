import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
from datetime import datetime, timedelta
from config import API_KEY, SECRET_KEY, BASE_URL
import sys
import json
import os

SCREENER_RESULTS_FILE = "screener_results.json"

if len(sys.argv) != 3:
    print("Usage: python3 z_score_bot.py TICKER1 TICKER2")
    sys.exit()

ASSET_1 = sys.argv[1].upper()
ASSET_2 = sys.argv[2].upper()

# --- Check this pair against the FDR-corrected screener results ---
# This defers to screener.py's properly-corrected finding rather than
# re-deriving an approximate answer here. If screener.py hasn't been run,
# or this pair wasn't in its basket, we refuse to trade rather than assume.
def check_approved(asset1, asset2):
    if not os.path.exists(SCREENER_RESULTS_FILE):
        return False, f"{SCREENER_RESULTS_FILE} not found. Run screener.py first."

    with open(SCREENER_RESULTS_FILE, 'r') as f:
        screener_data = json.load(f)

    approved = screener_data.get('approved_pairs', [])
    for pair in approved:
        if set(pair) == {asset1, asset2}:
            return True, f"Pair approved by FDR-corrected screen (generated {screener_data.get('generated_at', 'unknown time')})."

    return False, f"Pair not in FDR-corrected approved list ({len(approved)} pair(s) approved). See {SCREENER_RESULTS_FILE}."

approved, reason = check_approved(ASSET_1, ASSET_2)

print(f"Initializing LIVE Z-Score Execution Engine for {ASSET_1} & {ASSET_2}...")
print(f"\n--- SCREENER APPROVAL CHECK ---")
print(reason)

if not approved:
    print("EXECUTION: HALTED. This pair has not cleared multiple-comparisons-corrected cointegration testing.")
    sys.exit()

api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

try:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    bars_1 = api.get_bars(ASSET_1, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
    bars_2 = api.get_bars(ASSET_2, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df

    data = pd.DataFrame({ASSET_1: bars_1['close'], ASSET_2: bars_2['close']}).dropna()

    X = sm.add_constant(data[ASSET_2])
    model = sm.OLS(data[ASSET_1], X)
    results = model.fit()
    hedge_ratio = round(results.params.iloc[1], 2)

    data['Spread'] = data[ASSET_1] - (hedge_ratio * data[ASSET_2])

    # --- OU fit: AR(1) regression on the spread, for the half-life-based window ---
    spread_lag = data['Spread'].shift(1).dropna()
    spread_now = data['Spread'].loc[spread_lag.index]

    X_ar = sm.add_constant(spread_lag)
    ar_model = sm.OLS(spread_now, X_ar).fit()
    a, b = ar_model.params.iloc[0], ar_model.params.iloc[1]

    if not (0 < b < 1):
        print(f"WARNING: AR(1) coefficient b={b:.3f} outside (0,1) -- reversion speed undefined. Falling back to 30-day window.")
        window = 30
    else:
        theta = -np.log(b)
        half_life = np.log(2) / theta
        window = max(5, int(round(half_life)))
        print(f"OU fit: mean-reversion speed theta={theta:.4f}, half-life={half_life:.1f} days -> using {window}-day window")

    data['Rolling_Mean'] = data['Spread'].rolling(window=window).mean()
    data['Rolling_Std'] = data['Spread'].rolling(window=window).std()
    data['Z_Score'] = (data['Spread'] - data['Rolling_Mean']) / data['Rolling_Std']

    today = data.iloc[-1]

    print("\n--- TODAY'S MARKET STATE ---")
    print(f"{ASSET_1} Price: ${today[ASSET_1]:.2f} | {ASSET_2} Price: ${today[ASSET_2]:.2f}")
    print(f"Hedge Ratio: 1 to {hedge_ratio}")
    print(f"Current Z-Score: {today['Z_Score']:+.2f}")

    print("\n--- TRANSMITTING ORDERS TO EXCHANGE ---")

    if today['Z_Score'] > 2.0:
        print(f"SIGNAL: {ASSET_1} is overpriced. Executing Arbitrage...")
        api.submit_order(symbol=ASSET_1, qty=1, side='sell', type='market', time_in_force='day')
        api.submit_order(symbol=ASSET_2, qty=round(hedge_ratio), side='buy', type='market', time_in_force='day')
        print("SUCCESS: Dollar-Neutral position established.")
    elif today['Z_Score'] < -2.0:
        print(f"SIGNAL: {ASSET_1} is underpriced. Executing Arbitrage...")
        api.submit_order(symbol=ASSET_1, qty=1, side='buy', type='market', time_in_force='day')
        api.submit_order(symbol=ASSET_2, qty=round(hedge_ratio), side='sell', type='market', time_in_force='day')
        print("SUCCESS: Dollar-Neutral position established.")
    elif abs(today['Z_Score']) < 0.5:
        print("SIGNAL: Spread has reverted to the mean. Taking Profit.")
        try:
            api.close_position(ASSET_1)
            api.close_position(ASSET_2)
            print("SUCCESS: Positions liquidated.")
        except Exception as e:
            print("STATUS: No active positions currently held in inventory to liquidate.")
    else:
        print("SIGNAL: Z-Score is in the normal zone (-2.0 to 2.0).")
        print("EXECUTION: HOLD. No new orders transmitted.")

except Exception as e:
    print(f"\nExecution Failed: {e}")
