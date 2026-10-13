
import json
from pathlib import Path

import pandas as pd


# --------------------------------------------------
# Project paths and settings
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
OUTPUT_DIR = PROJECT_DIR / "data" / "processed"

SET_CODE = "DFT"
BOOSTER_TYPE = "play"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_set_data():
    """Load the saved MTGJSON set file."""
    file_path = RAW_DIR / f"{SET_CODE}.json"

    if not file_path.exists():
        raise FileNotFoundError(
            f"Could not find {file_path}. "
            "Run download_mtgjson.py first."
        )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_probabilities(set_data):
    """
    Calculate card probabilities from MTGJSON's
    booster variant weights and card-sheet weights.
    """
    booster_config = set_data.get("booster") or {}
    config = booster_config.get(BOOSTER_TYPE)

    if not config:
        raise ValueError(
            f"No '{BOOSTER_TYPE}' booster configuration "
            f"found for {SET_CODE}."
        )

    variants = config.get("boosters", [])
    total_variant_weight = config.get("boostersTotalWeight", 0)
    sheets = config.get("sheets", {})
    cards = set_data.get("cards", [])

    if not variants or total_variant_weight <= 0:
        raise ValueError("Booster configuration is incomplete.")

    # Connect card UUIDs to their names and metadata.
    card_lookup = {
        card["uuid"]: card
        for card in cards
        if card.get("uuid")
    }

    # Some booster sheets can reference cards from other sets.
    # Load Special Guests as an additional metadata source.
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

            # Check whether the individual card weights add up
            # to the sheet's declared total weight.
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
                        "in the set card list."
                    )
                    continue

                # Conditional probability of selecting this card
                # from this sheet.
                probability_within_sheet = (
                    card_weight / sheet_total_weight
                )

                # Expected number of copies of this card per pack
                # contributed by this variant and slot.
                expected_copies_per_pack = (
                    variant_probability
                    * cards_per_pack
                    * probability_within_sheet
                )

                rows.append({
                    "set_code": SET_CODE,
                    "set_name": set_data.get("name"),
                    "booster_type": BOOSTER_TYPE,
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


def main():
    print(f"Extracting {SET_CODE} Play Booster probabilities...")

    set_data = load_set_data()
    df = extract_probabilities(set_data)

    if df.empty:
        raise ValueError(
            "No card probabilities were extracted. "
            "Check the booster configuration."
        )

    # Save detailed probabilities by pack variant and slot.
    detailed_path = (
        OUTPUT_DIR / f"{SET_CODE}_play_card_probabilities.csv"
    )
    df.to_csv(detailed_path, index=False)

    # Combine the same card across variants and slots.
    # This estimates its expected number of appearances per pack.

    print("Dataframe columns:", df.columns.tolist())

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

    # Calculate the probability of at least one copy of each card.
    # Booster variants are mutually exclusive, so calculate the
    # probability within each variant before weighting the results.

    probability_rows = []

    variants = (
        df[["variant_number", "variant_probability"]]
        .drop_duplicates()
    )

    for _, card in summary.iterrows():
        card_rows = df[df["uuid"] == card["uuid"]]

        # Total probability of getting no copy, across all variants.
        probability_no_copy_overall = 0.0

        for _, variant in variants.iterrows():
            variant_number = variant["variant_number"]
            variant_probability = variant["variant_probability"]

            variant_card_rows = card_rows[
                card_rows["variant_number"] == variant_number
                ]

            # If the card is absent from this variant, its
            # probability of not appearing in the pack is 1.
            probability_no_copy_in_variant = 1.0

            for _, row in variant_card_rows.iterrows():
                p = row["probability_within_sheet"]
                n = int(row["cards_per_pack"])

                # Assumes independent draws within this slot.
                probability_no_copy_in_variant *= (1 - p) ** n

            probability_no_copy_overall += (
                    variant_probability * probability_no_copy_in_variant
            )

        probability_rows.append(1 - probability_no_copy_overall)

    summary["probability_at_least_one"] = probability_rows

    summary_path = (
        OUTPUT_DIR / f"{SET_CODE}_play_card_summary.csv"
    )
    summary.to_csv(summary_path, index=False)

    # Report the expected number of cards contributed by each slot.
    slot_summary = (
        df.groupby("slot_name", as_index=False)
        .agg(
            expected_cards_per_pack=(
                "expected_copies_per_pack", "sum"
            )
        )
    )

    slot_path = (
        OUTPUT_DIR / f"{SET_CODE}_play_slot_summary.csv"
    )
    slot_summary.to_csv(slot_path, index=False)

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
            "expected_copies_per_pack", ascending=False
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
