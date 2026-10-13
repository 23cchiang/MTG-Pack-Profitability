
import pandas as pd

df = pd.read_csv("data/all_sets.csv")

check_sets = ["FRA", "HOB", "MSH", "SOS", "TMT"]

for code in check_sets:
    subset = df[df["set"] == code]

    print("\n" + "=" * 55)
    print(f"{code}: {subset['set_name'].iloc[0]}")
    print("=" * 55)

    print("Rows:", len(subset))
    print("Release date:", subset["released_at"].iloc[0])
    print("Booster flags:")
    print(subset["booster"].value_counts(dropna=False))

    print("\nRarity counts:")
    print(subset["rarity"].value_counts(dropna=False))

    print("\nFinish counts:")
    print(subset["finishes"].value_counts(dropna=False).head(10))

    print("\nSample cards:")
    print(
        subset[
            ["collector_number", "name", "rarity", "booster", "finishes"]
        ].head(8).to_string(index=False)
    )
