
from pathlib import Path
import pandas as pd

# Locate project and data
PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data" / "all_sets.csv"

# Load the original data
df = pd.read_csv(DATA_FILE)

print("=" * 60)
print("MTG BOOSTER PROFITABILITY - DATA VALIDATION")
print("=" * 60)

# 1. Dataset overview
print("\n1. DATASET OVERVIEW")
print("-" * 40)
print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print(f"Number of sets: {df['set'].nunique()}")

# 2. Missing prices
print("\n2. MISSING PRICE DATA")
print("-" * 40)

price_columns = ["usd", "usd_foil", "usd_etched"]

for column in price_columns:
    missing = df[column].isna().sum()
    percentage = missing / len(df) * 100
    print(
        f"{column}: {missing} missing "
        f"({percentage:.2f}%)"
    )

# 3. Duplicate printings
print("\n3. DUPLICATE PRINTINGS")
print("-" * 40)

duplicate_columns = ["set", "collector_number", "name"]
duplicate_count = df.duplicated(
    subset=duplicate_columns
).sum()

print(f"Duplicate rows: {duplicate_count}")

# 4. Booster flag counts
print("\n4. BOOSTER FLAG COUNTS")
print("-" * 40)

print(df["booster"].value_counts(dropna=False))

print("\nBooster flag by set:")
booster_summary = pd.crosstab(
    df["set"],
    df["booster"],
    dropna=False
)
print(booster_summary)

# 5. Cards and prices by set
print("\n5. SET SUMMARY")
print("-" * 40)

summary = df.groupby(["set", "set_name"]).agg(
    total_printings=("name", "size"),
    missing_nonfoil=("usd", lambda x: x.isna().sum()),
    missing_foil=("usd_foil", lambda x: x.isna().sum()),
    rare_printings=(
        "rarity",
        lambda x: (x == "rare").sum()
    ),
    mythic_printings=(
        "rarity",
        lambda x: (x == "mythic").sum()
    )
).reset_index()

print(summary.to_string(index=False))

print("\nValidation complete.")
print("Original CSV was not modified.")
