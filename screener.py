import alpaca_trade_api as tradeapi
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.stats.multitest import multipletests
from datetime import datetime, timedelta
import argparse
import itertools
import json

from config import API_KEY, SECRET_KEY, BASE_URL

BASKET = ['AAPL', 'MSFT', 'GOOG', 'META', 'AMZN', 'NFLX', 'NVDA', 'TSLA']
ALPHA = 0.05
LOOKBACK_DAYS = 365
FORMATION_FRACTION = 0.70
FDR_METHOD = 'fdr_bh'
SUPPORTED_FDR_METHODS = {'fdr_bh', 'fdr_by'}

RESULTS_FILE = "screener_results.json"


def apply_fdr_correction(ranked, alpha=ALPHA, fdr_method=FDR_METHOD):
    if fdr_method not in SUPPORTED_FDR_METHODS:
        raise ValueError(f"Unsupported FDR method: {fdr_method}")

    corrected = ranked.copy()
    rejected, corrected_pvals, _, _ = multipletests(
        corrected['P-Value'],
        alpha=alpha,
        method=fdr_method
    )
    corrected['Corrected P-Value'] = corrected_pvals
    corrected['Significant (FDR-corrected)'] = rejected
    return corrected


def cointegration_pair_results(data, pairs):
    results = []

    for pair in pairs:
        _, p_value, _ = coint(data[pair[0]], data[pair[1]])
        results.append({
            'Pair': f"{pair[0]} & {pair[1]}",
            'Asset1': pair[0],
            'Asset2': pair[1],
            'P-Value': p_value
        })

    return pd.DataFrame(results).sort_values(by='P-Value', ascending=True).reset_index(drop=True)


def screen_cointegrated_pairs(data, basket, alpha=ALPHA, fdr_method=FDR_METHOD):
    ranked = cointegration_pair_results(data, list(itertools.combinations(basket, 2)))
    return apply_fdr_correction(ranked, alpha=alpha, fdr_method=fdr_method)


def download_close_data(api, basket, start_date, end_date):
    data = pd.DataFrame()
    for ticker in basket:
        bars = api.get_bars(
            ticker,
            tradeapi.TimeFrame.Day,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            feed='iex'
        ).df
        data[ticker] = bars['close']

    return data.dropna()


def split_lookback_window(data, formation_fraction=FORMATION_FRACTION):
    split_at = int(len(data) * formation_fraction)
    if split_at <= 0 or split_at >= len(data):
        raise ValueError("Not enough data to split into formation and validation windows")

    return data.iloc[:split_at], data.iloc[split_at:]


def validate_formation_survivors(formation_ranked, validation_data, alpha=ALPHA, fdr_method=FDR_METHOD):
    ranked = formation_ranked.copy()
    ranked['Validation P-Value'] = None
    ranked['Validation Corrected P-Value'] = None
    ranked['Validation Significant (FDR-corrected)'] = False
    ranked['Approved'] = False

    formation_survivors = ranked[ranked['Significant (FDR-corrected)']]
    if formation_survivors.empty:
        return ranked

    pairs = list(zip(formation_survivors['Asset1'], formation_survivors['Asset2']))
    validation_ranked = cointegration_pair_results(validation_data, pairs)
    validation_ranked = apply_fdr_correction(validation_ranked, alpha=alpha, fdr_method=fdr_method)
    validation_ranked = validation_ranked.rename(columns={
        'P-Value': 'Validation P-Value',
        'Corrected P-Value': 'Validation Corrected P-Value',
        'Significant (FDR-corrected)': 'Validation Significant (FDR-corrected)',
    })

    validation_cols = [
        'Asset1',
        'Asset2',
        'Validation P-Value',
        'Validation Corrected P-Value',
        'Validation Significant (FDR-corrected)',
    ]
    ranked = ranked.drop(columns=[
        'Validation P-Value',
        'Validation Corrected P-Value',
        'Validation Significant (FDR-corrected)',
    ]).merge(validation_ranked[validation_cols], on=['Asset1', 'Asset2'], how='left')
    ranked['Validation Significant (FDR-corrected)'] = ranked['Validation Significant (FDR-corrected)'].fillna(False)
    ranked['Approved'] = (
        ranked['Significant (FDR-corrected)']
        & ranked['Validation Significant (FDR-corrected)']
    )
    return ranked


