import os
import requests
from dotenv import load_dotenv

# 1. Find the exact, absolute path of the folder this script is sitting in
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')

# 2. Force load the vault and OVERRIDE any ghost variables in the terminal's cache
load_dotenv(dotenv_path=env_path, override=True)

# 3. Securely read the credentials
API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
BASE_URL = 'https://paper-api.alpaca.markets'

def test_secure_connection():
    print(f"🔍 Forcing dotenv to read vault at: {env_path}")
    print("Initiating secure connection to Alpaca...")

    if not API_KEY or not SECRET_KEY:
        print("❌ ERROR: Credentials still missing.")
        return

    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    }

    try:
        response = requests.get(f"{BASE_URL}/v2/account", headers=headers)
        
        if response.status_code == 200:
            account = response.json()
            print("✅ SUCCESS: Connected to Alpaca Paper Trading!")
            print(f"   Account Status: {account.get('status')}")
            print(f"   Portfolio Value: ${float(account.get('portfolio_value', 0)):.2f}")
        else:
            print(f"❌ ERROR: Authentication failed. (Status Code: {response.status_code})")
            print(f"   Message: {response.text}")
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Could not reach Alpaca servers.\nDetails: {e}")

if __name__ == "__main__":
    test_secure_connection()