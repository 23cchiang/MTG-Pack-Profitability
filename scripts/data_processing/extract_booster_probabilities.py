
import json
import argparse
from pathlib import Path

import pandas as pd


# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw"
OUTPUT_DIR = PROJECT_DIR / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Extract MTG booster card probabilities."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTG set code, such as DFT or FIN."
    )

    parser.add_argument(
        "booster_type",
        type=str,
        help="Booster type, such as play or collector."
    )

    return parser.parse_args()


# --------------------------------------------------
# Load set data
# --------------------------------------------------

def load_set_data(set_code):
    file_path = RAW_DIR / f"{set_code}.json"

    if not file_path.exists():
        raise FileNotFoundError(
            f"Could not find {file_path}. "
            "Run download_mtgjson.py first."
        )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# Extract probabilities
# --------------------------------------------------

def extract_probabilities(set_data, set_code, booster_type):

    booster_config = set_data.get("booster") or {}
    config = booster_config.get(booster_type)

    if not config:
        raise ValueError(
            f"No '{booster_type}' booster configuration "
            f"found for {set_code}."
        )

    variants = config.get("boosters", [])
    total_variant_weight = config.get("boostersTotalWeight", 0)
    sheets = config.get("sheets", {})
    cards = set_data.get("cards", [])

    if not variants or total_variant_weight <= 0:
        raise ValueError("Booster configuration is incomplete.")

    # Connect card UUIDs to their metadata.
    # Connect card UUIDs to metadata from the main set.
    card_lookup = {
        card["uuid"]: card
        for card in cards
        if card.get("uuid")
    }

    # Include Special Guests when available.
    spg_path = RAW_DIR / "SPG.json"

    if spg_path.exists():
        with spg_path.open("r", encoding="utf-8") as file:
            spg_data = json.load(file)

        for card in spg_data.get("cards", []):
            if card.get("uuid"):
                card_lookup[card["uuid"]] = card
    else:
        print(
            "NOTE: SPG.json not found. "
            "Special Guest card metadata may be missing."
        )

    # Include external cards referenced by the FIN booster configuration.
    external_path = RAW_DIR / "FIN_external_cards.json"

    if external_path.exists():
        with external_path.open("r", encoding="utf-8") as file:
            external_cards = json.load(file)

        card_lookup.update(external_cards)

        print(
            f"Loaded {len(external_cards)} external FIN booster cards."
        )
    else:
        print("NOTE: FIN_external_cards.json not found.")

    rows = []

    for variant_number, variant in enumerate(variants, start=1):

        variant_weight = variant.get("weight", 0)

        if variant_weight <= 0:
            raise ValueError(
                f"Invalid weight for booster variant {variant_number}."
            )

        variant_probability = (
            variant_weight / total_variant_weight
        )

        contents = variant.get("contents", {})

        for slot_name, cards_per_pack in contents.items():

            sheet = sheets.get(slot_name)

            if sheet is None:
                print(
                    f"WARNING: No sheet named '{slot_name}' "
                    f"for variant {variant_number}."
                )
                continue

            sheet_cards = sheet.get("cards", {})
            sheet_total_weight = sheet.get("totalWeight", 0)

            if sheet_total_weight <= 0:
                print(
                    f"WARNING: Invalid total weight for "
                    f"sheet '{slot_name}'."
                )
                continue

            calculated_sheet_weight = sum(sheet_cards.values())

            if calculated_sheet_weight != sheet_total_weight:
                print(
                    f"WARNING: Sheet '{slot_name}' weights sum to "
                    f"{calculated_sheet_weight:,}, but MTGJSON "
                    f"declares {sheet_total_weight:,}."
                )

            for card_uuid, card_weight in sheet_cards.items():

                card = card_lookup.get(card_uuid)

                if card is None:
                    print(
                        f"WARNING: UUID {card_uuid} was not found "
                        "in the set card list or SPG metadata."
                    )
                    continue

                probability_within_sheet = (
                    card_weight / sheet_total_weight
                )

                expected_copies_per_pack = (
                    variant_probability
                    * cards_per_pack
                    * probability_within_sheet
                )

                rows.append({
                    "set_code": set_code,
                    "set_name": set_data.get("name"),
                    "booster_type": booster_type,
                    "variant_number": variant_number,
                    "variant_weight": variant_weight,
                    "variant_probability": variant_probability,
                    "slot_name": slot_name,
                    "cards_per_pack": cards_per_pack,
                    "card_name": card.get("name"),
                    "rarity": card.get("rarity"),
                    "collector_number": card.get("number"),
                    "uuid": card_uuid,
                    "finish_options": ", ".join(
                        card.get("finishes") or []
                    ),
                    "card_weight": card_weight,
                    "sheet_total_weight": sheet_total_weight,
                    "probability_within_sheet": (
                        probability_within_sheet
                    ),
                    "expected_copies_per_pack": (
                        expected_copies_per_pack
                    ),
                })

    return pd.DataFrame(rows)


