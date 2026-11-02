
import pandas as pd
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

SUMMARY_FILE = PROCESSED_DIR / "DFT_play_card_summary.csv"
PRICE_FILE = PROCESSED_DIR / "DFT_tcgplayer_prices.csv"
OUTPUT_FILE = PROCESSED_DIR / "DFT_cards_with_prices.csv"

print("Loading DFT card summary...")
cards = pd.read_csv(SUMMARY_FILE)

print("Loading TCGplayer prices...")
prices = pd.read_csv(PRICE_FILE)

# Normalize UUIDs to avoid mismatches caused by formatting.
cards["uuid"] = cards["uuid"].astype("string").str.strip()
prices["uuid"] = prices["uuid"].astype("string").str.strip()

# Match normal cards to normal finishes, and foils to foil finishes.
# Keep etched prices separate rather than treating them as ordinary foils.
finish_map = {
    "nonfoil": "normal",
    "normal": "normal",
    "foil": "foil",
    "etched": "etched",
}

cards["price_finish"] = (
    cards["finish_options"]
    .astype("string")
    .str.lower()
    .map(finish_map)
)

# Join using the UUID and the finish when it can be identified.
matched = cards.merge(
    prices[["uuid", "cardFinish", "price", "date"]],
    left_on=["uuid", "price_finish"],
    right_on=["uuid", "cardFinish"],
    how="left",
    validate="many_to_many",
)

matched.to_csv(OUTPUT_FILE, index=False)

print("\nMatching complete!")
print(f"Summary cards: {len(cards):,}")
print(f"Output rows: {len(matched):,}")
print(f"Cards with a matched price: {matched['price'].notna().sum():,}")
print(f"Cards without a matched price: {matched['price'].isna().sum():,}")
print(f"Saved to: {OUTPUT_FILE}")

print("\nExample matched records:")
print(
    matched[
        ["card_name", "rarity", "finish_options", "price", "date"]
    ].head(10).to_string(index=False)
)
