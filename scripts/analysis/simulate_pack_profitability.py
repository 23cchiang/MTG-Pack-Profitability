
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Project paths and defaults
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "results" / "individual_sets"

DEFAULT_PACK_PRICE = 4.99
DEFAULT_N_PACKS = 200_000
RANDOM_SEED = 4212026

THRESHOLDS = [4.99, 10.00, 20.00, 50.00, 100.00]

FOIL_SLOTS = {"foil", "foilLand"}


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Simulate MTG booster pack profitability."
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

    parser.add_argument(
        "--n-packs",
        type=int,
        default=DEFAULT_N_PACKS,
        help="Number of packs to simulate."
    )

    return parser.parse_args()


# --------------------------------------------------
# Price loading
# --------------------------------------------------

def normalize_prices(price_file, finish_column, source_priority):
    """Load and normalize one source of finish-specific prices."""

    prices = pd.read_csv(price_file)

    required = {"uuid", finish_column, "price"}
    missing = required - set(prices.columns)

    if missing:
        raise ValueError(
            f"{price_file.name} missing columns: {sorted(missing)}"
        )

    prices["uuid"] = prices["uuid"].astype("string").str.strip()

    prices["price"] = pd.to_numeric(
        prices["price"], errors="coerce"
    )

    prices["finish"] = (
        prices[finish_column]
        .astype("string")
        .str.lower()
        .str.strip()
        .replace({
            "normal": "nonfoil",
            "nonfoil": "nonfoil",
            "foil": "foil"
        })
    )

    prices = prices[
        prices["finish"].isin(["foil", "nonfoil"])
    ].copy()

    prices = prices.dropna(
        subset=["uuid", "price"]
    )

    if "date" in prices.columns:
        prices["date"] = pd.to_datetime(
            prices["date"], errors="coerce"
        )
    else:
        prices["date"] = pd.NaT

    prices["source_priority"] = source_priority

    return prices[
        ["uuid", "finish", "price", "date", "source_priority"]
    ]


def load_price_lookup(set_price_file, all_price_file):
    """
    Combine set-specific matched prices with the full price extract.

    The set-specific matched file takes priority when dates are equal.
    The latest available price is retained per UUID and finish.
    """

    all_prices = normalize_prices(
        all_price_file,
        finish_column="cardFinish",
        source_priority=0
    )

    set_prices = normalize_prices(
        set_price_file,
        finish_column="price_finish",
        source_priority=1
    )

    prices = pd.concat(
        [all_prices, set_prices],
        ignore_index=True
    )

    prices = prices.sort_values(
        ["date", "source_priority"],
        na_position="first"
    )

    prices = prices.drop_duplicates(
        ["uuid", "finish"],
        keep="last"
    )

    lookup = {}

    for row in prices.itertuples(index=False):
        lookup[(str(row.uuid), row.finish)] = float(row.price)

    return lookup


# --------------------------------------------------
# Probability preparation
# --------------------------------------------------

