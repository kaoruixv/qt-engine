import alpaca_trade_api as tradeapi

# 1. Input your exact keys
API_KEY = 'REDACTED'
SECRET_KEY = 'REDACTED'

# 2. Connect to the market (Forcing the exact URL to prevent the /v2/v2 bug)
print("Connecting to Alpaca Paper Market...")
api = tradeapi.REST(
    key_id=API_KEY, 
    secret_key=SECRET_KEY, 
    base_url='https://paper-api.alpaca.markets'
)

# 3. Retrieve account data
account = api.get_account()

# 4. Prove it works
print("\n--- CONNECTION SUCCESSFUL ---")
print(f"Account Status: {account.status}")
print(f"Paper Trading Balance: ${account.cash}")
print(f"Total Buying Power: ${account.buying_power}")

# 5. Execute a test trade (Buy 1 share of Apple)
print("\nExecuting test trade: Buying 1 share of AAPL...")
api.submit_order(
    symbol='AAPL',
    qty=1,
    side='buy',
    type='market',
    time_in_force='gtc'
)
print("Trade submitted! Check your Alpaca web dashboard.")