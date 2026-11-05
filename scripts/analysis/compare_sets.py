
"""
Compare MTG booster profitability across all eight selected sets.

Run from the project root:

    python3 scripts/analysis/compare_sets.py

Optional pack-price overrides:

    python3 scripts/analysis/compare_sets.py --dft-pack-price 4.99

Inputs:
    results/individual_sets/<SET>/tables/<SET>_final_single_pack_comparison.csv
    results/individual_sets/<SET>/tables/<SET>_final_multi_pack_comparison.csv

Outputs:
    results/comparisons/set_comparison.csv
    results/comparisons/multi_pack_comparison.csv
    results/comparisons/set_comparison_report.txt
    results/comparisons/figures/set_value_vs_cost.png
    results/comparisons/figures/market_price_sensitivity.png
"""

from pathlib import Path
import argparse

import pandas as pd
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SET_CONFIG = {
    "DFT": {
        "name": "Aetherdrift",
        "pack_price": 4.99,
    },
    "FIN": {
        "name": "Final Fantasy",
        "pack_price": 9.34,
    },
    "EOE": {
        "name": "Edge of Eternities",
        "pack_price": 7.60,
    },
    "TDM": {
        "name": "Tarkir: Dragonstorm",
        "pack_price": 6.58,
    },
    "SOS": {
        "name": "Secrets of Strixhaven",
        "pack_price": 4.87,
    },
    "FRA": {
        "name": "Reality Fracture",
        "pack_price": 5.02,
    },
    "ECL": {
        "name": "Lorwyn Eclipsed",
        "pack_price": 4.84,
    },
    "TLA": {
        "name": "Avatar: The Last Airbender",
        "pack_price": 4.87,
    },
}

BASELINE_LABELS = [
    "Standard baseline",
    "SPG nonfoil baseline",
]


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Compare profitability across all eight MTG sets."
    )

    for set_code, config in SET_CONFIG.items():
        parser.add_argument(
            f"--{set_code.lower()}-pack-price",
            type=float,
            default=config["pack_price"],
            help=f"{config['name']} Play Booster price."
        )

    return parser.parse_args()


def find_baseline_label(data, set_code):
    if "finish_assumption" not in data.columns:
        raise ValueError(
            f"{set_code} results are missing finish_assumption."
        )

    available = data["finish_assumption"].dropna().unique().tolist()

    for label in BASELINE_LABELS:
        if label in available:
            return label

    raise ValueError(
        f"No recognized baseline found for {set_code}. "
        f"Available labels: {available}"
    )


def load_set_results(set_code, pack_price):
    set_dir = (
        PROJECT_ROOT
        / "results"
        / "individual_sets"
        / set_code
        / "tables"
    )

    single_path = (
        set_dir
        / f"{set_code}_final_single_pack_comparison.csv"
    )

    multi_path = (
        set_dir
        / f"{set_code}_final_multi_pack_comparison.csv"
    )

    for path in [single_path, multi_path]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required file:\n{path}\n"
                "Run consolidate_research_results.py first."
            )

    single = pd.read_csv(single_path)
    multi = pd.read_csv(multi_path)

    baseline_label = find_baseline_label(single, set_code)

    # Keep only the standard baseline scenario.
    single = single[
        single["finish_assumption"] == baseline_label
    ].copy()

    multi = multi[
        multi["finish_assumption"] == baseline_label
    ].copy()

    if single.empty or multi.empty:
        raise ValueError(
            f"No baseline results available for {set_code}."
        )

    # Attach identifying information.
    single["set_code"] = set_code
    single["set_name"] = SET_CONFIG[set_code]["name"]
    single["pack_price_usd"] = pack_price

    multi["set_code"] = set_code
    multi["set_name"] = SET_CONFIG[set_code]["name"]
    multi["pack_price_usd"] = pack_price

    # Calculate simulated ROI.
    single["simulated_roi_percent"] = (
        single["mean_profit_loss_per_pack_usd"]
        / pack_price
        * 100
    )

    multi["simulated_roi_percent"] = (
        multi["mean_profit_loss_usd"]
        / multi["total_cost_usd"]
        * 100
    )

    return single, multi, baseline_label


def create_value_vs_cost_chart(comparison, figures_dir):
    baseline = comparison[
        comparison["market_price_decline_percent"] == 0
    ].copy()

    fig, ax = plt.subplots(figsize=(14, 7))

    x = range(len(baseline))
    width = 0.35

    ax.bar(
        [i - width / 2 for i in x],
        baseline["mean_pack_market_value_usd"],
        width,
        label="Mean simulated pack value"
    )

    ax.bar(
        [i + width / 2 for i in x],
        baseline["pack_price_usd"],
        width,
        label="Pack cost"
    )

    ax.set_title("Expected Market Value vs. Pack Cost Across Eight Sets")
    ax.set_ylabel("Value (USD)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        baseline["set_code"],
        rotation=0
    )

    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()

    output_path = figures_dir / "set_value_vs_cost.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print(f"Created chart: {output_path}")


