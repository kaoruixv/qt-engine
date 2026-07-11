import alpaca_trade_api as tradeapi
import time
from config import API_KEY, SECRET_KEY, BASE_URL

# Initialize REST Client
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

# Target Configuration
SYMBOL = 'NVDA'
QUANTITY = 1
TRAIL_PERCENTAGE = 2.0

print(f"Initializing Risk Automation Engine for ticker: {SYMBOL}...")

try:
    # Step A: Execute entry order
    print(f"Sending Market Buy Order for {QUANTITY} share(s) of {SYMBOL}...")
    buy_order = api.submit_order(
        symbol=SYMBOL,
        qty=QUANTITY,
        side='buy',
        type='market',
        time_in_force='gtc'
    )

    # Step B: The Verification Loop
    print("Waiting for the exchange to fill the order...")
    MAX_RETRIES = 60  # 60 attempts * 5s = 5 minutes max wait
    for attempt in range(MAX_RETRIES):
        order = api.get_order(buy_order.id)
        if order.status == 'filled':
            print(f"\nOrder Filled! We officially own {SYMBOL}.")
            break
        elif order.status in ['canceled', 'rejected', 'expired']:
            raise Exception(f"Buy order was {order.status} by the exchange.")
        else:
            print(f"Order status: '{order.status}'. Market is likely closed. Checking again in 5 seconds... ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(5)
    else:
        raise TimeoutError(f"Order {buy_order.id} did not fill within {MAX_RETRIES * 5} seconds. Cancel it manually if needed via api.cancel_order().")

    # Step C: Deploy the trailing stop-loss architecture
    print(f"\nDeploying {TRAIL_PERCENTAGE}% Trailing Stop-Loss protection...")
    protection_order = api.submit_order(
        symbol=SYMBOL,
        qty=QUANTITY,
        side='sell',
        type='trailing_stop',
        trail_percent=TRAIL_PERCENTAGE,
        time_in_force='gtc'
    )

    print("\n--- AUTOMATION SUCCESSFUL ---")
    print(f"Position opened. Trailing stop-loss set at -{TRAIL_PERCENTAGE}% from peak.")

except Exception as e:
    print(f"\nExecution Failed: {e}")
