
"""
Consolidate MTG booster profitability research results.

Run from the project root:

    python3 scripts/analysis/consolidate_research_results.py DFT play --pack-price 4.99

Inputs:
    results/individual_sets/{SET}/tables/{SET}_market_value_recovery_and_sensitivity.csv
    results/individual_sets/{SET}/tables/{SET}_market_value_multi_pack_sensitivity.csv

Outputs:
    results/individual_sets/{SET}/tables/{SET}_final_single_pack_comparison.csv
    results/individual_sets/{SET}/tables/{SET}_final_multi_pack_comparison.csv
    results/individual_sets/{SET}/reports/{SET}_final_research_results.txt
"""

from pathlib import Path
import argparse
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Consolidate MTG booster profitability research results."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTG set code, such as DFT"
    )

    parser.add_argument(
        "booster_type",
        type=str,
        help="Booster type, such as play or collector"
    )

    parser.add_argument(
        "--pack-price",
        type=float,
        default=4.99,
        help="Price per booster pack (default: 4.99)"
    )

    return parser.parse_args()


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required input file is missing:\n{path}\n\n"
            "Run analyze_market_value_sensitivity.py first."
        )


def require_columns(data, required_columns, filename):
    missing = [
        column for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"{filename} is missing required columns: {missing}"
        )


def get_result_row(data, finish_assumption, decline):
    matching_rows = data[
        (data["finish_assumption"] == finish_assumption)
        & (data["market_price_decline_percent"] == decline)
    ]

    if matching_rows.empty:
        raise ValueError(
            f"Could not find a result for '{finish_assumption}' "
            f"at a {decline}% market-price decline."
        )

    return matching_rows.iloc[0]


