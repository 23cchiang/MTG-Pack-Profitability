"""
Post-simulation analysis for the Aetherdrift Play Booster project.

Run from the project root:
    python3 analyze_pack_results.py

Inputs:
    results/DFT_monte_carlo_pack_values.csv
    data/processed/DFT_expected_value_by_card.csv
    data/processed/DFT_play_card_probabilities.csv

Outputs:
    results/DFT_pack_value_distribution.png
    results/DFT_top_card_sensitivity.csv
    results/DFT_multi_pack_profitability.csv
    results/DFT_probability_model_audit.txt
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SET_CODE = "DFT"

SET_RESULTS_DIR = PROJECT_ROOT / "results" / "individual_sets" / SET_CODE
TABLES_DIR = SET_RESULTS_DIR / "tables"
FIGURES_DIR = SET_RESULTS_DIR / "figures"
REPORTS_DIR = SET_RESULTS_DIR / "reports"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PACK_VALUES_FILE = TABLES_DIR / "DFT_monte_carlo_pack_values.csv"
CARD_EV_FILE = PROCESSED_DIR / "DFT_expected_value_by_card.csv"
PROBABILITY_FILE = PROCESSED_DIR / "DFT_play_card_probabilities.csv"
PACK_PRICE = 4.99
RANDOM_SEED = 20261102
N_PORTFOLIOS = 50_000
PACK_COUNTS = [10, 20, 36, 100]


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}\n"
            "Make sure you run this script from your MTG project folder."
        )


def analyze_distribution(pack_values):
    """Create a histogram of simulated pack values."""
    plt.figure(figsize=(10, 6))
    plt.hist(pack_values, bins=100)
    plt.axvline(PACK_PRICE, linestyle="--",
                label=f"Pack price (${PACK_PRICE:.2f})")
    plt.xlabel("Estimated card market value per pack ($)")
    plt.ylabel("Number of simulated packs")
    plt.title("Aetherdrift Play Booster: Simulated Pack-Value Distribution")
    plt.legend()
    plt.tight_layout()

    output = RESULTS_DIR / "DFT_pack_value_distribution.png"
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"Saved histogram: {output}")


def analyze_top_cards(card_ev):
    """Quantify how much expected value is concentrated in top cards."""
    required = {
        "card_name", "expected_value_contribution_usd",
        "expected_copies_per_pack"
    }
    missing = required - set(card_ev.columns)
    if missing:
        raise ValueError(f"Expected-value file missing columns: {sorted(missing)}")

    grouped = (
        card_ev.groupby("card_name", as_index=False)
        .agg(
            expected_copies_per_pack=("expected_copies_per_pack", "sum"),
            expected_value_contribution_usd=(
                "expected_value_contribution_usd", "sum"
            ),
        )
        .sort_values("expected_value_contribution_usd", ascending=False)
    )

    total_ev = grouped["expected_value_contribution_usd"].sum()
    grouped["share_of_total_ev_percent"] = (
        grouped["expected_value_contribution_usd"] / total_ev * 100
    )
    grouped["cumulative_ev_share_percent"] = (
        grouped["share_of_total_ev_percent"].cumsum()
    )

    rows = []
    for n in [1, 3, 5, 10]:
        removed_ev = grouped.head(n)["expected_value_contribution_usd"].sum()
        rows.append({
            "cards_removed": n,
            "removed_cards_ev_per_pack_usd": removed_ev,
            "remaining_ev_per_pack_usd": total_ev - removed_ev,
            "removed_share_of_total_ev_percent": removed_ev / total_ev * 100,
            "remaining_ev_minus_pack_price_usd":
                total_ev - removed_ev - PACK_PRICE,
        })

    output = RESULTS_DIR / "DFT_top_card_sensitivity.csv"
    pd.DataFrame(rows).to_csv(output, index=False)

    print("\nTOP EXPECTED-VALUE CARDS")
    print(grouped.head(10).to_string(index=False))
    print("\nTOP-CARD REMOVAL SENSITIVITY")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"Saved: {output}")


def analyze_multi_pack(pack_values):
    """Resample simulated individual packs into multi-pack openings."""
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []

    for n_packs in PACK_COUNTS:
        # Each row is one hypothetical opening session of n_packs packs.
        draws = rng.choice(
            pack_values,
            size=(N_PORTFOLIOS, n_packs),
            replace=True
        )
        total_value = draws.sum(axis=1)
        total_cost = n_packs * PACK_PRICE
        total_profit = total_value - total_cost

        rows.append({
            "packs_opened": n_packs,
            "total_cost_usd": total_cost,
            "mean_total_card_value_usd": total_value.mean(),
            "median_total_card_value_usd": np.median(total_value),
            "probability_total_value_exceeds_cost_percent":
                (total_value > total_cost).mean() * 100,
            "probability_total_value_at_least_cost_percent":
                (total_value >= total_cost).mean() * 100,
            "mean_profit_loss_usd": total_profit.mean(),
            "median_profit_loss_usd": np.median(total_profit),
            "profit_loss_5th_percentile_usd": np.quantile(total_profit, 0.05),
            "profit_loss_95th_percentile_usd": np.quantile(total_profit, 0.95),
            "simulated_opening_sessions": N_PORTFOLIOS,
        })

    summary = pd.DataFrame(rows)
    output = RESULTS_DIR / "DFT_multi_pack_profitability.csv"
    summary.to_csv(output, index=False)

    print("\nMULTI-PACK OPENING RESULTS")
    print(summary.to_string(index=False))
    print(f"Saved: {output}")


def audit_probability_model(probabilities):
    """Check variant weights, slot weights, and expected-copy calculations."""
    required = {
        "variant_number", "variant_probability", "slot_name",
        "cards_per_pack", "probability_within_sheet",
        "expected_copies_per_pack"
    }
    missing = required - set(probabilities.columns)
    if missing:
        raise ValueError(f"Probability file missing columns: {sorted(missing)}")

    for col in [
        "variant_probability", "cards_per_pack",
        "probability_within_sheet", "expected_copies_per_pack"
    ]:
        probabilities[col] = pd.to_numeric(probabilities[col], errors="coerce")

    variants = (
        probabilities[["variant_number", "variant_probability"]]
        .drop_duplicates()
        .sort_values("variant_number")
    )
    variant_sum = variants["variant_probability"].sum()

    slot_checks = (
        probabilities.groupby(
            ["variant_number", "slot_name"], as_index=False
        )
        .agg(
            within_sheet_probability_sum=(
                "probability_within_sheet", "sum"
            ),
            cards_per_pack_min=("cards_per_pack", "min"),
            cards_per_pack_max=("cards_per_pack", "max"),
        )
    )
    slot_checks["probability_sums_to_one"] = np.isclose(
        slot_checks["within_sheet_probability_sum"], 1.0
    )
    slot_checks["cards_per_pack_is_constant"] = (
        slot_checks["cards_per_pack_min"]
        == slot_checks["cards_per_pack_max"]
    )

    # The expected number of copies in a pack for a row is:
    # variant probability * number of cards in that slot * within-sheet probability.
    probabilities["expected_copies_recalculated"] = (
        probabilities["variant_probability"]
        * probabilities["cards_per_pack"]
        * probabilities["probability_within_sheet"]
    )
    probabilities["expected_copy_formula_matches"] = np.isclose(
        probabilities["expected_copies_per_pack"],
        probabilities["expected_copies_recalculated"],
        rtol=1e-6,
        atol=1e-9
    )

    variant_ok = np.isclose(variant_sum, 1.0)
    slots_ok = (
        slot_checks["probability_sums_to_one"].all()
        and slot_checks["cards_per_pack_is_constant"].all()
    )
    copies_ok = probabilities["expected_copy_formula_matches"].all()

    lines = [
        "AETHERDRIFT PROBABILITY MODEL AUDIT",
        "=" * 45,
        f"Variant probability total: {variant_sum:.10f}",
        f"Variant weights sum to 1: {variant_ok}",
        f"Variant/slot groups checked: {len(slot_checks)}",
        f"All within-slot probability totals equal 1: "
        f"{slot_checks['probability_sums_to_one'].all()}",
        f"Cards-per-pack constant within each slot: "
        f"{slot_checks['cards_per_pack_is_constant'].all()}",
        f"Expected-copy formula matches all rows: {copies_ok}",
        "",
        "VARIANT WEIGHTS",
        variants.to_string(index=False),
        "",
        "SLOT CHECKS",
        slot_checks.to_string(index=False),
        "",
        "OVERALL RESULT: "
        + ("PASS" if variant_ok and slots_ok and copies_ok else "REVIEW REQUIRED"),
        "",
        "Scope note: these checks validate the supplied probability table and "
        "the simulation's independent slot-sampling assumptions. They do not "
        "independently prove that the probability table matches every physical "
        "booster collation rule or print-run constraint."
    ]

    output = RESULTS_DIR / "DFT_probability_model_audit.txt"
    output.write_text("\n".join(lines), encoding="utf-8")

    print("\nPROBABILITY MODEL AUDIT")
    print("\n".join(lines[:10]))
    print(f"Full audit saved: {output}")


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PACK_VALUES_FILE, CARD_EV_FILE, PROBABILITY_FILE]:
        require_file(path)

    print("Loading existing Monte Carlo and expected-value outputs...")
    pack_df = pd.read_csv(PACK_VALUES_FILE)
    card_ev = pd.read_csv(CARD_EV_FILE)
    probabilities = pd.read_csv(PROBABILITY_FILE)

    value_column = "pack_value_spg_nonfoil_usd"
    if value_column not in pack_df.columns:
        raise ValueError(
            f"Pack simulation file needs the column '{value_column}'. "
            f"Found: {list(pack_df.columns)}"
        )
    pack_values = pd.to_numeric(
        pack_df[value_column], errors="coerce"
    ).dropna().to_numpy()

    if len(pack_values) == 0:
        raise ValueError("No valid simulated pack values were found.")

    print(f"Loaded {len(pack_values):,} simulated pack values.")
    print(f"Mean: ${pack_values.mean():.4f}")
    print(f"Median: ${np.median(pack_values):.4f}")

    analyze_distribution(pack_values)
    analyze_top_cards(card_ev)
    analyze_multi_pack(pack_values)
    audit_probability_model(probabilities)

    print("\nAnalysis complete. Check the results folder for four new outputs.")


if __name__ == "__main__":
    main()
