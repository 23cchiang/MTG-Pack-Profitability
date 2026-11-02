"""
Market-value recovery and price-sensitivity analysis for Aetherdrift Play Boosters.

Place this file in the MTG-Pack-Profitability project root, beside
simulate_pack_profitability.py, then run:
    python3 analyze_market_value_sensitivity.py

Uses existing Monte Carlo pack values and applies hypothetical uniform
declines to card market values. It does not model selling fees or proceeds.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "results" / "DFT_monte_carlo_pack_values.csv"
RESULTS = ROOT / "results"

PACK_PRICE = 4.99
PACK_COUNTS = [10, 20, 36, 100]
PRICE_DECLINES = [0.00, 0.10, 0.20, 0.30]
SESSIONS = 50_000
RANDOM_SEED = 4212026

VALUE_COLUMNS = {
    "SPG nonfoil baseline": "pack_value_spg_nonfoil_usd",
    "SPG all-foil sensitivity": "pack_value_spg_all_foil_usd",
}


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT}\n"
            "Make sure you run this script from inside your project folder "
            "and that results/DFT_monte_carlo_pack_values.csv exists."
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT)

    missing = [column for column in VALUE_COLUMNS.values() if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Monte Carlo CSV: {missing}")

    rng = np.random.default_rng(RANDOM_SEED)
    single_pack_rows = []
    multi_pack_rows = []

    print(f"Loaded {len(df):,} simulated packs from:")
    print(INPUT)
    print(f"\nPack cost: ${PACK_PRICE:.2f}")
    print(f"Simulated sessions per multi-pack scenario: {SESSIONS:,}")

    for finish_assumption, column in VALUE_COLUMNS.items():
        pack_values = df[column].dropna().to_numpy(dtype=float)
        if pack_values.size == 0:
            print(f"Skipping {finish_assumption}: no values found.")
            continue

        original_mean = float(np.mean(pack_values))
        break_even_decline = max(0.0, 1.0 - PACK_PRICE / original_mean)

        for decline in PRICE_DECLINES:
            adjusted_values = pack_values * (1.0 - decline)
            mean_value = float(np.mean(adjusted_values))
            median_value = float(np.median(adjusted_values))

            single_pack_rows.append({
                "finish_assumption": finish_assumption,
                "market_price_decline_percent": decline * 100,
                "mean_pack_market_value_usd": mean_value,
                "median_pack_market_value_usd": median_value,
                "mean_recovery_percent": mean_value / PACK_PRICE * 100,
                "median_recovery_percent": median_value / PACK_PRICE * 100,
                "probability_pack_value_at_least_cost_percent":
                    float(np.mean(adjusted_values >= PACK_PRICE) * 100),
                "mean_profit_loss_per_pack_usd": mean_value - PACK_PRICE,
                "break_even_price_decline_percent": break_even_decline * 100,
            })

            for number_of_packs in PACK_COUNTS:
                draws = rng.choice(
                    adjusted_values,
                    size=(SESSIONS, number_of_packs),
                    replace=True,
                )
                total_market_value = draws.sum(axis=1)
                total_cost = number_of_packs * PACK_PRICE
                profit_loss = total_market_value - total_cost
                recovery_percent = total_market_value / total_cost * 100

                multi_pack_rows.append({
                    "finish_assumption": finish_assumption,
                    "market_price_decline_percent": decline * 100,
                    "packs_opened": number_of_packs,
                    "total_cost_usd": total_cost,
                    "mean_total_market_value_usd": float(np.mean(total_market_value)),
                    "median_total_market_value_usd": float(np.median(total_market_value)),
                    "mean_recovery_percent": float(np.mean(recovery_percent)),
                    "median_recovery_percent": float(np.median(recovery_percent)),
                    "probability_recovering_at_least_cost_percent":
                        float(np.mean(total_market_value >= total_cost) * 100),
                    "mean_profit_loss_usd": float(np.mean(profit_loss)),
                    "median_profit_loss_usd": float(np.median(profit_loss)),
                    "profit_loss_5th_percentile_usd":
                        float(np.percentile(profit_loss, 5)),
                    "profit_loss_95th_percentile_usd":
                        float(np.percentile(profit_loss, 95)),
                    "simulated_sessions": SESSIONS,
                })

    single_df = pd.DataFrame(single_pack_rows)
    multi_df = pd.DataFrame(multi_pack_rows)

    single_path = RESULTS / "DFT_market_value_recovery_and_sensitivity.csv"
    multi_path = RESULTS / "DFT_market_value_multi_pack_sensitivity.csv"
    report_path = RESULTS / "DFT_market_value_sensitivity_report.txt"
    chart_path = RESULTS / "DFT_market_value_recovery_sensitivity.png"

    single_df.to_csv(single_path, index=False)
    multi_df.to_csv(multi_path, index=False)

    # Chart: mean recovery percentage across price-decline scenarios.
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for finish_assumption in VALUE_COLUMNS:
        subset = single_df[single_df["finish_assumption"] == finish_assumption]
        ax.plot(
            subset["market_price_decline_percent"],
            subset["mean_recovery_percent"],
            marker="o",
            label=finish_assumption,
        )
    ax.axhline(100, linestyle="--", linewidth=1, label="100% recovery (break-even)")
    ax.set_title("Aetherdrift Play Booster: Market-Value Recovery")
    ax.set_xlabel("Hypothetical decrease in TCGplayer Market Prices (%)")
    ax.set_ylabel("Mean card market value recovered (%)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(chart_path, dpi=180)
    plt.close(fig)

    with report_path.open("w", encoding="utf-8") as report:
        report.write("AETHERDRIFT PLAY BOOSTER — MARKET-VALUE RECOVERY ANALYSIS\n")
        report.write("=" * 65 + "\n\n")
        report.write(f"Pack cost: ${PACK_PRICE:.2f}\n")
        report.write("Valuation: TCGplayer Market Price from the existing price snapshot.\n")
        report.write("Price shocks are hypothetical uniform declines in card market values.\n")
        report.write("No seller fees, shipping, or buylist discounts are deducted.\n")
        report.write(f"Source simulated packs: {len(df):,}\n")
        report.write(f"Sessions per multi-pack scenario: {SESSIONS:,}\n\n")
        report.write("SINGLE-PACK RECOVERY AND PRICE SENSITIVITY\n")
        report.write(single_df.to_string(
            index=False, float_format=lambda value: f"{value:.3f}"
        ))
        report.write("\n\nMULTI-PACK SESSION RESULTS\n")
        report.write(multi_df.to_string(
            index=False, float_format=lambda value: f"{value:.3f}"
        ))
        report.write(
            "\n\nINTERPRETATION NOTES\n"
            "- Recovery rate = card market value divided by pack cost.\n"
            "- Above 100% means the card market value exceeds the pack cost.\n"
            "- Price declines are hypothetical sensitivity tests, not forecasts.\n"
            "- Multi-pack results are resampled from existing simulated pack values; "
            "they are not guaranteed returns.\n"
        )

    print("\nSINGLE-PACK RESULTS — SPG NONFOIL BASELINE")
    print(single_df[single_df["finish_assumption"] == "SPG nonfoil baseline"].to_string(
        index=False, float_format=lambda value: f"{value:.3f}"
    ))
    print("\nMULTI-PACK RESULTS — SPG NONFOIL BASELINE")
    print(multi_df[multi_df["finish_assumption"] == "SPG nonfoil baseline"].to_string(
        index=False, float_format=lambda value: f"{value:.3f}"
    ))
    print("\nCreated these files:")
    for output in [single_path, multi_path, report_path, chart_path]:
        print(output)


if __name__ == "__main__":
    main()
