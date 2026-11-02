"""
Consolidate the Aetherdrift Play Booster profitability results.

Place this script in the MTG-Pack-Profitability project root and run:
    python3 consolidate_research_results.py

Inputs (created by earlier project scripts):
    results/DFT_market_value_recovery_and_sensitivity.csv
    results/DFT_market_value_multi_pack_sensitivity.csv
    results/DFT_expected_value_report.txt

Outputs:
    results/DFT_final_single_pack_comparison.csv
    results/DFT_final_multi_pack_comparison.csv
    results/DFT_final_research_results.txt
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

SINGLE_INPUT = RESULTS / "DFT_market_value_recovery_and_sensitivity.csv"
MULTI_INPUT = RESULTS / "DFT_market_value_multi_pack_sensitivity.csv"

SINGLE_COLUMNS = [
    "finish_assumption",
    "market_price_decline_percent",
    "mean_pack_market_value_usd",
    "median_pack_market_value_usd",
    "mean_recovery_percent",
    "median_recovery_percent",
    "probability_pack_value_at_least_cost_percent",
    "mean_profit_loss_per_pack_usd",
    "break_even_price_decline_percent",
]

MULTI_COLUMNS = [
    "finish_assumption",
    "market_price_decline_percent",
    "packs_opened",
    "total_cost_usd",
    "mean_total_market_value_usd",
    "median_total_market_value_usd",
    "mean_recovery_percent",
    "median_recovery_percent",
    "probability_recovering_at_least_cost_percent",
    "mean_profit_loss_usd",
    "median_profit_loss_usd",
    "profit_loss_5th_percentile_usd",
    "profit_loss_95th_percentile_usd",
    "simulated_sessions",
]


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required input file is missing:\n{path}\n"
            "Run analyze_market_value_sensitivity.py first."
        )


def main():
    require_file(SINGLE_INPUT)
    require_file(MULTI_INPUT)

    single = pd.read_csv(SINGLE_INPUT)
    multi = pd.read_csv(MULTI_INPUT)

    missing_single = [c for c in SINGLE_COLUMNS if c not in single.columns]
    missing_multi = [c for c in MULTI_COLUMNS if c not in multi.columns]
    if missing_single or missing_multi:
        raise ValueError(
            f"Unexpected input columns. Missing single-pack: {missing_single}; "
            f"missing multi-pack: {missing_multi}"
        )

    single = single[SINGLE_COLUMNS].sort_values(
        ["market_price_decline_percent", "finish_assumption"]
    )
    multi = multi[MULTI_COLUMNS].sort_values(
        ["market_price_decline_percent", "finish_assumption", "packs_opened"]
    )

    single_path = RESULTS / "DFT_final_single_pack_comparison.csv"
    multi_path = RESULTS / "DFT_final_multi_pack_comparison.csv"
    report_path = RESULTS / "DFT_final_research_results.txt"

    single.to_csv(single_path, index=False)
    multi.to_csv(multi_path, index=False)

    # Pull the exact baseline rows for concise headline results.
    baseline = single[
        (single["finish_assumption"] == "SPG nonfoil baseline")
        & (single["market_price_decline_percent"] == 0)
    ].iloc[0]
    all_foil = single[
        (single["finish_assumption"] == "SPG all-foil sensitivity")
        & (single["market_price_decline_percent"] == 0)
    ].iloc[0]

    baseline_10 = single[
        (single["finish_assumption"] == "SPG nonfoil baseline")
        & (single["market_price_decline_percent"] == 10)
    ].iloc[0]
    allfoil_10 = single[
        (single["finish_assumption"] == "SPG all-foil sensitivity")
        & (single["market_price_decline_percent"] == 10)
    ].iloc[0]

    with report_path.open("w", encoding="utf-8") as f:
        f.write("AETHERDRIFT PLAY BOOSTER — CONSOLIDATED RESEARCH RESULTS\n")
        f.write("=" * 68 + "\n\n")
        f.write("PROJECT SETTINGS\n")
        f.write("- Product: Aetherdrift Play Booster\n")
        f.write("- Pack price: $4.99\n")
        f.write("- Valuation basis: TCGplayer Market Price\n")
        f.write("- SPG baseline assumption: nonfoil\n")
        f.write("- SPG sensitivity assumption: all foil\n")
        f.write("- Price sensitivity: uniform hypothetical decreases of 0%, 10%, 20%, 30%\n")
        f.write("- No selling fees, shipping, or buylist discounts are deducted\n\n")

        f.write("HEADLINE SINGLE-PACK RESULTS (NO PRICE DECLINE)\n")
        f.write(
            f"SPG nonfoil: mean ${baseline['mean_pack_market_value_usd']:.4f}; "
            f"median ${baseline['median_pack_market_value_usd']:.4f}; "
            f"mean recovery {baseline['mean_recovery_percent']:.2f}%; "
            f"probability pack value >= cost "
            f"{baseline['probability_pack_value_at_least_cost_percent']:.2f}%; "
            f"mean P/L ${baseline['mean_profit_loss_per_pack_usd']:.4f}; "
            f"break-even uniform price decline "
            f"{baseline['break_even_price_decline_percent']:.2f}%.\n"
        )
        f.write(
            f"SPG all-foil: mean ${all_foil['mean_pack_market_value_usd']:.4f}; "
            f"median ${all_foil['median_pack_market_value_usd']:.4f}; "
            f"mean recovery {all_foil['mean_recovery_percent']:.2f}%; "
            f"probability pack value >= cost "
            f"{all_foil['probability_pack_value_at_least_cost_percent']:.2f}%; "
            f"mean P/L ${all_foil['mean_profit_loss_per_pack_usd']:.4f}; "
            f"break-even uniform price decline "
            f"{all_foil['break_even_price_decline_percent']:.2f}%.\n\n"
        )

        f.write("10% MARKET-PRICE DECLINE CHECK\n")
        f.write(
            f"SPG nonfoil mean pack value: ${baseline_10['mean_pack_market_value_usd']:.4f}; "
            f"mean P/L: ${baseline_10['mean_profit_loss_per_pack_usd']:.4f}.\n"
        )
        f.write(
            f"SPG all-foil mean pack value: ${allfoil_10['mean_pack_market_value_usd']:.4f}; "
            f"mean P/L: ${allfoil_10['mean_profit_loss_per_pack_usd']:.4f}.\n\n"
        )

        f.write("SINGLE-PACK COMPARISON TABLE\n")
        f.write(single.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
        f.write("\n\nMULTI-PACK COMPARISON TABLE\n")
        f.write(multi.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

        f.write(
            "\n\nINTERPRETATION AND LIMITATIONS\n"
            "- Expected/mean market value is an average, not a guaranteed pack outcome.\n"
            "- Median pack value describes the middle simulated pack and can be lower "
            "than the mean when rare high-value cards create a right-skewed distribution.\n"
            "- The all-foil SPG case is a sensitivity assumption, not a claim that all "
            "Special Guest cards are actually foil in every relevant pack.\n"
            "- Uniform price declines are hypothetical stress tests, not forecasts.\n"
            "- Multi-pack outcomes are resampled from the existing simulated single-pack "
            "distribution and assume independent pack outcomes.\n"
            "- Results reflect the price snapshot used to build the existing datasets; "
            "they are not live TCGplayer prices.\n"
            "- The probability audit checked internal consistency of the supplied "
            "probability tables; it does not independently establish physical collation.\n"
        )

    print("CONSOLIDATION COMPLETE")
    print("\nHeadline single-pack results (no price decline):")
    print(f"SPG nonfoil mean: ${baseline['mean_pack_market_value_usd']:.4f}")
    print(f"SPG all-foil mean: ${all_foil['mean_pack_market_value_usd']:.4f}")
    print(f"Nonfoil break-even price decline: {baseline['break_even_price_decline_percent']:.2f}%")
    print(f"All-foil break-even price decline: {all_foil['break_even_price_decline_percent']:.2f}%")
    print("\nCreated:")
    for path in [single_path, multi_path, report_path]:
        print(path)


if __name__ == "__main__":
    main()
