
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# Project paths and defaults
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULTS_ROOT = PROJECT_ROOT / "results" / "individual_sets"

DEFAULT_PACK_PRICE = 4.99
PACK_COUNTS = [10, 20, 36, 100]
PRICE_DECLINES = [0.00, 0.10, 0.20, 0.30]

SESSIONS = 50_000
RANDOM_SEED = 4212026

VALUE_COLUMNS = {
    "SPG nonfoil baseline": "pack_value_spg_nonfoil_usd",
    "SPG all-foil sensitivity": "pack_value_spg_all_foil_usd",
}


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Analyze MTG booster market-value sensitivity."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTG set code, such as DFT."
    )

    parser.add_argument(
        "booster_type",
        type=str,
        help="Booster type, such as play."
    )

    parser.add_argument(
        "--pack-price",
        type=float,
        default=DEFAULT_PACK_PRICE,
        help="Pack purchase price. Defaults to 4.99."
    )

    return parser.parse_args()


# --------------------------------------------------
# Main analysis
# --------------------------------------------------

def main():

    args = parse_arguments()

    set_code = args.set_code.upper()
    booster_type = args.booster_type.lower()
    pack_price = args.pack_price

    if pack_price <= 0:
        raise ValueError(
            "Pack price must be greater than zero."
        )

    # --------------------------------------------------
    # Paths
    # --------------------------------------------------

    set_results_dir = RESULTS_ROOT / set_code

    tables_dir = set_results_dir / "tables"
    figures_dir = set_results_dir / "figures"
    reports_dir = set_results_dir / "reports"

    for directory in [
        tables_dir,
        figures_dir,
        reports_dir
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    input_file = (
        tables_dir
        / f"{set_code}_monte_carlo_pack_values.csv"
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Monte Carlo input file not found: {input_file}\n"
            "Run simulate_pack_profitability.py first."
        )

    # --------------------------------------------------
    # Load simulated pack values
    # --------------------------------------------------

    df = pd.read_csv(input_file)

    missing = [
        column
        for column in VALUE_COLUMNS.values()
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns in Monte Carlo CSV: {missing}"
        )

    rng = np.random.default_rng(RANDOM_SEED)

    single_pack_rows = []
    multi_pack_rows = []

    print(
        f"Analyzing {set_code} {booster_type.title()} "
        "Booster market-value sensitivity..."
    )

    print(f"Loaded {len(df):,} simulated packs.")
    print(f"Pack cost: ${pack_price:.2f}")
    print(f"Sessions per multi-pack scenario: {SESSIONS:,}")

    # --------------------------------------------------
    # Price sensitivity calculations
    # --------------------------------------------------

    for finish_assumption, column in VALUE_COLUMNS.items():

        pack_values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna().to_numpy(dtype=float)

        if pack_values.size == 0:
            print(
                f"Skipping {finish_assumption}: "
                "no values found."
            )
            continue

        if not np.isfinite(pack_values).all():
            raise ValueError(
                f"Non-finite pack values found in {column}."
            )

        original_mean = float(np.mean(pack_values))

        break_even_decline = max(
            0.0,
            1.0 - pack_price / original_mean
        )

        for decline in PRICE_DECLINES:

            adjusted_values = pack_values * (1.0 - decline)

            mean_value = float(np.mean(adjusted_values))
            median_value = float(np.median(adjusted_values))

            single_pack_rows.append({
                "set_code": set_code,
                "booster_type": booster_type,
                "finish_assumption": finish_assumption,
                "market_price_decline_percent": decline * 100,
                "mean_pack_market_value_usd": mean_value,
                "median_pack_market_value_usd": median_value,
                "mean_recovery_percent": (
                    mean_value / pack_price * 100
                ),
                "median_recovery_percent": (
                    median_value / pack_price * 100
                ),
                "probability_pack_value_at_least_cost_percent": (
                    np.mean(adjusted_values >= pack_price) * 100
                ),
                "mean_profit_loss_per_pack_usd": (
                    mean_value - pack_price
                ),
                "break_even_price_decline_percent": (
                    break_even_decline * 100
                )
            })

            # --------------------------------------------------
            # Multi-pack sensitivity
            # --------------------------------------------------

            for number_of_packs in PACK_COUNTS:

                draws = rng.choice(
                    adjusted_values,
                    size=(SESSIONS, number_of_packs),
                    replace=True
                )

                total_market_value = draws.sum(axis=1)

                total_cost = number_of_packs * pack_price

                profit_loss = total_market_value - total_cost

                recovery_percent = (
                    total_market_value / total_cost * 100
                )

                multi_pack_rows.append({
                    "set_code": set_code,
                    "booster_type": booster_type,
                    "finish_assumption": finish_assumption,
                    "market_price_decline_percent": decline * 100,
                    "packs_opened": number_of_packs,
                    "total_cost_usd": total_cost,
                    "mean_total_market_value_usd": (
                        np.mean(total_market_value)
                    ),
                    "median_total_market_value_usd": (
                        np.median(total_market_value)
                    ),
                    "mean_recovery_percent": (
                        np.mean(recovery_percent)
                    ),
                    "median_recovery_percent": (
                        np.median(recovery_percent)
                    ),
                    "probability_recovering_at_least_cost_percent": (
                        np.mean(total_market_value >= total_cost) * 100
                    ),
                    "mean_profit_loss_usd": (
                        np.mean(profit_loss)
                    ),
                    "median_profit_loss_usd": (
                        np.median(profit_loss)
                    ),
                    "profit_loss_5th_percentile_usd": (
                        np.percentile(profit_loss, 5)
                    ),
                    "profit_loss_95th_percentile_usd": (
                        np.percentile(profit_loss, 95)
                    ),
                    "simulated_sessions": SESSIONS
                })

    # --------------------------------------------------
    # Create result DataFrames
    # --------------------------------------------------

    single_df = pd.DataFrame(single_pack_rows)
    multi_df = pd.DataFrame(multi_pack_rows)

    if single_df.empty or multi_df.empty:
        raise ValueError(
            "No sensitivity results were generated."
        )

    # --------------------------------------------------
    # Output paths
    # --------------------------------------------------

    single_path = (
        tables_dir
        / f"{set_code}_market_value_recovery_and_sensitivity.csv"
    )

    multi_path = (
        tables_dir
        / f"{set_code}_market_value_multi_pack_sensitivity.csv"
    )

    report_path = (
        reports_dir
        / f"{set_code}_market_value_sensitivity_report.txt"
    )

    chart_path = (
        figures_dir
        / f"{set_code}_market_value_recovery_sensitivity.png"
    )

    # --------------------------------------------------
    # Save tables
    # --------------------------------------------------

    single_df.to_csv(single_path, index=False)
    multi_df.to_csv(multi_path, index=False)

    # --------------------------------------------------
    # Create chart
    # --------------------------------------------------

    fig, ax = plt.subplots(figsize=(9, 5.5))

    for finish_assumption in VALUE_COLUMNS:

        subset = single_df[
            single_df["finish_assumption"] == finish_assumption
        ]

        if subset.empty:
            continue

        ax.plot(
            subset["market_price_decline_percent"],
            subset["mean_recovery_percent"],
            marker="o",
            label=finish_assumption
        )

    ax.axhline(
        100,
        linestyle="--",
        linewidth=1,
        label="100% recovery (break-even)"
    )

    ax.set_title(
        f"{set_code} {booster_type.title()} Booster: "
        "Market-Value Recovery"
    )

    ax.set_xlabel(
        "Hypothetical decrease in TCGplayer Market Prices (%)"
    )

    ax.set_ylabel(
        "Mean card market value recovered (%)"
    )

    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    fig.savefig(chart_path, dpi=180)
    plt.close(fig)

    # --------------------------------------------------
    # Create report
    # --------------------------------------------------

    report_lines = [
        (
            f"{set_code} {booster_type.upper()} BOOSTER "
            "— MARKET-VALUE RECOVERY ANALYSIS"
        ),
        "=" * 65,
        f"Pack cost: ${pack_price:.2f}",
        (
            "Valuation: TCGplayer Market Price from "
            "the existing price snapshot."
        ),
        (
            "Price shocks are hypothetical uniform declines "
            "in card market values."
        ),
        "No seller fees, shipping, or buylist discounts are deducted.",
        f"Source simulated packs: {len(df):,}",
        f"Sessions per multi-pack scenario: {SESSIONS:,}",
        "",
        "SINGLE-PACK RECOVERY AND PRICE SENSITIVITY",
        single_df.to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}"
        ),
        "",
        "MULTI-PACK SESSION RESULTS",
        multi_df.to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}"
        ),
        "",
        "INTERPRETATION NOTES",
        "- Recovery rate = card market value divided by pack cost.",
        "- Above 100% means card market value exceeds pack cost.",
        "- Price declines are hypothetical sensitivity tests, not forecasts.",
        (
            "- Multi-pack results are resampled from existing simulated "
            "pack values; they are not guaranteed returns."
        )
    ]

    report_path.write_text(
        "\n".join(report_lines),
        encoding="utf-8"
    )

    # --------------------------------------------------
    # Terminal output
    # --------------------------------------------------

    print("\nSINGLE-PACK RESULTS — SPG NONFOIL BASELINE")

    print(
        single_df[
            single_df["finish_assumption"] == "SPG nonfoil baseline"
        ].to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}"
        )
    )

    print("\nMULTI-PACK RESULTS — SPG NONFOIL BASELINE")

    print(
        multi_df[
            multi_df["finish_assumption"] == "SPG nonfoil baseline"
        ].to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}"
        )
    )

    print("\nCreated these files:")

    for output in [
        single_path,
        multi_path,
        report_path,
        chart_path
    ]:
        print(output)


if __name__ == "__main__":
    main()
