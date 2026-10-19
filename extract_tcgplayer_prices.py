import pandas as pd
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

PRICE_FILE = RAW_DIR / "cardPrices.csv.bz2"
OUTPUT_FILE = PROCESSED_DIR / "DFT_tcgplayer_prices.csv"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

print("Loading MTGJSON price data...")

# Keep TCGplayer USD prices for paper cards and retail listing
prices = prices[
    (prices["priceProvider"] == "tcgplayer")
    & (prices["currency"] == "USD")
    & (prices["gameAvailability"] == "paper")
    & (prices["providerListing"] == "retail")
].copy()

# Keep the latest available date in the downloaded dataset.
prices = prices[
    ["uuid", "cardFinish", "currency", "date", "price", "priceProvider", "providerListing"]
]

prices = prices.drop_duplicates(
    subset=["uuid", "cardFinish"],
    keep="last"
)

prices.to_csv(OUTPUT_FILE, index=False)

print("\nExtraction complete!")
print(f"Latest price date: {latest_date.date()}")
print(f"Price records saved: {len(prices)}")
print(f"Output file: {OUTPUT_FILE}")

print("\nPrices by finished:")
print(prices["cardFinish"].value_counts().to_string())