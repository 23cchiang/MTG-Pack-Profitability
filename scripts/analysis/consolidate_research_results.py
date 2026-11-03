
"""
Consolidate MTG booster profitability research results.

Run from the project root:

    python3 scripts/analysis/consolidate_research_results.py DFT play --pack-price 4.99
    python3 scripts/analysis/consolidate_research_results.py FIN play --pack-price 9.34

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

BASELINE_LABELS = [
    "Standard baseline",
    "SPG nonfoil baseline",
]

SENSITIVITY_LABELS = [
    "Special Guest all-foil sensitivity",
    "SPG all-foil sensitivity",
]

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
        help="MTG set code, such as DFT or FIN"
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
        help="Price per booster pack"
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


def find_available_label(data, possible_labels):
    for label in possible_labels:
        if label in data["finish_assumption"].values:
            return label

    return None


def write_scenario_summary(f, label, baseline, decline_10):
    f.write(
        f"{label}: mean "
        f"${baseline['mean_pack_market_value_usd']:.4f}; "
        f"median "
        f"${baseline['median_pack_market_value_usd']:.4f}; "
        f"mean recovery "
        f"{baseline['mean_recovery_percent']:.2f}%; "
        f"probability pack value >= cost "
        f"{baseline['probability_pack_value_at_least_cost_percent']:.2f}%; "
        f"mean P/L "
        f"${baseline['mean_profit_loss_per_pack_usd']:.4f}; "
        f"break-even price decline "
        f"{baseline['break_even_price_decline_percent']:.2f}%.\n"
    )

    if decline_10 is not None:
        f.write(
            f"  At a 10% price decline: mean value "
            f"${decline_10['mean_pack_market_value_usd']:.4f}; "
            f"mean P/L "
            f"${decline_10['mean_profit_loss_per_pack_usd']:.4f}.\n"
        )


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

    require_file(single_input)
    require_file(multi_input)

    single = pd.read_csv(single_input)
    multi = pd.read_csv(multi_input)

    require_columns(single, SINGLE_COLUMNS, single_input.name)
    require_columns(multi, MULTI_COLUMNS, multi_input.name)

    # Detect which scenarios are available.
    baseline_label = find_available_label(
        single,
        BASELINE_LABELS
    )

    if baseline_label is None:
        raise ValueError(
            "No recognized baseline scenario was found. "
            f"Available labels: {single['finish_assumption'].unique().tolist()}"
        )

    sensitivity_label = find_available_label(
        single,
        SENSITIVITY_LABELS
    )

    print(f"\nBaseline scenario: {baseline_label}")

    if sensitivity_label:
        print(f"Additional scenario: {sensitivity_label}")
    else:
        print("No additional foil sensitivity scenario found.")

    # Verify that the baseline has the expected rows.
    baseline = get_result_row(single, baseline_label, 0)

    baseline_10 = get_result_row(single, baseline_label, 10)

    # Retrieve the optional sensitivity scenario.
    all_foil = None
    all_foil_10 = None

    if sensitivity_label:
        all_foil = get_result_row(
            single,
            sensitivity_label,
            0
        )

        all_foil_10 = get_result_row(
            single,
            sensitivity_label,
            10
        )

    # Add identifying information.
    single["booster_type"] = booster_type
    single["set_code"] = set_code

    multi["booster_type"] = booster_type
    multi["set_code"] = set_code

    # Sort results.
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

    # Save comparison tables.
    single.to_csv(single_path, index=False)
    multi.to_csv(multi_path, index=False)

    # Generate consolidated report.
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
        f.write(f"- Baseline assumption: {baseline_label}\n")

        if sensitivity_label:
            f.write(
                f"- Additional sensitivity assumption: "
                f"{sensitivity_label}\n"
            )

        f.write(
            "- Price sensitivity: hypothetical decreases "
            "of 0%, 10%, 20%, and 30%\n"
        )

        f.write(
            "- No selling fees, shipping, or buylist discounts "
            "are deducted\n\n"
        )

        f.write("HEADLINE SINGLE-PACK RESULTS (NO PRICE DECLINE)\n")
        f.write("-" * 50 + "\n")

        write_scenario_summary(
            f,
            baseline_label,
            baseline,
            baseline_10
        )

        if all_foil is not None:
            write_scenario_summary(
                f,
                sensitivity_label,
                all_foil,
                all_foil_10
            )

        f.write("\nBREAK-EVEN INTERPRETATION\n")
        f.write("-" * 40 + "\n")
        f.write(
            "A break-even price decline of 0% can mean the expected "
            "pack value is already below the pack cost. It does not "
            "necessarily indicate that the pack is breaking even.\n"
        )

        f.write("\nSINGLE-PACK COMPARISON TABLE\n")
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
        )

        if sensitivity_label:
            f.write(
                "- The all-foil Special Guest case is a sensitivity "
                "assumption, not a claim that all Special Guest cards "
                "are actually foil in every relevant pack.\n"
            )

        f.write(
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

    # Display completion summary.
    print("\nCONSOLIDATION COMPLETE")

    print("\nHeadline single-pack results:")
    print(
        f"{baseline_label} mean: "
        f"${baseline['mean_pack_market_value_usd']:.4f}"
    )

    print(
        f"{baseline_label} expected P/L: "
        f"${baseline['mean_profit_loss_per_pack_usd']:.4f}"
    )

    if all_foil is not None:
        print(
            f"{sensitivity_label} mean: "
            f"${all_foil['mean_pack_market_value_usd']:.4f}"
        )

    print("\nCreated:")
    for path in [single_path, multi_path, report_path]:
        print(path)


if __name__ == "__main__":
    main()
