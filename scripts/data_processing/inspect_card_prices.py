import pandas as pd
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PRICE_FILE = PROJECT_DIR / "data" / "raw" / "cardPrices.csv.bz2"

print("Reading MTGJSON card price data...")

df = pd.read_csv(PRICE_FILE, compression="bz2", nrows=5)

print("\nColumn names:")
print(df.columns.tolist())

print("\nFirst five rows:")
print(df.to_string(index=False))

print("\nDone")