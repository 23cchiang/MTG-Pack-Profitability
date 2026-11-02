
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# Project paths and defaults
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "results" / "individual_sets"

DEFAULT_PACK_PRICE = 4.99
RANDOM_SEED = 20261102
N_PORTFOLIOS = 50_000
PACK_COUNTS = [10, 20, 36, 100]


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Analyze MTG booster simulation results."
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
# File validation
# --------------------------------------------------

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}\n"
            "Run the preceding analysis scripts first."
        )


# --------------------------------------------------
# Pack-value distribution
# --------------------------------------------------

def analyze_distribution(pack_values, pack_price, figures_dir,
                         set_code, booster_type):

    plt.figure(figsize=(10, 6))

    plt.hist(pack_values, bins=100)

    plt.axvline(
        pack_price,
        linestyle="--",
        label=f"Pack price (${pack_price:.2f})"
    )

    plt.xlabel("Estimated card market value per pack ($)")
    plt.ylabel("Number of simulated packs")

    plt.title(
        f"{set_code} {booster_type.title()} Booster: "
        "Simulated Pack-Value Distribution"
    )

    plt.legend()
    plt.tight_layout()

    output = (
        figures_dir
        / f"{set_code}_pack_value_distribution.png"
    )

    plt.savefig(output, dpi=200)
    plt.close()

    print(f"Saved histogram: {output}")


# --------------------------------------------------
# Top-card sensitivity
# --------------------------------------------------

def analyze_top_cards(card_ev, pack_price, tables_dir, set_code):

    required = {
        "card_name",
        "expected_value_contribution_usd",
        "expected_copies_per_pack"
    }

    missing = required - set(card_ev.columns)

    if missing:
        raise ValueError(
            f"Expected-value file missing columns: {sorted(missing)}"
        )

    grouped = (
        card_ev.groupby("card_name", as_index=False)
        .agg(
            expected_copies_per_pack=(
                "expected_copies_per_pack", "sum"
            ),
            expected_value_contribution_usd=(
                "expected_value_contribution_usd", "sum"
            )
        )
        .sort_values(
            "expected_value_contribution_usd",
            ascending=False
        )
    )

    total_ev = grouped[
        "expected_value_contribution_usd"
    ].sum()

    if total_ev <= 0:
        raise ValueError(
            "Total expected value must be positive."
        )

    grouped["share_of_total_ev_percent"] = (
        grouped["expected_value_contribution_usd"]
        / total_ev * 100
    )

    grouped["cumulative_ev_share_percent"] = (
        grouped["share_of_total_ev_percent"].cumsum()
    )

    rows = []

    for n in [1, 3, 5, 10]:

        removed_ev = grouped.head(n)[
            "expected_value_contribution_usd"
        ].sum()

        rows.append({
            "cards_removed": n,
            "removed_cards_ev_per_pack_usd": removed_ev,
            "remaining_ev_per_pack_usd": total_ev - removed_ev,
            "removed_share_of_total_ev_percent": (
                removed_ev / total_ev * 100
            ),
            "remaining_ev_minus_pack_price_usd": (
                total_ev - removed_ev - pack_price
            )
        })

    output = (
        tables_dir
        / f"{set_code}_top_card_sensitivity.csv"
    )

    pd.DataFrame(rows).to_csv(output, index=False)

    print("\nTOP EXPECTED-VALUE CARDS")
    print(grouped.head(10).to_string(index=False))

    print("\nTOP-CARD REMOVAL SENSITIVITY")
    print(pd.DataFrame(rows).to_string(index=False))

    print(f"Saved: {output}")


# --------------------------------------------------
# Multi-pack profitability
# --------------------------------------------------

def analyze_multi_pack(
    pack_values,
    pack_price,
    tables_dir,
    set_code
):

    rng = np.random.default_rng(RANDOM_SEED)

    rows = []

    for n_packs in PACK_COUNTS:

        # Each row represents one hypothetical opening session.
        draws = rng.choice(
            pack_values,
            size=(N_PORTFOLIOS, n_packs),
            replace=True
        )

        total_value = draws.sum(axis=1)

        total_cost = n_packs * pack_price
        total_profit = total_value - total_cost

        rows.append({
            "packs_opened": n_packs,
            "total_cost_usd": total_cost,
            "mean_total_card_value_usd": total_value.mean(),
            "median_total_card_value_usd": np.median(total_value),
            "probability_total_value_exceeds_cost_percent": (
                (total_value > total_cost).mean() * 100
            ),
            "probability_total_value_at_least_cost_percent": (
                (total_value >= total_cost).mean() * 100
            ),
            "mean_profit_loss_usd": total_profit.mean(),
            "median_profit_loss_usd": np.median(total_profit),
            "profit_loss_5th_percentile_usd": (
                np.quantile(total_profit, 0.05)
            ),
            "profit_loss_95th_percentile_usd": (
                np.quantile(total_profit, 0.95)
            ),
            "simulated_opening_sessions": N_PORTFOLIOS
        })

    summary = pd.DataFrame(rows)

    output = (
        tables_dir
        / f"{set_code}_multi_pack_profitability.csv"
    )

    summary.to_csv(output, index=False)

    print("\nMULTI-PACK OPENING RESULTS")
    print(summary.to_string(index=False))

    print(f"Saved: {output}")


# --------------------------------------------------
# Probability model audit
# --------------------------------------------------

