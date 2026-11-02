
import json
from pathlib import Path

import pandas as pd
import requests


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TEST_SET = "DFT"
URL = f"https://mtgjson.com/api/v5/{TEST_SET}.json"


def main():
    print(f"Downloading MTGJSON data for {TEST_SET}...")

    response = requests.get(URL, timeout=60)
    response.raise_for_status()
    set_data = response.json()["data"]

    # Save the original MTGJSON response.
    json_path = DATA_DIR / f"{TEST_SET}.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(set_data, file, indent=2)

    # Inspect available booster configurations.
    booster_config = set_data.get("booster") or {}

    print("\nAvailable booster configurations:")
    print(list(booster_config.keys()))

    play_config = booster_config.get("play")

    print("\nPlay Booster configuration:")
    print(json.dumps(play_config, indent=2))

    # Extract card information.
    cards = set_data.get("cards", [])
    rows = []

    for card in cards:
        rows.append({
            "set_code": set_data.get("code"),
            "set_name": set_data.get("name"),
            "card_name": card.get("name"),
            "rarity": card.get("rarity"),
            "number": card.get("number"),
            "uuid": card.get("uuid"),
            "booster_types": ", ".join(
                card.get("boosterTypes") or []
            ),
            "finishes": ", ".join(card.get("finishes") or []),
        })

    # Create the DataFrame BEFORE using df.
    df = pd.DataFrame(rows)

    csv_path = DATA_DIR / f"{TEST_SET}_cards.csv"
    df.to_csv(csv_path, index=False)

    print(f"\nSet: {set_data.get('name')}")
    print(f"Cards downloaded: {len(df)}")
    print(f"Saved CSV: {csv_path}")

    print("\nRarity counts:")
    print(df["rarity"].value_counts(dropna=False))

    print("\nBooster type counts:")
    print(
        df["booster_types"]
        .replace("", "None")
        .value_counts(dropna=False)
    )

    print("\nFirst 10 cards:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