def create_sensitivity_chart(comparison, figures_dir):
    fig, ax = plt.subplots(figsize=(13, 7))

    for set_code, group in comparison.groupby("set_code"):
        group = group.sort_values(
            "market_price_decline_percent"
        )

        ax.plot(
            group["market_price_decline_percent"],
            group["mean_pack_market_value_usd"],
            marker="o",
            label=f"{set_code} - {SET_CONFIG[set_code]['name']}"
        )

    ax.set_title("Market-Price Sensitivity Across Eight Sets")
    ax.set_xlabel("Market Price Decline (%)")
    ax.set_ylabel("Mean Simulated Pack Value (USD)")

    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=8
    )

    ax.grid(alpha=0.3)

    fig.tight_layout()

    output_path = figures_dir / "market_price_sensitivity.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Created chart: {output_path}")


def write_report(comparison, multi_comparison, report_path):
    baseline = comparison[
        comparison["market_price_decline_percent"] == 0
    ].copy()

    with report_path.open("w", encoding="utf-8") as f:
        f.write("MTG BOOSTER SET PROFITABILITY COMPARISON\n")
        f.write("=" * 70 + "\n\n")

        f.write("COMPARISON SETTINGS\n")
        f.write("-" * 40 + "\n")
        f.write("- Sets: All eight selected MTG sets\n")
        f.write("- Booster type: Play Boosters\n")
        f.write("- Valuation: TCGplayer Market Price\n")
        f.write("- Scenarios: Standard baseline only\n")
        f.write("- Price declines: 0%, 10%, 20%, and 30%\n")
        f.write(
            "- Results are based on the October 19, 2026 "
            "market-price snapshot.\n"
        )
        f.write(
            "- Eight individual set analyses were consolidated "
            "before comparison.\n\n"
        )

        f.write("PACK PRICES\n")
        f.write("-" * 40 + "\n")

        for _, row in baseline.iterrows():
            f.write(
                f"{row['set_code']} - {row['set_name']}: "
                f"${row['pack_price_usd']:.2f}\n"
            )

        f.write("\n\nSINGLE-PACK COMPARISON\n")
        f.write("-" * 55 + "\n")

        for _, row in baseline.iterrows():
            f.write(f"\n{row['set_name']} ({row['set_code']})\n")
            f.write(f"Pack cost: ${row['pack_price_usd']:.2f}\n")
            f.write(
                f"Mean simulated pack value: "
                f"${row['mean_pack_market_value_usd']:.4f}\n"
            )
            f.write(
                f"Median pack value: "
                f"${row['median_pack_market_value_usd']:.4f}\n"
            )
            f.write(
                f"Mean profit/loss: "
                f"${row['mean_profit_loss_per_pack_usd']:.4f}\n"
            )
            f.write(
                f"Simulated ROI: "
                f"{row['simulated_roi_percent']:.2f}%\n"
            )
            f.write(
                f"Probability of recovering pack cost: "
                f"{row['probability_pack_value_at_least_cost_percent']:.2f}%\n"
            )

        f.write("\n\nMARKET-PRICE SENSITIVITY\n")
        f.write("-" * 45 + "\n")

        for _, row in comparison.iterrows():
            f.write(
                f"{row['set_code']} | "
                f"Price decline: "
                f"{row['market_price_decline_percent']:.0f}% | "
                f"Mean value: "
                f"${row['mean_pack_market_value_usd']:.3f} | "
                f"Mean P/L: "
                f"${row['mean_profit_loss_per_pack_usd']:.3f}\n"
            )

        f.write("\n\nMULTI-PACK COMPARISON\n")
        f.write("-" * 45 + "\n")

        for _, row in multi_comparison.iterrows():
            f.write(
                f"{row['set_code']} | "
                f"{row['packs_opened']} packs | "
                f"Price decline: "
                f"{row['market_price_decline_percent']:.0f}% | "
                f"Mean P/L: "
                f"${row['mean_profit_loss_usd']:.2f} | "
                f"Recovery probability: "
                f"{row['probability_recovering_at_least_cost_percent']:.2f}%\n"
            )

        f.write("\n\nINTERPRETATION AND LIMITATIONS\n")
        f.write("-" * 45 + "\n")
        f.write(
            "- Mean simulated pack value represents an average "
            "across simulated openings, not a guaranteed outcome.\n"
        )
        f.write(
            "- The standard baseline is used for all sets to "
            "maintain a consistent comparison.\n"
        )
        f.write(
            "- Optional Special Guest all-foil sensitivity "
            "scenarios are excluded from the standard comparison.\n"
        )
        f.write(
            "- TLA does not have a Special Guest slot in this analysis.\n"
        )
        f.write(
            "- Market prices are estimates and do not guarantee "
            "resale proceeds.\n"
        )
        f.write(
            "- Selling fees, shipping, and buylist discounts "
            "are not deducted.\n"
        )
        f.write(
            "- Multi-pack simulations assume independent pack "
            "outcomes.\n"
        )
        f.write(
            "- Market-price declines are hypothetical stress tests, "
            "not forecasts.\n"
        )


