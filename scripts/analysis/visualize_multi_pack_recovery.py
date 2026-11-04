
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT / "results" / "comparisons" / "multi_pack_comparison.csv"
)

FIGURES = ROOT / "results" / "comparisons" / "figures"
TABLES = ROOT / "results" / "comparisons" / "tables"

FIGURES.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# LOAD AND FILTER DATA
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

pack_counts = [10, 20, 36, 100]

baseline = df[
    (df["market_price_decline_percent"] == 0)
    & (df["packs_opened"].isin(pack_counts))
    & (df["set_code"].isin(["DFT", "FIN"]))
].copy()

baseline = baseline.sort_values(["set_code", "packs_opened"])

if len(baseline) != 8:
    raise ValueError(
        f"Expected 8 baseline rows, but found {len(baseline)}. "
        "Check the comparison CSV."
    )

# Verify that both sets have all four pack counts.
for set_code in ["DFT", "FIN"]:
    actual_counts = sorted(
        baseline.loc[
            baseline["set_code"] == set_code,
            "packs_opened"
        ].tolist()
    )

    if actual_counts != pack_counts:
        raise ValueError(
            f"Unexpected pack counts for {set_code}: {actual_counts}"
        )


# Save filtered data
table_path = TABLES / "multi_pack_recovery_baseline.csv"
baseline.to_csv(table_path, index=False)


# --------------------------------------------------
# DISPLAY RESULTS
# --------------------------------------------------

print("\nMULTI-PACK RECOVERY COMPARISON")
print("=" * 70)

for set_code, set_name in [
    ("DFT", "Aetherdrift"),
    ("FIN", "Final Fantasy")
]:
    subset = baseline[baseline["set_code"] == set_code]

    print(f"\n{set_name} ({set_code})")

    for _, row in subset.iterrows():
        print(
            f"{int(row['packs_opened']):3} packs | "
            f"Recovery: "
            f"{row['probability_recovering_at_least_cost_percent']:.2f}% | "
            f"Mean P/L: ${row['mean_profit_loss_usd']:.2f}"
        )


# --------------------------------------------------
# EXTRACT SERIES
# --------------------------------------------------

dft = baseline[baseline["set_code"] == "DFT"]
fin = baseline[baseline["set_code"] == "FIN"]

dft_packs = dft["packs_opened"]
fin_packs = fin["packs_opened"]

dft_recovery = dft[
    "probability_recovering_at_least_cost_percent"
]

fin_recovery = fin[
    "probability_recovering_at_least_cost_percent"
]

dft_profit = dft["mean_profit_loss_usd"]
fin_profit = fin["mean_profit_loss_usd"]


# --------------------------------------------------
# CREATE TWO-PANEL CHART
# --------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(15, 6))


# Panel 1: Recovery probability
ax = axes[0]

ax.plot(
    dft_packs,
    dft_recovery,
    marker="o",
    linewidth=2,
    markersize=7,
    label="Aetherdrift (DFT)"
)

ax.plot(
    fin_packs,
    fin_recovery,
    marker="s",
    linewidth=2,
    markersize=7,
    label="Final Fantasy (FIN)"
)

for x, y in zip(dft_packs, dft_recovery):
    ax.annotate(
        f"{y:.1f}%",
        (x, y),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center"
    )

for x, y in zip(fin_packs, fin_recovery):
    ax.annotate(
        f"{y:.1f}%",
        (x, y),
        xytext=(0, -17),
        textcoords="offset points",
        ha="center"
    )

ax.set_title("Probability of Recovering Total Cost")
ax.set_xlabel("Number of Packs Opened")
ax.set_ylabel("Recovery Probability (%)")
ax.set_xticks(pack_counts)
ax.set_ylim(0, 100)
ax.grid(True, alpha=0.3)
ax.legend()


# Panel 2: Mean profit/loss
ax = axes[1]

ax.plot(
    dft_packs,
    dft_profit,
    marker="o",
    linewidth=2,
    markersize=7,
    label="Aetherdrift (DFT)"
)

ax.plot(
    fin_packs,
    fin_profit,
    marker="s",
    linewidth=2,
    markersize=7,
    label="Final Fantasy (FIN)"
)

ax.axhline(
    y=0,
    linestyle="--",
    linewidth=1.5,
    label="Break-even"
)

for x, y in zip(dft_packs, dft_profit):
    ax.annotate(
        f"${y:.2f}",
        (x, y),
        xytext=(0, 9),
        textcoords="offset points",
        ha="center"
    )

for x, y in zip(fin_packs, fin_profit):
    ax.annotate(
        f"${y:.2f}",
        (x, y),
        xytext=(0, -17),
        textcoords="offset points",
        ha="center"
    )

ax.set_title("Expected Mean Profit/Loss")
ax.set_xlabel("Number of Packs Opened")
ax.set_ylabel("Mean Profit/Loss ($)")
ax.set_xticks(pack_counts)
ax.grid(True, alpha=0.3)
ax.legend()


# Overall formatting
fig.suptitle(
    "Multi-Pack Profitability Comparison",
    fontsize=16
)

fig.text(
    0.5,
    0.01,
    "Baseline market prices; 50,000 simulated sessions per scenario.",
    ha="center",
    fontsize=9
)

plt.tight_layout(rect=[0, 0.04, 1, 0.94])


# --------------------------------------------------
# SAVE FIGURE
# --------------------------------------------------

figure_path = FIGURES / "multi_pack_recovery_probability.png"

plt.savefig(
    figure_path,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print(f"\nChart saved to: {figure_path}")
print(f"Table saved to: {table_path}")
