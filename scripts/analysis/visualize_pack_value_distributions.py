
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RESULTS = ROOT / "results" / "individual_sets"
FIGURES = ROOT / "results" / "comparisons" / "figures"

FIGURES.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# LOAD SIMULATION DATA
# --------------------------------------------------

dft_path = RESULTS / "DFT" / "tables" / "DFT_monte_carlo_pack_values.csv"
fin_path = RESULTS / "FIN" / "tables" / "FIN_monte_carlo_pack_values.csv"

dft = pd.read_csv(dft_path)
fin = pd.read_csv(fin_path)


# Standard baseline value columns
dft_values = dft["pack_value_spg_nonfoil_usd"].dropna()
fin_values = fin["pack_value_baseline_usd"].dropna()


# Pack prices
pack_prices = {
    "DFT": 4.99,
    "FIN": 9.34
}


# --------------------------------------------------
# CALCULATE SUMMARY STATISTICS
# --------------------------------------------------

datasets = {
    "Aetherdrift (DFT)": dft_values,
    "Final Fantasy (FIN)": fin_values
}

print("\nPACK VALUE DISTRIBUTION SUMMARY")
print("=" * 55)

for name, values in datasets.items():
    print(f"\n{name}")
    print(f"Simulated packs: {len(values):,}")
    print(f"Mean value:      ${values.mean():.2f}")
    print(f"Median value:    ${values.median():.2f}")
    print(f"Minimum value:   ${values.min():.2f}")
    print(f"Maximum value:   ${values.max():.2f}")
    print(f"90th percentile: ${values.quantile(0.90):.2f}")
    print(f"99th percentile: ${values.quantile(0.99):.2f}")


# --------------------------------------------------
# CREATE COMPARISON HISTOGRAM
# --------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

plot_settings = [
    (axes[0], dft_values, "Aetherdrift (DFT)", pack_prices["DFT"]),
    (axes[1], fin_values, "Final Fantasy (FIN)", pack_prices["FIN"])
]

for ax, values, title, pack_price in plot_settings:

    mean_value = values.mean()
    median_value = values.median()

    # Display the central 99% of pack values.
    # All simulated packs remain included in the statistics.
    upper_limit = values.quantile(0.99)
    visible_values = values[values <= upper_limit]

    ax.hist(
        visible_values,
        bins=60,
        edgecolor="black",
        alpha=0.75
    )

    ax.axvline(
        pack_price,
        linestyle="--",
        linewidth=2,
        label=f"Pack cost (${pack_price:.2f})"
    )

    ax.axvline(
        mean_value,
        linestyle="-",
        linewidth=2,
        label=f"Mean (${mean_value:.2f})"
    )

    ax.axvline(
        median_value,
        linestyle=":",
        linewidth=2,
        label=f"Median (${median_value:.2f})"
    )

    ax.set_title(title)
    ax.set_xlabel("Simulated Pack Value ($)")
    ax.set_ylabel("Number of Packs")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

fig.suptitle(
    "Monte Carlo Pack Value Distributions",
    fontsize=16
)

fig.text(
    0.5,
    0.01,
    "Note: Histograms display values up to each set's 99th percentile. "
    "All simulated packs are included in summary statistics.",
    ha="center",
    fontsize=9
)

plt.tight_layout(rect=[0, 0.04, 1, 0.94])


# --------------------------------------------------
# SAVE FIGURE
# --------------------------------------------------

output_path = FIGURES / "pack_value_distributions.png"

plt.savefig(output_path, dpi=300, bbox_inches="tight")
plt.show()

print(f"\nChart saved to: {output_path}")
