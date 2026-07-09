import alpaca_trade_api as tradeapi
import time

# 1. Credentials Setup
API_KEY = 'REDACTED'
SECRET_KEY = 'REDACTED'

BASE_URL = 'https://paper-api.alpaca.markets'

# 2. Initialize REST Client
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

# 3. Target Configuration
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
    while True:
        # Check the exact status of our specific order ID
        order = api.get_order(buy_order.id)
        
        if order.status == 'filled':
            print(f"\nOrder Filled! We officially own {SYMBOL}.")
            break # Exit the loop and proceed
            
        elif order.status in ['canceled', 'rejected', 'expired']:
            raise Exception(f"Buy order was {order.status} by the exchange.")
            
        else:
            print(f"Order status: '{order.status}'. Market is likely closed. Checking again in 5 seconds...")
            time.sleep(5)
    
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