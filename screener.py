import alpaca_trade_api as tradeapi
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.stats.multitest import multipletests
from datetime import datetime, timedelta
import itertools
import json
import os

from config import API_KEY, SECRET_KEY, BASE_URL
api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

basket = ['AAPL', 'MSFT', 'GOOG', 'META', 'AMZN', 'NFLX', 'NVDA', 'TSLA']

RESULTS_FILE = "screener_results.json"

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
        results.append({'Pair': f"{pair[0]} & {pair[1]}", 'Asset1': pair[0], 'Asset2': pair[1], 'P-Value': p_value})

    ranked = pd.DataFrame(results).sort_values(by='P-Value', ascending=True).reset_index(drop=True)

    rejected, corrected_pvals, _, _ = multipletests(ranked['P-Value'], alpha=0.05, method='fdr_bh')
    ranked['Corrected P-Value'] = corrected_pvals
    ranked['Significant (FDR-corrected)'] = rejected

    print("--- ALL PAIRS, RANKED BY RAW P-VALUE ---")
    print(ranked[['Pair', 'P-Value', 'Corrected P-Value', 'Significant (FDR-corrected)']].to_string(index=False))

    survivors = ranked[ranked['Significant (FDR-corrected)']]
    print(f"\n--- PAIRS SURVIVING MULTIPLE-COMPARISONS CORRECTION ---")
    if len(survivors) == 0:
        print("None. No pair remains significant after FDR correction -- treat all raw p-values above with caution.")
    else:
        print(survivors[['Pair', 'P-Value', 'Corrected P-Value']].to_string(index=False))

    # --- Save results so other scripts (e.g. z_score_bot.py) can defer to the ---
    # --- FDR-corrected finding instead of re-deriving their own approximation. ---
    approved_pairs = [
        [row['Asset1'], row['Asset2']] for _, row in survivors.iterrows()
    ]
    output = {
        "generated_at": datetime.now().isoformat(),
        "basket": basket,
        "alpha": 0.05,
        "approved_pairs": approved_pairs,
        "all_results": ranked[['Asset1', 'Asset2', 'P-Value', 'Corrected P-Value', 'Significant (FDR-corrected)']].to_dict(orient='records')
    }
    with open(RESULTS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved FDR-corrected results to {RESULTS_FILE} ({len(approved_pairs)} pair(s) approved).")

except Exception as e:
    print(f"\nError: {e}")
