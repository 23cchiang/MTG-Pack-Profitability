
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RESULTS = ROOT / "results" / "individual_sets"
OUTPUT_DIR = ROOT / "results" / "comparisons"

FIGURES = OUTPUT_DIR / "figures"
TABLES = OUTPUT_DIR / "tables"

FIGURES.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# LOAD SIMULATION DATA
# --------------------------------------------------

dft_path = RESULTS / "DFT" / "tables" / "DFT_monte_carlo_pack_values.csv"
fin_path = RESULTS / "FIN" / "tables" / "FIN_monte_carlo_pack_values.csv"

dft = pd.read_csv(dft_path)
fin = pd.read_csv(fin_path)

dft_values = dft["pack_value_spg_nonfoil_usd"].dropna()
fin_values = fin["pack_value_baseline_usd"].dropna()


# --------------------------------------------------
# CALCULATE PERCENTILES
# --------------------------------------------------

percentiles = [10, 25, 50, 75, 90, 95, 99]

dft_percentiles = [
    dft_values.quantile(p / 100)
    for p in percentiles
]

fin_percentiles = [
    fin_values.quantile(p / 100)
    for p in percentiles
]

comparison = pd.DataFrame({
    "percentile": percentiles,
    "DFT_pack_value_usd": dft_percentiles,
    "FIN_pack_value_usd": fin_percentiles
})


# --------------------------------------------------
# SAVE PERCENTILE TABLE
# --------------------------------------------------

table_path = TABLES / "pack_value_percentiles.csv"

comparison.to_csv(table_path, index=False)


# --------------------------------------------------
# PRINT RESULTS
# --------------------------------------------------

print("\nPACK VALUE PERCENTILE COMPARISON")
print("=" * 65)

print(
    comparison.to_string(
        index=False,
        formatters={
            "DFT_pack_value_usd": "${:.2f}".format,
            "FIN_pack_value_usd": "${:.2f}".format
        }
    )
)

print("\nPACK COST COMPARISON")
print("-" * 40)
print("Aetherdrift (DFT): $4.99")
print("Final Fantasy (FIN): $9.34")


# --------------------------------------------------
# CREATE PERCENTILE CHART
# --------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 7))

ax.plot(
    percentiles,
    dft_percentiles,
    marker="o",
    linewidth=2,
    markersize=7,
    label="Aetherdrift (DFT)"
)

ax.plot(
    percentiles,
    fin_percentiles,
    marker="s",
    linewidth=2,
    markersize=7,
    label="Final Fantasy (FIN)"
)


# Pack cost reference lines
ax.axhline(
    y=4.99,
    linestyle="--",
    linewidth=1.8,
    label="DFT pack cost ($4.99)"
)

ax.axhline(
    y=9.34,
    linestyle=":",
    linewidth=2,
    label="FIN pack cost ($9.34)"
)


# Add value labels to each point
for x, y in zip(percentiles, dft_percentiles):
    ax.annotate(
        f"${y:.2f}",
        (x, y),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center"
    )

for x, y in zip(percentiles, fin_percentiles):
    ax.annotate(
        f"${y:.2f}",
        (x, y),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center"
    )


# Formatting
ax.set_title(
    "Monte Carlo Pack Value Percentiles",
    fontsize=16
)

ax.set_xlabel("Percentile", fontsize=12)
ax.set_ylabel("Pack Value ($)", fontsize=12)

ax.set_xticks(percentiles)
ax.set_xticklabels([f"{p}th" for p in percentiles])

ax.grid(True, alpha=0.3)
ax.legend()

plt.tight_layout()


# --------------------------------------------------
# SAVE FIGURE
# --------------------------------------------------

figure_path = FIGURES / "pack_value_percentiles.png"

plt.savefig(
    figure_path,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print(f"\nChart saved to: {figure_path}")
print(f"Table saved to: {table_path}")
