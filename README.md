# qt-engine

A statistical arbitrage pairs-trading research pipeline: cointegration screening,
z-score-based signal generation, walk-forward backtesting, and parameter
optimization — built to surface real findings, including negative ones.

## What this actually found

Two honest, verifiable results came out of this project, and both are
reported here even though neither supports "the strategy works":

1. **Zero pairs survive multiple-comparisons correction.** `screener.py`
   tests 28 candidate pairs for cointegration. The best raw result
   (META/NFLX, p = 0.0018) looks strong in isolation — but testing 28
   pairs means ~1-2 false positives are expected by chance alone, even
   if nothing is real. After Benjamini-Hochberg FDR correction, that
   same pair's adjusted p-value is 0.0515 — just above the 0.05
   threshold. **None of the 28 pairs survive correction.**
   `z_score_bot.py` now defers to `screener.py`'s FDR-corrected output
   (`screener_results.json`) instead of re-approximating significance
   on its own.

2. **The optimizer's "winning" parameter set was overfit.** `optimizer.py`
   originally selected parameters by maximizing in-sample Sharpe ratio
   with no train/test split — a classic winner's-curse setup: with
   enough parameter combinations tried, one will fit historical noise
   well by chance, regardless of whether any real edge exists. Adding
   a walk-forward train/test split exposed this: the in-sample "winner"
   returned 5.56% out-of-sample, against a 20.61% buy-and-hold
   benchmark over the same period, and the Sharpe ratio flipped sign
   entirely once transaction costs and the honest (non-overfit)
   expected value were accounted for.

## Other fixes in this pass

- Removed hardcoded Alpaca API keys from 9 files; centralized config via
  `config.py` + `.env`; scrubbed leaked keys from git history with
  `git filter-repo`.
- Fixed a missing-intercept bug in the OLS hedge-ratio regression.
- Eliminated look-ahead bias in `backtest.py` by switching to
  walk-forward hedge-ratio estimation (previously used full-sample
  data to compute hedge ratios applied to earlier trades).
- Fixed an infinite polling loop in `risk_bot.py`.
- Added `requirements.txt`.

## Why report null and negative results

A backtest that shows a profitable strategy and was never stress-tested
proves nothing — overfitting is the default failure mode in this kind
of research, and it's easy to find *a* combination of pairs and
parameters that looks good on historical data by construction. The
useful test is whether a result survives correction for how many
chances it was given to look good by luck. Here, neither the pair
selection nor the optimized parameters survived that test, and that's
the finding worth reporting, not hiding.

## Structure

- `screener.py` — cointegration testing across candidate pairs, with
  FDR correction
- `z_score_bot.py` — signal generation, deferring to FDR-corrected
  screener results
- `backtest.py` — walk-forward backtesting engine
- `optimizer.py` — parameter search with train/test split
- `risk_bot.py` — position/risk monitoring
- `config.py` / `.env` — credentials and configuration (not committed)

## Setup

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env   # add your Alpaca API keys here
\`\`\`
