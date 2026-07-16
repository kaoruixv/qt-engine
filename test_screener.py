import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from screener import apply_fdr_correction, main, run_screener


class FDRCorrectionTests(unittest.TestCase):
    def test_marks_expected_pairs_significant_after_bh_correction(self):
        ranked = pd.DataFrame({
            'Pair': ['A & B', 'A & C', 'A & D', 'A & E'],
            'Asset1': ['A', 'A', 'A', 'A'],
            'Asset2': ['B', 'C', 'D', 'E'],
            'P-Value': [0.001, 0.01, 0.02, 0.20],
        })

        corrected = apply_fdr_correction(ranked, alpha=0.05)

        self.assertEqual(
            corrected['Significant (FDR-corrected)'].tolist(),
            [True, True, True, False],
        )
        self.assertEqual(
            corrected['Corrected P-Value'].round(6).tolist(),
            [0.004000, 0.020000, 0.026667, 0.200000],
        )

    def test_supports_by_correction_for_dependent_tests(self):
        ranked = pd.DataFrame({
            'Pair': ['A & B', 'A & C', 'A & D', 'A & E'],
            'Asset1': ['A', 'A', 'A', 'A'],
            'Asset2': ['B', 'C', 'D', 'E'],
            'P-Value': [0.001, 0.01, 0.02, 0.20],
        })

        corrected = apply_fdr_correction(ranked, alpha=0.05, fdr_method='fdr_by')

        self.assertEqual(
            corrected['Significant (FDR-corrected)'].tolist(),
            [True, True, False, False],
        )
        self.assertEqual(
            corrected['Corrected P-Value'].round(6).tolist(),
            [0.008333, 0.041667, 0.055556, 0.416667],
        )

    def test_preserves_row_alignment_for_unsorted_input(self):
        ranked = pd.DataFrame({
            'Pair': ['A & E', 'A & B', 'A & D', 'A & C'],
            'Asset1': ['A', 'A', 'A', 'A'],
            'Asset2': ['E', 'B', 'D', 'C'],
            'P-Value': [0.20, 0.001, 0.02, 0.01],
        })

        corrected = apply_fdr_correction(ranked, alpha=0.05)

        by_pair = corrected.set_index('Pair')
        self.assertFalse(bool(by_pair.loc['A & E', 'Significant (FDR-corrected)']))
        self.assertTrue(bool(by_pair.loc['A & B', 'Significant (FDR-corrected)']))
        self.assertAlmostEqual(by_pair.loc['A & B', 'Corrected P-Value'], 0.004)
        self.assertAlmostEqual(by_pair.loc['A & E', 'Corrected P-Value'], 0.20)

    def test_rejects_no_pairs_when_all_corrected_values_exceed_alpha(self):
        ranked = pd.DataFrame({
            'Pair': ['A & B', 'A & C', 'A & D'],
            'Asset1': ['A', 'A', 'A'],
            'Asset2': ['B', 'C', 'D'],
            'P-Value': [0.04, 0.06, 0.07],
        })

        corrected = apply_fdr_correction(ranked, alpha=0.05)

        self.assertEqual(
            corrected['Significant (FDR-corrected)'].tolist(),
            [False, False, False],
        )
        self.assertTrue((corrected['Corrected P-Value'] > 0.05).all())

    def test_run_screener_filters_pair_that_fails_validation_window(self):
        data = pd.DataFrame({
            'A': range(10),
            'B': range(10, 20),
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, 'screener_results.json')
            with patch('screener.tradeapi.REST', return_value=Mock()), \
                    patch('screener.last_completed_trading_day', return_value=pd.Timestamp('2026-01-31')), \
                    patch('screener.download_close_data', return_value=data), \
                    patch('screener.coint') as coint_mock, \
                    patch('builtins.print'):
                coint_mock.side_effect = [
                    (0, 0.001, None),
                    (0, 0.20, None),
                ]

                ranked = run_screener(
                    basket=['A', 'B'],
                    alpha=0.05,
                    lookback_days=10,
                    output_file=output_file,
                )

            with open(output_file, 'r') as f:
                saved = json.load(f)

        self.assertEqual(saved['approved_pairs'], [])
        self.assertTrue(bool(ranked.loc[0, 'Significant (FDR-corrected)']))
        self.assertFalse(bool(ranked.loc[0, 'Validation Significant (FDR-corrected)']))
        self.assertFalse(bool(ranked.loc[0, 'Approved']))

    def test_cli_passes_fdr_method_to_run_screener(self):
        with patch('sys.argv', ['screener.py', '--fdr-method', 'fdr_by']), \
                patch('screener.run_screener') as run_screener_mock:
            main()

        run_screener_mock.assert_called_once_with(fdr_method='fdr_by')


if __name__ == "__main__":
    unittest.main()
