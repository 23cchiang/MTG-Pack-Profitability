import argparse
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"


def match_set_prices(set_code):
    set_code = set_code.upper()

    summary_file = PROCESSED_DIR / f"{set_code}_play_card_summary.csv"
    price_file = PROCESSED_DIR / f"{set_code}_tcgplayer_prices.csv"
    output_file = PROCESSED_DIR / f"{set_code}_cards_with_prices.csv"

    for path in [summary_file, price_file]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    print(f"Loading {set_code} card summary...")
    cards = pd.read_csv(summary_file)

    print("Loading TCGplayer prices...")
    prices = pd.read_csv(price_file)

    required_cards = {"uuid", "finish_options"}
    required_prices = {"uuid", "cardFinish", "price", "date"}

    missing_cards = required_cards - set(cards.columns)
    missing_prices = required_prices - set(prices.columns)

    if missing_cards or missing_prices:
        raise ValueError(
            f"Missing card columns: {sorted(missing_cards)}; "
            f"missing price columns: {sorted(missing_prices)}"
        )

    # Normalize UUIDs.
    cards["uuid"] = cards["uuid"].astype("string").str.strip()
    prices["uuid"] = prices["uuid"].astype("string").str.strip()

    # Expand each card into one row per available finish.
    finish_map = {
        "nonfoil": "normal",
        "normal": "normal",
        "foil": "foil",
        "etched": "etched",
    }

    cards["finish_options"] = (
        cards["finish_options"]
        .astype("string")
        .str.lower()
    )

    cards["price_finish"] = cards["finish_options"].str.split(",")
    cards = cards.explode("price_finish")

    cards["price_finish"] = (
        cards["price_finish"]
        .str.strip()
        .map(finish_map)
    )

    # Match UUID and finish.
    matched = cards.merge(
        prices[["uuid", "cardFinish", "price", "date"]],
        left_on=["uuid", "price_finish"],
        right_on=["uuid", "cardFinish"],
        how="left",
        validate="many_to_many",
    )

    matched.to_csv(output_file, index=False)

    print("\nMatching complete!")
    print(f"Set: {set_code}")
    print(f"Summary cards: {len(cards):,}")
    print(f"Output rows: {len(matched):,}")
    print(f"Cards with a matched price: {matched['price'].notna().sum():,}")
    print(f"Cards without a matched price: {matched['price'].isna().sum():,}")
    print(f"Saved to: {output_file}")

    display_columns = [
        column for column in
        ["card_name", "rarity", "finish_options", "price", "date"]
        if column in matched.columns
    ]

    print("\nExample matched records:")
    print(matched[display_columns].head(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Match MTG set cards with TCGplayer prices."
    )
    parser.add_argument(
        "set_code",
        help="MTG set code, such as DFT."
    )

    args = parser.parse_args()
    match_set_prices(args.set_code)