def last_completed_trading_day(api):
    now = pd.Timestamp.now(tz='America/New_York')
    calendar = api.get_calendar(
        start=(now.date() - timedelta(days=14)).isoformat(),
        end=now.date().isoformat()
    )
    completed = [
        session.date for session in calendar
        if pd.Timestamp.combine(session.date.date(), session.close).tz_localize('America/New_York') < now
    ]
    return completed[-1]


def save_results(ranked, basket, output_file=RESULTS_FILE, alpha=ALPHA, fdr_method=FDR_METHOD):
    approval_column = 'Approved' if 'Approved' in ranked.columns else 'Significant (FDR-corrected)'
    survivors = ranked[ranked[approval_column]]
    approved_pairs = [
        [row['Asset1'], row['Asset2']] for _, row in survivors.iterrows()
    ]
    result_columns = [
        'Asset1',
        'Asset2',
        'P-Value',
        'Corrected P-Value',
        'Significant (FDR-corrected)',
        'Validation P-Value',
        'Validation Corrected P-Value',
        'Validation Significant (FDR-corrected)',
        'Approved',
    ]
    result_columns = [column for column in result_columns if column in ranked.columns]
    all_results = (
        ranked[result_columns]
        .astype(object)
        .where(pd.notna(ranked[result_columns]), None)
        .to_dict(orient='records')
    )
    output = {
        "generated_at": datetime.now().isoformat(),
        "basket": basket,
        "alpha": alpha,
        "fdr_method": fdr_method,
        "formation_fraction": FORMATION_FRACTION,
        "approved_pairs": approved_pairs,
        "all_results": all_results
    }
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    return approved_pairs


def run_screener(
    basket=BASKET,
    alpha=ALPHA,
    lookback_days=LOOKBACK_DAYS,
    output_file=RESULTS_FILE,
    fdr_method=FDR_METHOD,
):
    api = tradeapi.REST(key_id=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

    print(f"Initializing Screener for {len(basket)} assets...")
    end_date = last_completed_trading_day(api)
    start_date = end_date - timedelta(days=lookback_days)

    print("Downloading bulk historical data...")
    data = download_close_data(api, basket, start_date, end_date)
    formation_data, validation_data = split_lookback_window(data)
    print("Data mapped. Splitting formation/validation windows and generating pairs...\n")

    formation_ranked = screen_cointegrated_pairs(formation_data, basket, alpha=alpha, fdr_method=fdr_method)
    ranked = validate_formation_survivors(
        formation_ranked,
        validation_data,
        alpha=alpha,
        fdr_method=fdr_method,
    )

    print("--- FORMATION WINDOW: ALL PAIRS, RANKED BY RAW P-VALUE ---")
    print(ranked[['Pair', 'P-Value', 'Corrected P-Value', 'Significant (FDR-corrected)']].to_string(index=False))

    survivors = ranked[ranked['Approved']]
    print(f"\n--- PAIRS SURVIVING FORMATION AND VALIDATION FDR CORRECTION ---")
    if len(survivors) == 0:
        print("None. No pair remains significant after both FDR-corrected windows.")
    else:
        print(survivors[['Pair', 'P-Value', 'Corrected P-Value', 'Validation P-Value', 'Validation Corrected P-Value']].to_string(index=False))

    # --- Save results so other scripts (e.g. z_score_bot.py) can defer to the ---
    # --- FDR-corrected finding instead of re-deriving their own approximation. ---
    approved_pairs = save_results(ranked, basket, output_file=output_file, alpha=alpha, fdr_method=fdr_method)
    print(f"\nSaved FDR-corrected results to {output_file} ({len(approved_pairs)} pair(s) approved).")
    return ranked


def main():
    parser = argparse.ArgumentParser(description="Screen equity pairs for cointegration with FDR correction.")
    parser.add_argument("--fdr-method", choices=sorted(SUPPORTED_FDR_METHODS), default=FDR_METHOD)
    args = parser.parse_args()

    try:
        run_screener(fdr_method=args.fdr_method)
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
