import alpaca_trade_api as tradeapi
API_KEY = 'REDACTED'
SECRET_KEY = 'REDACTED'
BASE_URL = 'https://paper-api.alpaca.markets'

try:
    api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)
    account = api.get_account()
    print("SUCCESS: Connection established.")
    print(f"Account Status: {account.status}")
except Exception as e:
    print(f"FAILURE: Authentication failed.")
    print(f"Error details: {e}")
