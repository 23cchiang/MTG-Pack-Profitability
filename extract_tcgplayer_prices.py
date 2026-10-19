
import pandas as pd
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

PRICE_FILE = RAW_DIR / "cardPrices.csv.bz2"
OUTPUT_FILE = PROCESSED_DIR / "DFT_tcgplayer_prices.csv"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

print("Loading MTGJSON price data...")

prices = pd.read_csv(PRICE_FILE, compression="bz2")

print(f"Total price records loaded: {len(prices):,}")

# Keep TCGplayer USD prices for paper cards and retail listings.
prices = prices[
    (prices["priceProvider"] == "tcgplayer")
    & (prices["currency"] == "USD")
    & (prices["gameAvailability"] == "paper")
    & (prices["providerListing"] == "retail")
].copy()

# Keep the latest available date in the downloaded dataset.
prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
latest_date = prices["date"].max()
prices = prices[prices["date"] == latest_date].copy()

# Keep the fields needed for joining and analysis.
prices = prices[
    ["uuid", "cardFinish", "currency", "date", "price",
     "priceProvider", "providerListing"]
]

prices = prices.drop_duplicates(
    subset=["uuid", "cardFinish"],
    keep="last"
)

prices.to_csv(OUTPUT_FILE, index=False)

print("\nExtraction complete!")
print(f"Latest price date: {latest_date.date()}")
print(f"Price records saved: {len(prices):,}")
print(f"Output file: {OUTPUT_FILE}")

print("\nPrices by finish:")
print(prices["cardFinish"].value_counts().to_string())
