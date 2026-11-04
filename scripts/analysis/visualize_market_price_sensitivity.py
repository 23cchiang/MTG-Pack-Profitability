
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
# LOAD SENSITIVITY DATA
# --------------------------------------------------

dft_path = (
    RESULTS / "DFT" / "tables"
    / "DFT_market_value_recovery_and_sensitivity.csv"
)

fin_path = (
    RESULTS / "FIN" / "tables"
    / "FIN_market_value_recovery_and_sensitivity.csv"
)

dft = pd.read_csv(dft_path)
fin = pd.read_csv(fin_path)


# --------------------------------------------------
# FILTER STANDARD BASELINE SCENARIOS
# --------------------------------------------------

dft = dft[
    dft["finish_assumption"] == "SPG nonfoil baseline"
].copy()

fin = fin[
    fin["finish_assumption"] == "Standard baseline"
].copy()

expected_declines = [0.0, 10.0, 20.0, 30.0]

for name, data in [("DFT", dft), ("FIN", fin)]:
    actual = sorted(data["market_price_decline_percent"].tolist())

    if actual != expected_declines:
        raise ValueError(
            f"Unexpected price-decline scenarios for {name}: {actual}"
        )

dft = dft.sort_values("market_price_decline_percent")
fin = fin.sort_values("market_price_decline_percent")


# Save combined comparison data
comparison = pd.concat([dft, fin], ignore_index=True)

table_path = TABLES / "market_price_sensitivity_comparison.csv"
comparison.to_csv(table_path, index=False)


# --------------------------------------------------
# PRINT RESULTS
# --------------------------------------------------

print("\nMARKET-PRICE SENSITIVITY COMPARISON")
print("=" * 75)

for name, data in [("Aetherdrift (DFT)", dft),
                   ("Final Fantasy (FIN)", fin)]:

    print(f"\n{name}")

    for _, row in data.iterrows():
        print(
            f"Price decline: {row['market_price_decline_percent']:5.1f}% | "
            f"Mean value: ${row['mean_pack_market_value_usd']:6.2f} | "
            f"Mean P/L: ${row['mean_profit_loss_per_pack_usd']:6.2f} | "
            f"Recovery probability: "
            f"{row['probability_pack_value_at_least_cost_percent']:.2f}%"
        )

    print(
        f"Break-even price decline: "
        f"{data['break_even_price_decline_percent'].iloc[0]:.2f}%"
    )


# --------------------------------------------------
# EXTRACT SERIES
# --------------------------------------------------

declines = expected_declines

dft_values = dft["mean_pack_market_value_usd"]
fin_values = fin["mean_pack_market_value_usd"]

dft_profit = dft["mean_profit_loss_per_pack_usd"]
fin_profit = fin["mean_profit_loss_per_pack_usd"]

dft_recovery = dft[
    "probability_pack_value_at_least_cost_percent"
]

fin_recovery = fin[
    "probability_pack_value_at_least_cost_percent"
]

dft_pack_price = 4.99
fin_pack_price = 9.34


# --------------------------------------------------
# CREATE THREE-PANEL CHART
# --------------------------------------------------

fig, axes = plt.subplots(1, 3, figsize=(19, 6))


# Panel 1: Mean pack market value
ax = axes[0]

ax.plot(
    declines, dft_values,
    marker="o", linewidth=2,
    markersize=7, label="Aetherdrift (DFT)"
)

ax.plot(
    declines, fin_values,
    marker="s", linewidth=2,
    markersize=7, label="Final Fantasy (FIN)"
)

ax.axhline(
    dft_pack_price,
    linestyle="--",
    linewidth=1.5,
    label="DFT pack cost ($4.99)"
)

ax.axhline(
    fin_pack_price,
    linestyle=":",
    linewidth=1.8,
    label="FIN pack cost ($9.34)"
)

ax.set_title("Mean Pack Market Value")
ax.set_xlabel("Market Price Decline (%)")
ax.set_ylabel("Expected Pack Value ($)")
ax.set_xticks(declines)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8)


# Panel 2: Mean profit/loss
ax = axes[1]

ax.plot(
    declines, dft_profit,
    marker="o", linewidth=2,
    markersize=7, label="Aetherdrift (DFT)"
)

ax.plot(
    declines, fin_profit,
    marker="s", linewidth=2,
    markersize=7, label="Final Fantasy (FIN)"
)

ax.axhline(
    0,
    linestyle="--",
    linewidth=1.5,
    label="Break-even"
)

ax.set_title("Mean Profit/Loss Per Pack")
ax.set_xlabel("Market Price Decline (%)")
ax.set_ylabel("Mean Profit/Loss ($)")
ax.set_xticks(declines)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8)


# Panel 3: Probability of recovering pack cost
ax = axes[2]

ax.plot(
    declines, dft_recovery,
    marker="o", linewidth=2,
    markersize=7, label="Aetherdrift (DFT)"
)

ax.plot(
    declines, fin_recovery,
    marker="s", linewidth=2,
    markersize=7, label="Final Fantasy (FIN)"
)

ax.set_title("Probability of Recovering Pack Cost")
ax.set_xlabel("Market Price Decline (%)")
ax.set_ylabel("Recovery Probability (%)")
ax.set_xticks(declines)
ax.set_ylim(0, 100)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8)


# --------------------------------------------------
# OVERALL FORMATTING
# --------------------------------------------------

fig.suptitle(
    "Market-Price Sensitivity Analysis",
    fontsize=16
)

fig.text(
    0.5,
    0.01,
    "Standard baseline finish assumptions; "
    "market prices reduced uniformly across all card values.",
    ha="center",
    fontsize=9
)

plt.tight_layout(rect=[0, 0.04, 1, 0.94])


# --------------------------------------------------
# SAVE FIGURE
# --------------------------------------------------

figure_path = FIGURES / "market_price_sensitivity_comparison.png"

plt.savefig(
    figure_path,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print(f"\nChart saved to: {figure_path}")
print(f"Table saved to: {table_path}")