def main():
    args = parse_arguments()

    set_code = args.set_code.upper()
    booster_type = args.booster_type.lower()
    pack_price = args.pack_price

    if pack_price <= 0:
        raise ValueError("Pack price must be greater than zero.")

    results_dir = (
        PROJECT_ROOT
        / "results"
        / "individual_sets"
        / set_code
    )

    tables_dir = results_dir / "tables"
    reports_dir = results_dir / "reports"

    single_input = (
        tables_dir
        / f"{set_code}_market_value_recovery_and_sensitivity.csv"
    )

    multi_input = (
        tables_dir
        / f"{set_code}_market_value_multi_pack_sensitivity.csv"
    )

    single_path = (
        tables_dir
        / f"{set_code}_final_single_pack_comparison.csv"
    )

    multi_path = (
        tables_dir
        / f"{set_code}_final_multi_pack_comparison.csv"
    )

    report_path = (
        reports_dir
        / f"{set_code}_final_research_results.txt"
    )

    tables_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Consolidating {set_code} "
        f"{booster_type.title()} Booster research results..."
    )

    # Check that the required input files exist.
    require_file(single_input)
    require_file(multi_input)

    # Load the sensitivity results.
    single = pd.read_csv(single_input)
    multi = pd.read_csv(multi_input)

    require_columns(single, SINGLE_COLUMNS, single_input.name)
    require_columns(multi, MULTI_COLUMNS, multi_input.name)

    # Add or update identifying information in the final comparison tables.
    single["booster_type"] = booster_type
    single["set_code"] = set_code

    multi["booster_type"] = booster_type
    multi["set_code"] = set_code

    # Sort results for easier comparison.
    single = single.sort_values(
        ["market_price_decline_percent", "finish_assumption"]
    )

    multi = multi.sort_values(
        [
            "market_price_decline_percent",
            "finish_assumption",
            "packs_opened",
        ]
    )

    # Identify the baseline and all-foil results.
    baseline = get_result_row(
        single,
        "SPG nonfoil baseline",
        0
    )

    all_foil = get_result_row(
        single,
        "SPG all-foil sensitivity",
        0
    )

    baseline_10 = get_result_row(
        single,
        "SPG nonfoil baseline",
        10
    )

    allfoil_10 = get_result_row(
        single,
        "SPG all-foil sensitivity",
        10
    )

    # Save final comparison tables.
    single.to_csv(single_path, index=False)
    multi.to_csv(multi_path, index=False)

    # Generate the consolidated research report.
    with report_path.open("w", encoding="utf-8") as f:

        f.write(
            f"{set_code} {booster_type.upper()} BOOSTER "
            "— CONSOLIDATED RESEARCH RESULTS\n"
        )
        f.write("=" * 72 + "\n\n")

        f.write("PROJECT SETTINGS\n")
        f.write("-" * 30 + "\n")
        f.write(f"- Set code: {set_code}\n")
        f.write(f"- Booster type: {booster_type}\n")
        f.write(f"- Pack price: ${pack_price:.2f}\n")
        f.write("- Valuation basis: TCGplayer Market Price\n")
        f.write("- SPG baseline assumption: nonfoil\n")
        f.write("- SPG sensitivity assumption: all foil\n")
        f.write(
            "- Price sensitivity: uniform hypothetical decreases "
            "of 0%, 10%, 20%, and 30%\n"
        )
        f.write(
            "- No selling fees, shipping, or buylist discounts "
            "are deducted\n\n"
        )

        f.write("HEADLINE SINGLE-PACK RESULTS (NO PRICE DECLINE)\n")
        f.write("-" * 50 + "\n")

        f.write(
            f"SPG nonfoil: mean "
            f"${baseline['mean_pack_market_value_usd']:.4f}; "
            f"median "
            f"${baseline['median_pack_market_value_usd']:.4f}; "
            f"mean recovery "
            f"{baseline['mean_recovery_percent']:.2f}%; "
            f"probability pack value >= cost "
            f"{baseline['probability_pack_value_at_least_cost_percent']:.2f}%; "
            f"mean P/L "
            f"${baseline['mean_profit_loss_per_pack_usd']:.4f}; "
            f"break-even uniform price decline "
            f"{baseline['break_even_price_decline_percent']:.2f}%.\n"
        )

        f.write(
            f"SPG all-foil: mean "
            f"${all_foil['mean_pack_market_value_usd']:.4f}; "
            f"median "
            f"${all_foil['median_pack_market_value_usd']:.4f}; "
            f"mean recovery "
            f"{all_foil['mean_recovery_percent']:.2f}%; "
            f"probability pack value >= cost "
            f"{all_foil['probability_pack_value_at_least_cost_percent']:.2f}%; "
            f"mean P/L "
            f"${all_foil['mean_profit_loss_per_pack_usd']:.4f}; "
            f"break-even uniform price decline "
            f"{all_foil['break_even_price_decline_percent']:.2f}%.\n\n"
        )

        f.write("10% MARKET-PRICE DECLINE CHECK\n")
        f.write("-" * 40 + "\n")

        f.write(
            f"SPG nonfoil mean pack value: "
            f"${baseline_10['mean_pack_market_value_usd']:.4f}; "
            f"mean P/L: "
            f"${baseline_10['mean_profit_loss_per_pack_usd']:.4f}.\n"
        )

        f.write(
            f"SPG all-foil mean pack value: "
            f"${allfoil_10['mean_pack_market_value_usd']:.4f}; "
            f"mean P/L: "
            f"${allfoil_10['mean_profit_loss_per_pack_usd']:.4f}.\n\n"
        )

        f.write("SINGLE-PACK COMPARISON TABLE\n")
        f.write("-" * 40 + "\n")
        f.write(
            single.to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}"
            )
        )

        f.write("\n\nMULTI-PACK COMPARISON TABLE\n")
        f.write("-" * 40 + "\n")
        f.write(
            multi.to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}"
            )
        )

        f.write(
            "\n\nINTERPRETATION AND LIMITATIONS\n"
            "- Expected/mean market value is an average, not a "
            "guaranteed pack outcome.\n"
            "- Median pack value describes the middle simulated pack "
            "and can be lower than the mean when rare high-value cards "
            "create a right-skewed distribution.\n"
            "- The all-foil SPG case is a sensitivity assumption, "
            "not a claim that all Special Guest cards are actually foil "
            "in every relevant pack.\n"
            "- Uniform price declines are hypothetical stress tests, "
            "not forecasts.\n"
            "- Multi-pack outcomes are resampled from the existing "
            "simulated single-pack distribution and assume independent "
            "pack outcomes.\n"
            "- Results reflect the price snapshot used to build the "
            "existing datasets; they are not live TCGplayer prices.\n"
            "- The probability audit checked internal consistency of "
            "the supplied probability tables; it does not independently "
            "establish physical collation.\n"
        )

    # Display a concise completion summary.
    print("\nCONSOLIDATION COMPLETE")

    print("\nHeadline single-pack results (no price decline):")
    print(
        f"SPG nonfoil mean: "
        f"${baseline['mean_pack_market_value_usd']:.4f}"
    )
    print(
        f"SPG all-foil mean: "
        f"${all_foil['mean_pack_market_value_usd']:.4f}"
    )
    print(
        f"Nonfoil break-even price decline: "
        f"{baseline['break_even_price_decline_percent']:.2f}%"
    )
    print(
        f"All-foil break-even price decline: "
        f"{all_foil['break_even_price_decline_percent']:.2f}%"
    )

    print("\nCreated:")
    for path in [single_path, multi_path, report_path]:
        print(path)


if __name__ == "__main__":
    main()
