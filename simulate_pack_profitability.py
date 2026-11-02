"""
Monte Carlo simulation for Aetherdrift (DFT) Play Boosters.

Run from the project root:
    python3 simulate_pack_profitability.py

Inputs:
    data/processed/DFT_play_card_probabilities.csv
    data/processed/DFT_tcgplayer_prices.csv
    data/raw/SPG.json

Outputs:
    results/DFT_monte_carlo_summary.csv
    results/DFT_monte_carlo_pack_values.csv
    results/DFT_monte_carlo_report.txt

Model:
- First draw a booster variant using variant_probability.
- Within each slot, draw cards using probability_within_sheet.
- Add cards_per_pack copies for that slot.
- Foil and foilLand use foil prices.
- Other slots use nonfoil prices in the baseline.
- Special Guest finish is unknown, so both nonfoil-baseline and all-foil
  sensitivity simulations are reported.
- This models card market value, not cash proceeds after selling fees.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RAW_DIR = PROJECT_DIR / "data" / "raw"
RESULTS_DIR = PROJECT_DIR / "results"

PROBABILITY_FILE = PROCESSED_DIR / "DFT_play_card_probabilities.csv"
PRICE_FILE = PROCESSED_DIR / "DFT_tcgplayer_prices.csv"
SPG_FILE = RAW_DIR / "SPG.json"

PACK_PRICE = 4.99
N_PACKS = 200_000
RANDOM_SEED = 4212026
THRESHOLDS = [4.99, 10.00, 20.00, 50.00, 100.00]


def load_price_lookup():
    prices = pd.read_csv(PRICE_FILE)
    required = {"uuid", "cardFinish", "price"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Price file missing columns: {sorted(missing)}")

    prices["price"] = pd.to_numeric(prices["price"], errors="coerce")
    prices["cardFinish"] = prices["cardFinish"].astype(str).str.lower()
    prices = prices.dropna(subset=["uuid", "price"])
    prices = prices.sort_values("date") if "date" in prices.columns else prices
    prices = prices.drop_duplicates(["uuid", "cardFinish"], keep="last")

    lookup = {}
    for row in prices.itertuples(index=False):
        finish_key = "nonfoil" if str(row.cardFinish) == "normal" else str(row.cardFinish)
        lookup[(str(row.uuid), finish_key)] = float(row.price)
    return lookup


def load_spg_uuids():
    with open(SPG_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {str(card["uuid"]) for card in payload.get("cards", [])}


def prepare_probability_data(price_lookup, spg_uuids):
    probs = pd.read_csv(PROBABILITY_FILE)
    required = {
        "variant_number", "variant_probability", "slot_name",
        "cards_per_pack", "uuid", "card_name",
        "probability_within_sheet", "expected_copies_per_pack"
    }
    missing = required - set(probs.columns)
    if missing:
        raise ValueError(f"Probability file missing columns: {sorted(missing)}")

    for col in ["variant_probability", "cards_per_pack",
                "probability_within_sheet", "expected_copies_per_pack"]:
        probs[col] = pd.to_numeric(probs[col], errors="coerce")
    if probs[list(["variant_probability", "cards_per_pack",
                   "probability_within_sheet"])].isna().any().any():
        raise ValueError("Probability data contains missing/non-numeric weights.")

    # Check that variant probabilities are defined consistently.
    variants = (
        probs[["variant_number", "variant_probability"]]
        .drop_duplicates()
        .sort_values("variant_number")
    )
    if not np.isclose(variants["variant_probability"].sum(), 1.0):
        raise ValueError("Variant probabilities do not sum to 1.")

    # Attach prices. Special Guest UUIDs are in SPG.json and are also
    # looked up against the same MTGJSON TCGplayer price extract.
    def get_price(uuid, finish):
        return price_lookup.get((str(uuid), finish), np.nan)

    probs["uuid"] = probs["uuid"].astype(str)
    probs["is_special_guest"] = probs["uuid"].isin(spg_uuids)

    def slot_price(row, spg_finish="nonfoil"):
        slot = str(row["slot_name"])
        if slot in {"foil", "foilLand"}:
            finish = "foil"
        elif slot == "specialGuest":
            finish = spg_finish
        else:
            finish = "nonfoil"
        return get_price(row["uuid"], finish)

    probs["price_nonfoil"] = probs["uuid"].map(
        lambda u: get_price(u, "nonfoil")
    )
    probs["price_foil"] = probs["uuid"].map(
        lambda u: get_price(u, "foil")
    )
    probs["price_baseline"] = probs.apply(
        lambda r: slot_price(r, "nonfoil"), axis=1
    )
    probs["price_spg_all_foil"] = probs.apply(
        lambda r: slot_price(r, "foil"), axis=1
    )

    missing_baseline = probs[probs["price_baseline"].isna()]
    if not missing_baseline.empty:
        examples = missing_baseline[["slot_name", "card_name", "uuid"]].head(10)
        raise ValueError(
            f"{len(missing_baseline)} probability rows lack baseline prices. "
            f"Examples:\n{examples.to_string(index=False)}"
        )

    return probs, variants


def build_variant_models(probs, variants, price_column):
    models = {}
    for variant in variants.itertuples(index=False):
        variant_rows = probs[probs["variant_number"] == variant.variant_number]
        slot_models = {}
        for slot, group in variant_rows.groupby("slot_name"):
            weights = group["probability_within_sheet"].to_numpy(dtype=float)
            if (weights < 0).any() or not np.isclose(weights.sum(), 1.0):
                raise ValueError(
                    f"Within-sheet probabilities for variant "
                    f"{variant.variant_number}, slot {slot} sum to {weights.sum()}."
                )
            prices = group[price_column].to_numpy(dtype=float)
            cards_per_pack_values = group["cards_per_pack"].dropna().unique()
            if len(cards_per_pack_values) != 1:
                raise ValueError(
                    f"Multiple cards_per_pack values for variant "
                    f"{variant.variant_number}, slot {slot}."
                )
            slot_models[slot] = (
                prices, weights, int(cards_per_pack_values[0])
            )
        models[int(variant.variant_number)] = slot_models
    return models


def simulate(models, variants, n_packs, seed):
    rng = np.random.default_rng(seed)
    variant_numbers = variants["variant_number"].to_numpy(dtype=int)
    variant_weights = variants["variant_probability"].to_numpy(dtype=float)
    chosen_variants = rng.choice(
        variant_numbers, size=n_packs, p=variant_weights
    )
    pack_values = np.zeros(n_packs, dtype=float)

    for variant_number in variant_numbers:
        pack_indices = np.flatnonzero(chosen_variants == variant_number)
        if len(pack_indices) == 0:
            continue
        slot_models = models[int(variant_number)]
        for slot, (prices, weights, cards_per_pack) in slot_models.items():
            draws = rng.choice(
                prices, size=(len(pack_indices), cards_per_pack), p=weights
            )
            pack_values[pack_indices] += draws.sum(axis=1)

    return pack_values


def summarize(values, scenario):
    profit = values - PACK_PRICE
    rows = [
        {"metric": "packs_simulated", "value": len(values), "scenario": scenario},
        {"metric": "mean_pack_value_usd", "value": values.mean(), "scenario": scenario},
        {"metric": "median_pack_value_usd", "value": np.median(values), "scenario": scenario},
        {"metric": "standard_deviation_usd", "value": values.std(ddof=1), "scenario": scenario},
        {"metric": "mean_profit_loss_usd", "value": profit.mean(), "scenario": scenario},
        {"metric": "mean_roi_percent", "value": profit.mean() / PACK_PRICE * 100, "scenario": scenario},
        {"metric": "probability_value_at_least_pack_price_percent",
         "value": (values >= PACK_PRICE).mean() * 100, "scenario": scenario},
        {"metric": "probability_profit_positive_percent",
         "value": (values > PACK_PRICE).mean() * 100, "scenario": scenario},
    ]
    for threshold in THRESHOLDS:
        rows.append({
            "metric": f"probability_value_at_least_{threshold:.2f}_usd_percent",
            "value": (values >= threshold).mean() * 100,
            "scenario": scenario
        })
    for quantile in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
        rows.append({
            "metric": f"value_percentile_{int(quantile*100)}_usd",
            "value": np.quantile(values, quantile),
            "scenario": scenario
        })
    return rows


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PROBABILITY_FILE, PRICE_FILE, SPG_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    print("Loading probability, price, and Special Guest data...")
    price_lookup = load_price_lookup()
    spg_uuids = load_spg_uuids()
    probs, variants = prepare_probability_data(price_lookup, spg_uuids)

    baseline_models = build_variant_models(probs, variants, "price_baseline")
    foil_models = build_variant_models(probs, variants, "price_spg_all_foil")

    print(f"Simulating {N_PACKS:,} packs per scenario...")
    baseline_values = simulate(
        baseline_models, variants, N_PACKS, RANDOM_SEED
    )
    foil_values = simulate(
        foil_models, variants, N_PACKS, RANDOM_SEED
    )

    summary_rows = []
    summary_rows += summarize(baseline_values, "SPG nonfoil baseline")
    summary_rows += summarize(foil_values, "SPG all-foil sensitivity")
    summary = pd.DataFrame(summary_rows)

    summary_path = RESULTS_DIR / "DFT_monte_carlo_summary.csv"
    summary.to_csv(summary_path, index=False)

    pack_values = pd.DataFrame({
        "pack_number": np.arange(1, N_PACKS + 1),
        "booster_variant": "sampled",
        "pack_value_spg_nonfoil_usd": baseline_values,
        "profit_loss_spg_nonfoil_usd": baseline_values - PACK_PRICE,
        "pack_value_spg_all_foil_usd": foil_values,
        "profit_loss_spg_all_foil_usd": foil_values - PACK_PRICE,
    })
    pack_path = RESULTS_DIR / "DFT_monte_carlo_pack_values.csv"
    pack_values.to_csv(pack_path, index=False)

    baseline_ev = baseline_values.mean()
    analytic_ev = (
        probs["expected_copies_per_pack"] * probs["price_baseline"]
    ).sum()
    report = [
        "AETHERDRIFT PLAY BOOSTER — MONTE CARLO PROFITABILITY",
        "=" * 62,
        f"Pack price: ${PACK_PRICE:.2f}",
        f"Simulations per scenario: {N_PACKS:,}",
        f"Random seed: {RANDOM_SEED}",
        "",
        f"Simulated baseline mean: ${baseline_ev:.4f}",
        f"Analytical expected value check: ${analytic_ev:.4f}",
        f"Difference: ${baseline_ev - analytic_ev:.4f}",
        "",
        "Interpretation: probabilities are estimated by simulated pack outcomes.",
        "This is market card value, not net cash after selling fees or shipping.",
        "Special Guest finish is unknown; nonfoil is baseline and all-foil is sensitivity.",
        "",
        "See DFT_monte_carlo_summary.csv for thresholds and percentiles.",
    ]
    report_path = RESULTS_DIR / "DFT_monte_carlo_report.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print("\nMONTE CARLO RESULTS — SPG NONFOIL BASELINE")
    print(f"Mean pack value: ${baseline_values.mean():.4f}")
    print(f"Median pack value: ${np.median(baseline_values):.4f}")
    print(f"Probability pack value >= ${PACK_PRICE:.2f}: "
          f"{(baseline_values >= PACK_PRICE).mean()*100:.2f}%")
    for threshold in [10, 20, 50, 100]:
        print(f"Probability pack value >= ${threshold:.2f}: "
              f"{(baseline_values >= threshold).mean()*100:.2f}%")
    print(f"Analytical EV check: ${analytic_ev:.4f}")
    print("\nSaved:")
    print(summary_path)
    print(pack_path)
    print(report_path)


if __name__ == "__main__":
    main()
