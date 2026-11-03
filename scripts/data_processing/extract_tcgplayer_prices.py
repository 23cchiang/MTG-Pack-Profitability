
import argparse
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

PRICE_FILE = RAW_DIR / "cardPrices.csv.bz2"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Extract latest TCGplayer prices for an MTG set."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTG set code, such as DFT or FIN."
    )

    return parser.parse_args()


# --------------------------------------------------
# Extract prices
# --------------------------------------------------

def main():

    args = parse_arguments()
    set_code = args.set_code.upper()

    cards_file = RAW_DIR / f"{set_code}_cards.csv"
    output_file = PROCESSED_DIR / f"{set_code}_tcgplayer_prices.csv"

    if not PRICE_FILE.exists():
        raise FileNotFoundError(
            f"Price database not found: {PRICE_FILE}"
        )

    if not cards_file.exists():
        raise FileNotFoundError(
            f"Set card file not found: {cards_file}. "
            "Run download_mtgjson.py first."
        )

    print(f"Extracting TCGplayer prices for {set_code}...")

    # Load main set card UUIDs.
    cards = pd.read_csv(cards_file)

    if "uuid" not in cards.columns:
        raise ValueError(
            f"'uuid' column not found in {cards_file}"
        )

    set_uuids = set(cards["uuid"].dropna().astype(str))

    # Include external cards used in the FIN Play Booster.
    external_file = RAW_DIR / f"{set_code}_external_cards.json"

    if external_file.exists():
        import json

        with external_file.open("r", encoding="utf-8") as file:
            external_cards = json.load(file)

        external_uuids = set(external_cards.keys())
        set_uuids.update(external_uuids)

        print(f"External card UUIDs added: {len(external_uuids):,}")

    print(f"Total UUIDs to search: {len(set_uuids):,}")

    print(f"Unique set cards loaded: {len(set_uuids):,}")

    # Load MTGJSON price database.
    print("\nLoading MTGJSON price data...")

    prices = pd.read_csv(
        PRICE_FILE,
        compression="bz2"
    )

    print(f"Total price records loaded: {len(prices):,}")

    # Keep TCGplayer USD prices for paper cards and retail listings.
    prices = prices[
        (prices["priceProvider"] == "tcgplayer")
        & (prices["currency"] == "USD")
        & (prices["gameAvailability"] == "paper")
        & (prices["providerListing"] == "retail")
    ].copy()

    # Keep only cards belonging to this set.
    prices = prices[prices["uuid"].isin(set_uuids)].copy()

    print(f"Price records for {set_code}: {len(prices):,}")

    # Convert dates.
    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce"
    )

    prices = prices.dropna(subset=["date", "price"])

    # Sort by date.
    prices = prices.sort_values("date")

    # Keep the latest price for each card and finish.
    prices = prices.drop_duplicates(
        subset=["uuid", "cardFinish"],
        keep="last"
    )

    # Keep fields needed for joining and analysis.
    prices = prices[
        [
            "uuid",
            "cardFinish",
            "currency",
            "date",
            "price",
            "priceProvider",
            "providerListing"
        ]
    ]

    prices.to_csv(output_file, index=False)

    print("\nExtraction complete!")
    print(f"Price records saved: {len(prices):,}")
    print(f"Output file: {output_file}")

    print("\nPrices by finish:")
    print(prices["cardFinish"].value_counts().to_string())

    print("\nLatest price date:")
    print(prices["date"].max())

    print("\nUnique priced cards:")
    print(prices["uuid"].nunique())


if __name__ == "__main__":
    main()
