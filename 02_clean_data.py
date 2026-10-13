
from pathlib import Path
import pandas as pd

# --------------------------------------------------
# PATHS
# --------------------------------------------------

INPUT_FILE = Path("data/all_sets.csv")
OUTPUT_DIR = Path("data/processed")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

# Normalize fields
df["set"] = df["set"].astype(str).str.upper()
df["rarity"] = df["rarity"].astype(str).str.lower()
df["booster"] = (
    df["booster"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({"true": True, "false": False})
)

for column in ["usd", "usd_foil", "usd_etched"]:
    df[column] = pd.to_numeric(df[column], errors="coerce")

print("RAW DATA")
print(f"Rows: {len(df)}")
print(f"Sets: {df['set'].nunique()}")

# --------------------------------------------------
# CHECK DUPLICATES
# --------------------------------------------------

duplicate_columns = ["set", "collector_number", "name"]
duplicate_count = df.duplicated(
    subset=duplicate_columns
).sum()

print(f"\nDuplicate set/card-number/name rows: {duplicate_count}")

# --------------------------------------------------
# PRICE MISSINGNESS REPORT
# --------------------------------------------------

price_columns = ["usd", "usd_foil", "usd_etched"]

missing_summary = (
    df.groupby(["set", "rarity"])[price_columns]
    .agg(lambda column: column.isna().sum())
    .reset_index()
)

missing_summary.to_csv(
    OUTPUT_DIR / "missing_prices_by_set_rarity.csv",
    index=False,
)

print("\nMissing prices by column:")
print(df[price_columns].isna().sum())

# --------------------------------------------------
# BOOSTER FLAG SUBSETS
# --------------------------------------------------

booster_cards = df[df["booster"] == True].copy()
non_booster_cards = df[df["booster"] == False].copy()

booster_cards.to_csv(
    OUTPUT_DIR / "booster_flag_true.csv",
    index=False,
)

non_booster_cards.to_csv(
    OUTPUT_DIR / "booster_flag_false.csv",
    index=False,
)

# --------------------------------------------------
# SUMMARY BY SET
# --------------------------------------------------

summary = (
    booster_cards.groupby("set")
    .agg(
        set_name=("set_name", "first"),
        card_printings=("name", "size"),
        unique_names=("name", "nunique"),
        missing_nonfoil_price=("usd", lambda x: x.isna().sum()),
        missing_foil_price=("usd_foil", lambda x: x.isna().sum()),
        average_nonfoil_price=("usd", "mean"),
        median_nonfoil_price=("usd", "median"),
    )
    .reset_index()
)

summary.to_csv(
    OUTPUT_DIR / "booster_flag_summary.csv",
    index=False,
)

print("\nBOOSTER FLAG COUNTS FOR ALL SETS")
print(
    pd.crosstab(
        df["set"],
        df["booster"],
        margins=True
    ).to_string()
)

print("\nSETS WITH NO TRUE BOOSTER FLAGS")
true_counts = df.groupby("set")["booster"].apply(
    lambda column: (column == True).sum()
)

print(true_counts[true_counts == 0])


print("\nBOOSTER-FLAG SUMMARY")
print(summary.to_string(index=False))

print("\nSaved cleaned outputs to:", OUTPUT_DIR)