def audit_probability_model(
    probabilities,
    reports_dir,
    set_code
):

    required = {
        "variant_number",
        "variant_probability",
        "slot_name",
        "cards_per_pack",
        "probability_within_sheet",
        "expected_copies_per_pack"
    }

    missing = required - set(probabilities.columns)

    if missing:
        raise ValueError(
            f"Probability file missing columns: {sorted(missing)}"
        )

    probabilities = probabilities.copy()

    for column in [
        "variant_probability",
        "cards_per_pack",
        "probability_within_sheet",
        "expected_copies_per_pack"
    ]:
        probabilities[column] = pd.to_numeric(
            probabilities[column],
            errors="coerce"
        )

    if probabilities[
        [
            "variant_probability",
            "cards_per_pack",
            "probability_within_sheet",
            "expected_copies_per_pack"
        ]
    ].isna().any().any():

        raise ValueError(
            "Probability file contains missing or nonnumeric values."
        )

    variants = (
        probabilities[
            ["variant_number", "variant_probability"]
        ]
        .drop_duplicates()
        .sort_values("variant_number")
    )

    if variants["variant_number"].duplicated().any():
        raise ValueError(
            "A variant has inconsistent probability values."
        )

    variant_sum = variants[
        "variant_probability"
    ].sum()

    slot_checks = (
        probabilities.groupby(
            ["variant_number", "slot_name"],
            as_index=False
        )
        .agg(
            within_sheet_probability_sum=(
                "probability_within_sheet", "sum"
            ),
            cards_per_pack_min=("cards_per_pack", "min"),
            cards_per_pack_max=("cards_per_pack", "max")
        )
    )

    slot_checks["probability_sums_to_one"] = np.isclose(
        slot_checks["within_sheet_probability_sum"],
        1.0
    )

    slot_checks["cards_per_pack_is_constant"] = (
        slot_checks["cards_per_pack_min"]
        == slot_checks["cards_per_pack_max"]
    )

    # Recalculate expected copies per pack.
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

    copies_ok = (
        probabilities["expected_copy_formula_matches"].all()
    )

    lines = [
        f"{set_code} PROBABILITY MODEL AUDIT",
        "=" * 45,
        f"Variant probability total: {variant_sum:.10f}",
        f"Variant weights sum to 1: {variant_ok}",
        f"Variant/slot groups checked: {len(slot_checks)}",
        (
            "All within-slot probability totals equal 1: "
            f"{slot_checks['probability_sums_to_one'].all()}"
        ),
        (
            "Cards-per-pack constant within each slot: "
            f"{slot_checks['cards_per_pack_is_constant'].all()}"
        ),
        f"Expected-copy formula matches all rows: {copies_ok}",
        "",
        "VARIANT WEIGHTS",
        variants.to_string(index=False),
        "",
        "SLOT CHECKS",
        slot_checks.to_string(index=False),
        "",
        "OVERALL RESULT: "
        + (
            "PASS"
            if variant_ok and slots_ok and copies_ok
            else "REVIEW REQUIRED"
        ),
        "",
        (
            "Scope note: these checks validate the supplied probability "
            "table and the simulation's independent slot-sampling "
            "assumptions. They do not independently prove that the "
            "probability table matches every physical booster "
            "collation rule or print-run constraint."
        )
    ]

    output = (
        reports_dir
        / f"{set_code}_probability_model_audit.txt"
    )

    output.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print("\nPROBABILITY MODEL AUDIT")
    print("\n".join(lines[:10]))

    print(f"Full audit saved: {output}")


# --------------------------------------------------
# Main
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

    set_results_dir = RESULTS_DIR / set_code

    tables_dir = set_results_dir / "tables"
    figures_dir = set_results_dir / "figures"
    reports_dir = set_results_dir / "reports"

    for directory in [
        tables_dir,
        figures_dir,
        reports_dir
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # Input files
    # --------------------------------------------------

    pack_values_file = (
        tables_dir
        / f"{set_code}_monte_carlo_pack_values.csv"
    )

    card_ev_file = (
        PROCESSED_DIR
        / f"{set_code}_expected_value_by_card.csv"
    )

    probability_file = (
        PROCESSED_DIR
        / f"{set_code}_{booster_type}_card_probabilities.csv"
    )

    for path in [
        pack_values_file,
        card_ev_file,
        probability_file
    ]:
        require_file(path)

    # --------------------------------------------------
    # Load data
    # --------------------------------------------------

    print(
        f"Analyzing {set_code} {booster_type.title()} "
        "Booster simulation results..."
    )

    pack_df = pd.read_csv(pack_values_file)
    card_ev = pd.read_csv(card_ev_file)
    probabilities = pd.read_csv(probability_file)

    value_column = "pack_value_spg_nonfoil_usd"

    if value_column not in pack_df.columns:
        raise ValueError(
            f"Pack simulation file needs '{value_column}'. "
            f"Found: {list(pack_df.columns)}"
        )

    pack_values = pd.to_numeric(
        pack_df[value_column],
        errors="coerce"
    ).dropna().to_numpy()

    if len(pack_values) == 0:
        raise ValueError(
            "No valid simulated pack values were found."
        )

    print(f"Loaded {len(pack_values):,} simulated pack values.")
    print(f"Mean: ${pack_values.mean():.4f}")
    print(f"Median: ${np.median(pack_values):.4f}")

    # --------------------------------------------------
    # Run analyses
    # --------------------------------------------------

    analyze_distribution(
        pack_values,
        pack_price,
        figures_dir,
        set_code,
        booster_type
    )

    analyze_top_cards(
        card_ev,
        pack_price,
        tables_dir,
        set_code
    )

    analyze_multi_pack(
        pack_values,
        pack_price,
        tables_dir,
        set_code
    )

    audit_probability_model(
        probabilities,
        reports_dir,
        set_code
    )

    print("\nAnalysis complete.")
    print(f"Results folder: {set_results_dir}")


if __name__ == "__main__":
    main()