def prepare_probability_data(
    probability_file,
    price_lookup
):

    probs = pd.read_csv(probability_file)

    required = {
        "variant_number",
        "variant_probability",
        "slot_name",
        "cards_per_pack",
        "uuid",
        "card_name",
        "probability_within_sheet",
        "expected_copies_per_pack"
    }

    missing = required - set(probs.columns)

    if missing:
        raise ValueError(
            f"Probability file missing columns: {sorted(missing)}"
        )

    numeric_columns = [
        "variant_probability",
        "cards_per_pack",
        "probability_within_sheet",
        "expected_copies_per_pack"
    ]

    for column in numeric_columns:
        probs[column] = pd.to_numeric(
            probs[column], errors="coerce"
        )

    if probs[numeric_columns].isna().any().any():
        raise ValueError(
            "Probability data contains missing or nonnumeric values."
        )

    probs["uuid"] = (
        probs["uuid"].astype("string").str.strip()
    )

    # Verify booster variant probabilities.
    variants = (
        probs[["variant_number", "variant_probability"]]
        .drop_duplicates()
        .sort_values("variant_number")
    )

    if variants["variant_number"].duplicated().any():
        raise ValueError(
            "A booster variant has inconsistent probabilities."
        )

    if not np.isclose(
        variants["variant_probability"].sum(), 1.0
    ):
        raise ValueError(
            "Variant probabilities do not sum to 1."
        )

    if (
        (variants["variant_probability"] < 0).any()
        or (variants["variant_probability"] > 1).any()
    ):
        raise ValueError("Invalid variant probabilities.")

    # Attach both finishes to every card.
    probs["price_nonfoil"] = probs["uuid"].map(
        lambda uuid: price_lookup.get(
            (str(uuid), "nonfoil"), np.nan
        )
    )

    probs["price_foil"] = probs["uuid"].map(
        lambda uuid: price_lookup.get(
            (str(uuid), "foil"), np.nan
        )
    )

    # Baseline: foil slots use foil prices.
    # Special Guests use nonfoil prices.
    # All other slots use nonfoil prices.
    probs["price_baseline"] = np.where(
        probs["slot_name"].isin(FOIL_SLOTS),
        probs["price_foil"],
        probs["price_nonfoil"]
    )

    # Sensitivity: only Special Guests switch to foil prices.
    probs["price_spg_all_foil"] = probs["price_baseline"].copy()

    special_guest = probs["slot_name"].eq("specialGuest")

    probs.loc[
        special_guest, "price_spg_all_foil"
    ] = probs.loc[
        special_guest, "price_foil"
    ]

    # Validate baseline prices.
    missing_baseline = probs[
        probs["price_baseline"].isna()
    ]

    if not missing_baseline.empty:
        examples = missing_baseline[
            ["slot_name", "card_name", "uuid"]
        ].head(10)

        raise ValueError(
            f"{len(missing_baseline)} probability rows lack "
            f"baseline prices.\n{examples.to_string(index=False)}"
        )

    # The sensitivity simulation also needs complete prices.
    missing_sensitivity = probs[
        probs["price_spg_all_foil"].isna()
    ]

    if not missing_sensitivity.empty:
        examples = missing_sensitivity[
            ["slot_name", "card_name", "uuid"]
        ].head(10)

        raise ValueError(
            f"{len(missing_sensitivity)} probability rows lack "
            f"all-foil sensitivity prices.\n"
            f"{examples.to_string(index=False)}"
        )

    return probs, variants


# --------------------------------------------------
# Build booster models
# --------------------------------------------------

def build_variant_models(probs, variants, price_column):

    models = {}

    for variant in variants.itertuples(index=False):

        variant_rows = probs[
            probs["variant_number"] == variant.variant_number
        ]

        slot_models = {}

        for slot, group in variant_rows.groupby("slot_name"):

            weights = group[
                "probability_within_sheet"
            ].to_numpy(dtype=float)

            if (
                not np.isfinite(weights).all()
                or (weights < 0).any()
                or not np.isclose(weights.sum(), 1.0)
            ):
                raise ValueError(
                    f"Invalid sheet probabilities for variant "
                    f"{variant.variant_number}, slot {slot}. "
                    f"Sum: {weights.sum()}"
                )

            prices = group[
                price_column
            ].to_numpy(dtype=float)

            if not np.isfinite(prices).all():
                raise ValueError(
                    f"Missing or invalid prices for variant "
                    f"{variant.variant_number}, slot {slot}."
                )

            cards_per_pack_values = (
                group["cards_per_pack"].dropna().unique()
            )

            if len(cards_per_pack_values) != 1:
                raise ValueError(
                    f"Multiple cards_per_pack values for variant "
                    f"{variant.variant_number}, slot {slot}."
                )

            cards_per_pack = cards_per_pack_values[0]

            if (
                cards_per_pack <= 0
                or not float(cards_per_pack).is_integer()
            ):
                raise ValueError(
                    f"Invalid cards_per_pack for variant "
                    f"{variant.variant_number}, slot {slot}."
                )

            slot_models[slot] = (
                prices,
                weights,
                int(cards_per_pack)
            )

        models[int(variant.variant_number)] = slot_models

    return models


# --------------------------------------------------
# Monte Carlo simulation
# --------------------------------------------------

