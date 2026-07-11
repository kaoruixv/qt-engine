import alpaca_trade_api as tradeapi
import pandas as pd
import statsmodels.api as sm
from datetime import datetime, timedelta
import sys

# Argument Check
if len(sys.argv) != 3:
    print("Usage: python3 z_score_bot.py TICKER1 TICKER2")
    sys.exit()

ASSET_1 = sys.argv[1].upper()
ASSET_2 = sys.argv[2].upper()

# 1. Credentials Setup (PASTE YOUR REAL KEYS HERE)
from config import API_KEY, SECRET_KEY, BASE_URL
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

print(f"Initializing LIVE Z-Score Execution Engine for {ASSET_1} & {ASSET_2}...")

try:
    # 2. Download Data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    bars_1 = api.get_bars(ASSET_1, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
    bars_2 = api.get_bars(ASSET_2, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
    
    data = pd.DataFrame({ASSET_1: bars_1['close'], ASSET_2: bars_2['close']}).dropna()

    # 3. Hedge Ratio & Z-Score Math
    model = sm.OLS(data[ASSET_1], data[ASSET_2])
    results = model.fit()
    hedge_ratio = round(results.params.iloc[0], 2)
    
    data['Spread'] = data[ASSET_1] - (hedge_ratio * data[ASSET_2])
    window = 30
    data['Rolling_Mean'] = data['Spread'].rolling(window=window).mean()
    data['Rolling_Std'] = data['Spread'].rolling(window=window).std()
    data['Z_Score'] = (data['Spread'] - data['Rolling_Mean']) / data['Rolling_Std']

    today = data.iloc[-1]
    
    print(f"\n--- TODAY'S MARKET STATE ---")
    print(f"{ASSET_1} Price: ${today[ASSET_1]:.2f} | {ASSET_2} Price: ${today[ASSET_2]:.2f}")
    print(f"Hedge Ratio: 1 to {hedge_ratio}")
    print(f"Current Z-Score: {today['Z_Score']:+.2f}")

    # 4. LIVE EXECUTION LOGIC
    print("\n--- TRANSMITTING ORDERS TO EXCHANGE ---")
    
    if today['Z_Score'] > 2.0:
        print(f"SIGNAL: {ASSET_1} is overpriced. Executing Arbitrage...")
        api.submit_order(symbol=ASSET_1, qty=1, side='sell', type='market', time_in_force='day')
        api.submit_order(symbol=ASSET_2, qty=hedge_ratio, side='buy', type='market', time_in_force='day')
        print("SUCCESS: Dollar-Neutral position established.")

    elif today['Z_Score'] < -2.0:
        print(f"SIGNAL: {ASSET_1} is underpriced. Executing Arbitrage...")
        api.submit_order(symbol=ASSET_1, qty=1, side='buy', type='market', time_in_force='day')
        api.submit_order(symbol=ASSET_2, qty=hedge_ratio, side='sell', type='market', time_in_force='day')
        print("SUCCESS: Dollar-Neutral position established.")

    elif abs(today['Z_Score']) < 0.5:
        print(f"SIGNAL: Spread has reverted to the mean. Taking Profit.")
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