# --------------------------------------------------
# Main analysis
# --------------------------------------------------

def main():

    args = parse_arguments()

    set_code = args.set_code.upper()
    booster_type = args.booster_type.lower()

    print(
        f"Extracting {set_code} "
        f"{booster_type.title()} Booster probabilities..."
    )

    set_data = load_set_data(set_code)

    df = extract_probabilities(
        set_data,
        set_code,
        booster_type
    )

    if df.empty:
        raise ValueError(
            "No card probabilities were extracted. "
            "Check the booster configuration."
        )

    # --------------------------------------------------
    # Save detailed probabilities
    # --------------------------------------------------

    detailed_path = (
        OUTPUT_DIR
        / f"{set_code}_{booster_type}_card_probabilities.csv"
    )

    df.to_csv(detailed_path, index=False)

    # --------------------------------------------------
    # Summarize expected copies per card
    # --------------------------------------------------

    summary = (
        df.groupby(
            [
                "set_code",
                "set_name",
                "booster_type",
                "card_name",
                "rarity",
                "collector_number",
                "uuid",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            expected_copies_per_pack=(
                "expected_copies_per_pack", "sum"
            ),
            finish_options=("finish_options", "first"),
        )
    )

    # --------------------------------------------------
    # Probability of at least one copy
    # --------------------------------------------------

    probability_rows = []

    variants = (
        df[["variant_number", "variant_probability"]]
        .drop_duplicates()
    )

    for _, card in summary.iterrows():

        card_rows = df[df["uuid"] == card["uuid"]]

        probability_no_copy_overall = 0.0

        for _, variant in variants.iterrows():

            variant_number = variant["variant_number"]
            variant_probability = variant["variant_probability"]

            variant_card_rows = card_rows[
                card_rows["variant_number"] == variant_number
            ]

            probability_no_copy_in_variant = 1.0

            for _, row in variant_card_rows.iterrows():

                p = row["probability_within_sheet"]
                n = int(row["cards_per_pack"])

                probability_no_copy_in_variant *= (1 - p) ** n

            probability_no_copy_overall += (
                variant_probability
                * probability_no_copy_in_variant
            )

        probability_rows.append(
            1 - probability_no_copy_overall
        )

    summary["probability_at_least_one"] = probability_rows

    summary_path = (
        OUTPUT_DIR
        / f"{set_code}_{booster_type}_card_summary.csv"
    )

    summary.to_csv(summary_path, index=False)

    # --------------------------------------------------
    # Expected cards per slot
    # --------------------------------------------------

    slot_summary = (
        df.groupby("slot_name", as_index=False)
        .agg(
            expected_cards_per_pack=(
                "expected_copies_per_pack", "sum"
            )
        )
    )

    slot_path = (
        OUTPUT_DIR
        / f"{set_code}_{booster_type}_slot_summary.csv"
    )

    slot_summary.to_csv(slot_path, index=False)

    # --------------------------------------------------
    # Results
    # --------------------------------------------------

    print("\nExtraction complete!")

    print(f"Detailed results: {detailed_path}")
    print(f"Card summary:     {summary_path}")
    print(f"Slot summary:     {slot_path}")

    print(f"\nDetailed rows: {len(df)}")
    print(f"Unique cards: {summary['uuid'].nunique()}")

    print("\nExpected cards per pack by slot:")
    print(slot_summary.to_string(index=False))

    print("\nTop 10 cards by expected appearances per pack:")

    print(
        summary.sort_values(
            "expected_copies_per_pack",
            ascending=False
        )[
            [
                "card_name",
                "rarity",
                "expected_copies_per_pack",
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()