def simulate(models, variants, n_packs, seed):

    rng = np.random.default_rng(seed)

    variant_numbers = variants[
        "variant_number"
    ].to_numpy(dtype=int)

    variant_weights = variants[
        "variant_probability"
    ].to_numpy(dtype=float)

    chosen_variants = rng.choice(
        variant_numbers,
        size=n_packs,
        p=variant_weights
    )

    pack_values = np.zeros(n_packs, dtype=float)

    for variant_number in variant_numbers:

        pack_indices = np.flatnonzero(
            chosen_variants == variant_number
        )

        if len(pack_indices) == 0:
            continue

        slot_models = models[int(variant_number)]

        for slot, (prices, weights, cards_per_pack) in slot_models.items():

            draws = rng.choice(
                prices,
                size=(len(pack_indices), cards_per_pack),
                p=weights
            )

            pack_values[pack_indices] += draws.sum(axis=1)

    return pack_values


# --------------------------------------------------
# Simulation summary
# --------------------------------------------------

def summarize(values, scenario, pack_price, thresholds):

    profit = values - pack_price

    rows = [
        {
            "metric": "packs_simulated",
            "value": len(values),
            "scenario": scenario
        },
        {
            "metric": "mean_pack_value_usd",
            "value": values.mean(),
            "scenario": scenario
        },
        {
            "metric": "median_pack_value_usd",
            "value": np.median(values),
            "scenario": scenario
        },
        {
            "metric": "standard_deviation_usd",
            "value": values.std(ddof=1),
            "scenario": scenario
        },
        {
            "metric": "mean_profit_loss_usd",
            "value": profit.mean(),
            "scenario": scenario
        },
        {
            "metric": "mean_roi_percent",
            "value": profit.mean() / pack_price * 100,
            "scenario": scenario
        },
        {
            "metric": "probability_value_at_least_pack_price_percent",
            "value": (values >= pack_price).mean() * 100,
            "scenario": scenario
        },
        {
            "metric": "probability_profit_positive_percent",
            "value": (values > pack_price).mean() * 100,
            "scenario": scenario
        }
    ]

    for threshold in thresholds:
        rows.append({
            "metric": (
                f"probability_value_at_least_{threshold:.2f}_usd_percent"
            ),
            "value": (values >= threshold).mean() * 100,
            "scenario": scenario
        })

    for quantile in [
        0.05, 0.10, 0.25, 0.50,
        0.75, 0.90, 0.95, 0.99
    ]:
        rows.append({
            "metric": f"value_percentile_{int(quantile * 100)}_usd",
            "value": np.quantile(values, quantile),
            "scenario": scenario
        })

    return rows


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    args = parse_arguments()

    set_code = args.set_code.upper()
    booster_type = args.booster_type.lower()

    pack_price = args.pack_price
    n_packs = args.n_packs

    if pack_price <= 0:
        raise ValueError("Pack price must be greater than zero.")

    if n_packs <= 0:
        raise ValueError("Number of packs must be greater than zero.")

    probability_file = (
        PROCESSED_DIR
        / f"{set_code}_{booster_type}_card_probabilities.csv"
    )

    set_price_file = (
        PROCESSED_DIR
        / f"{set_code}_cards_with_prices.csv"
    )

    all_price_file = (
        PROCESSED_DIR
        / f"{set_code}_tcgplayer_prices.csv"
    )

    results_dir = RESULTS_DIR / set_code
    tables_dir = results_dir / "tables"
    reports_dir = results_dir / "reports"

    tables_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    for path in [
        probability_file,
        set_price_file,
        all_price_file
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Required input not found: {path}"
            )

    print(
        f"Loading {set_code} {booster_type.title()} "
        "probabilities and prices..."
    )

    price_lookup = load_price_lookup(
        set_price_file,
        all_price_file
    )

    probs, variants = prepare_probability_data(
        probability_file,
        price_lookup
    )

    baseline_models = build_variant_models(
        probs, variants, "price_baseline"
    )

    foil_models = build_variant_models(
        probs, variants, "price_spg_all_foil"
    )

    print(f"Simulating {n_packs:,} packs per scenario...")

    baseline_values = simulate(
        baseline_models,
        variants,
        n_packs,
        RANDOM_SEED
    )

    foil_values = simulate(
        foil_models,
        variants,
        n_packs,
        RANDOM_SEED
    )

    # --------------------------------------------------
    # Summary tables
    # --------------------------------------------------

    summary_rows = []

    summary_rows += summarize(
        baseline_values,
        "SPG nonfoil baseline",
        pack_price,
        THRESHOLDS
    )

    summary_rows += summarize(
        foil_values,
        "SPG all-foil sensitivity",
        pack_price,
        THRESHOLDS
    )

    summary = pd.DataFrame(summary_rows)

    summary_path = (
        tables_dir
        / f"{set_code}_monte_carlo_summary.csv"
    )

    summary.to_csv(summary_path, index=False)

    # --------------------------------------------------
    # Individual pack outcomes
    # --------------------------------------------------

    pack_values = pd.DataFrame({
        "pack_number": np.arange(1, n_packs + 1),
        "booster_variant": "sampled",
        "pack_value_spg_nonfoil_usd": baseline_values,
        "profit_loss_spg_nonfoil_usd": (
            baseline_values - pack_price
        ),
        "pack_value_spg_all_foil_usd": foil_values,
        "profit_loss_spg_all_foil_usd": (
            foil_values - pack_price
        )
    })

    pack_path = (
        tables_dir
        / f"{set_code}_monte_carlo_pack_values.csv"
    )

    pack_values.to_csv(pack_path, index=False)

    # --------------------------------------------------
    # Analytical expected-value check
    # --------------------------------------------------

    baseline_ev = baseline_values.mean()

    analytic_ev = (
        probs["expected_copies_per_pack"]
        * probs["price_baseline"]
    ).sum()

    foil_analytic_ev = (
        probs["expected_copies_per_pack"]
        * probs["price_spg_all_foil"]
    ).sum()

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    report = [
        f"{set_code} {booster_type.upper()} BOOSTER "
        "— MONTE CARLO PROFITABILITY",
        "=" * 62,
        f"Pack price: ${pack_price:.2f}",
        f"Simulations per scenario: {n_packs:,}",
        f"Random seed: {RANDOM_SEED}",
        "",
        f"Simulated baseline mean: ${baseline_values.mean():.4f}",
        f"Analytical expected value check: ${analytic_ev:.4f}",
        f"Difference: ${baseline_values.mean() - analytic_ev:.4f}",
        "",
        f"Simulated all-foil SPG mean: ${foil_values.mean():.4f}",
        f"Analytical all-foil expected value: ${foil_analytic_ev:.4f}",
        f"Difference: ${foil_values.mean() - foil_analytic_ev:.4f}",
        "",
        "MODEL ASSUMPTIONS",
        "- Booster variants are sampled using variant probabilities.",
        "- Cards are sampled independently within each slot.",
        "- Foil and foilLand slots use foil prices.",
        "- Other slots use nonfoil prices in the baseline.",
        "- Special Guest all-foil is a sensitivity scenario.",
        "- Values represent card market value, not cash proceeds after fees.",
        "",
        "OUTPUT FILES",
        f"- {summary_path}",
        f"- {pack_path}"
    ]

    report_path = (
        reports_dir
        / f"{set_code}_monte_carlo_report.txt"
    )

    report_path.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    # --------------------------------------------------
    # Terminal output
    # --------------------------------------------------

    print("\nMONTE CARLO RESULTS — SPG NONFOIL BASELINE")

    print(f"Set: {set_code}")
    print(f"Booster type: {booster_type}")
    print(f"Packs simulated: {n_packs:,}")

    print(f"Mean pack value: ${baseline_values.mean():.4f}")
    print(f"Median pack value: ${np.median(baseline_values):.4f}")

    print(
        f"Probability pack value >= ${pack_price:.2f}: "
        f"{(baseline_values >= pack_price).mean() * 100:.2f}%"
    )

    for threshold in [10, 20, 50, 100]:
        print(
            f"Probability pack value >= ${threshold:.2f}: "
            f"{(baseline_values >= threshold).mean() * 100:.2f}%"
        )

    print(f"Analytical EV check: ${analytic_ev:.4f}")

    print("\nMONTE CARLO RESULTS — SPG ALL-FOIL SENSITIVITY")
    print(f"Mean pack value: ${foil_values.mean():.4f}")
    print(f"Analytical EV check: ${foil_analytic_ev:.4f}")

    print("\nSaved:")

    print(summary_path)
    print(pack_path)
    print(report_path)


if __name__ == "__main__":
    main()
