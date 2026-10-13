
import pandas as pd
from pathlib import Path

data_path = Path("data/all_sets.csv")
df = pd.read_csv(data_path)

print("DATASET OVERVIEW")
print("-" * 50)
print(f"Total rows: {len(df)}")
print(f"Unique sets: {df['set'].nunique()}")
print(f"Columns: {list(df.columns)}")

print("\nROWS PER SET")
print(df.groupby("set").size().sort_values(ascending=False))

print("\nRARITY COUNTS BY SET")
print(pd.crosstab(df["set"], df["rarity"]))

print("\nMISSING VALUES")
print(df.isna().sum().sort_values(ascending=False))

print("\nBOOSTER FIELD COUNTS")
print(df["booster"].value_counts(dropna=False))

print("\nPRICE AVAILABILITY")
for column in ["usd", "usd_foil", "usd_etched"]:
    if column in df.columns:
        print(
            f"{column}: "
            f"{df[column].notna().sum()} populated, "
            f"{df[column].isna().sum()} missing"
        )

print("\nSAMPLE ROWS")
print(df.head(10).to_string(index=False))
