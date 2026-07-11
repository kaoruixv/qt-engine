import alpaca_trade_api as tradeapi
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.stats.multitest import multipletests
from datetime import datetime, timedelta
import itertools
import os

# Credentials
from config import API_KEY, SECRET_KEY, BASE_URL
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

# The Target Basket
basket = ['AAPL', 'MSFT', 'GOOG', 'META', 'AMZN', 'NFLX', 'NVDA', 'TSLA']

print(f"Initializing Screener for {len(basket)} assets...")

try:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    print("Downloading bulk historical data...")
    data = pd.DataFrame()
    for ticker in basket:
        bars = api.get_bars(ticker, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex').df
        data[ticker] = bars['close']

    data = data.dropna()
    print("Data mapped. Generating pairs...\n")

    pairs = list(itertools.combinations(basket, 2))
    results = []

    for pair in pairs:
        score, p_value, _ = coint(data[pair[0]], data[pair[1]])
        results.append({'Pair': f"{pair[0]} & {pair[1]}", 'P-Value': p_value})

    ranked = pd.DataFrame(results).sort_values(by='P-Value', ascending=True).reset_index(drop=True)

    # Benjamini-Hochberg correction for multiple comparisons.
    # Testing 28 pairs at raw alpha=0.05 means ~1-2 "significant" results
    # are expected by chance alone, even with no real cointegration.
    rejected, corrected_pvals, _, _ = multipletests(ranked['P-Value'], alpha=0.05, method='fdr_bh')
    ranked['Corrected P-Value'] = corrected_pvals
    ranked['Significant (FDR-corrected)'] = rejected

    print("--- ALL PAIRS, RANKED BY RAW P-VALUE ---")
    print(ranked.to_string(index=False))

    survivors = ranked[ranked['Significant (FDR-corrected)']]
    print(f"\n--- PAIRS SURVIVING MULTIPLE-COMPARISONS CORRECTION ---")
    if len(survivors) == 0:
        print("None. No pair remains significant after FDR correction — treat all raw p-values above with caution.")
    else:
        print(survivors.to_string(index=False))

except Exception as e:
    print(f"\nError: {e}")