def main():
    args = parse_arguments()

    prices = {
        set_code: getattr(
            args,
            f"{set_code.lower()}_pack_price"
        )
        for set_code in SET_CONFIG
    }

    for set_code, price in prices.items():
        if price <= 0:
            raise ValueError(
                f"{set_code} pack price must be greater than zero."
            )

    comparisons_dir = PROJECT_ROOT / "results" / "comparisons"
    figures_dir = comparisons_dir / "figures"

    comparisons_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print("Starting comparison across all eight MTG sets...")

    single_results = []
    multi_results = []

    for set_code, pack_price in prices.items():
        print(f"\nLoading {set_code} results...")

        single, multi, baseline_label = load_set_results(
            set_code,
            pack_price
        )

        print(f"Baseline detected: {baseline_label}")
        print(f"Pack price: ${pack_price:.2f}")

        single_results.append(single)
        multi_results.append(multi)

    comparison = pd.concat(
        single_results,
        ignore_index=True
    )

    multi_comparison = pd.concat(
        multi_results,
        ignore_index=True
    )

    # Preserve the selected set order.
    set_order = list(SET_CONFIG.keys())

    comparison["set_code"] = pd.Categorical(
        comparison["set_code"],
        categories=set_order,
        ordered=True
    )

    multi_comparison["set_code"] = pd.Categorical(
        multi_comparison["set_code"],
        categories=set_order,
        ordered=True
    )

    comparison = comparison.sort_values(
        ["set_code", "market_price_decline_percent"]
    )

    multi_comparison = multi_comparison.sort_values(
        [
            "set_code",
            "market_price_decline_percent",
            "packs_opened",
        ]
    )

    # Convert set_code back to ordinary strings for CSV output.
    comparison["set_code"] = comparison["set_code"].astype(str)
    multi_comparison["set_code"] = (
        multi_comparison["set_code"].astype(str)
    )

    # Save comparison tables.
    comparison_path = comparisons_dir / "set_comparison.csv"
    multi_path = comparisons_dir / "multi_pack_comparison.csv"

    comparison.to_csv(comparison_path, index=False)
    multi_comparison.to_csv(multi_path, index=False)

    print("\nCreated comparison tables.")

    # Generate charts.
    create_value_vs_cost_chart(comparison, figures_dir)
    create_sensitivity_chart(comparison, figures_dir)

    # Generate report.
    report_path = (
        comparisons_dir
        / "set_comparison_report.txt"
    )

    write_report(
        comparison,
        multi_comparison,
        report_path
    )

    print(f"\nCreated report: {report_path}")

    # Display headline comparison.
    baseline = comparison[
        comparison["market_price_decline_percent"] == 0
    ].copy()

    print("\nHEADLINE COMPARISON")
    print("=" * 75)

    for _, row in baseline.iterrows():
        print(f"\n{row['set_name']} ({row['set_code']})")
        print(f"Pack cost: ${row['pack_price_usd']:.2f}")
        print(
            f"Mean pack value: "
            f"${row['mean_pack_market_value_usd']:.4f}"
        )
        print(
            f"Mean profit/loss: "
            f"${row['mean_profit_loss_per_pack_usd']:.4f}"
        )
        print(
            f"Simulated ROI: "
            f"{row['simulated_roi_percent']:.2f}%"
        )
        print(
            f"Recovery probability: "
            f"{row['probability_pack_value_at_least_cost_percent']:.2f}%"
        )

    print("\nCOMPARISON COMPLETE")

    print("\nCreated files:")
    for path in [
        comparison_path,
        multi_path,
        report_path,
        figures_dir / "set_value_vs_cost.png",
        figures_dir / "market_price_sensitivity.png",
    ]:
        print(path)


if __name__ == "__main__":
    main()
