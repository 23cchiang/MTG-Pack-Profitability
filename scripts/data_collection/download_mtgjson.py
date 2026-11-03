
"""
Download MTGJSON data for any Magic: The Gathering set.

Examples:

    python3 scripts/data_collection/download_mtgjson.py FIN
    python3 scripts/data_collection/download_mtgjson.py DFT
    python3 scripts/data_collection/download_mtgjson.py FIN --booster play

Outputs:
    data/raw/{SET}.json
    data/raw/{SET}_cards.csv
"""

import argparse
import json
from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download card and booster data from MTGJSON."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTGJSON set code, such as DFT or FIN."
    )

    parser.add_argument(
        "--booster",
        type=str,
        default=None,
        help="Optional booster configuration to inspect, such as play."
    )

    return parser.parse_args()


def download_set(set_code):
    url = f"https://mtgjson.com/api/v5/{set_code}.json"

    print(f"Downloading MTGJSON data for {set_code}...")
    print(f"URL: {url}")

    response = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "MTG-Pack-Profitability/1.0"}
    )

    response.raise_for_status()

    response_data = response.json()

    if "data" not in response_data:
        raise ValueError(
            f"MTGJSON response for {set_code} did not contain set data."
        )

    return response_data["data"]


def save_json(set_data, set_code):
    json_path = DATA_DIR / f"{set_code}.json"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(set_data, file, indent=2)

    print(f"Saved JSON: {json_path}")

    return json_path


def save_card_csv(set_data, set_code):
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
            "finishes": ", ".join(
                card.get("finishes") or []
            ),
        })

    df = pd.DataFrame(rows)

    csv_path = DATA_DIR / f"{set_code}_cards.csv"
    df.to_csv(csv_path, index=False)

    print(f"Saved CSV: {csv_path}")

    print(f"\nSet: {set_data.get('name')}")
    print(f"Set code: {set_data.get('code')}")
    print(f"Cards downloaded: {len(df)}")

    print("\nRarity counts:")
    if not df.empty:
        print(df["rarity"].value_counts(dropna=False))
    else:
        print("No cards returned.")

    print("\nBooster type counts:")
    if not df.empty:
        print(
            df["booster_types"]
            .replace("", "None")
            .value_counts(dropna=False)
        )
    else:
        print("No cards returned.")

    print("\nFirst 10 cards:")
    print(df.head(10).to_string(index=False))

    return csv_path


def inspect_booster_config(set_data, requested_booster=None):
    booster_config = set_data.get("booster") or {}

    print("\nAvailable booster configurations:")
    print(list(booster_config.keys()))

    if not booster_config:
        print(
            "\nWARNING: This set does not contain booster "
            "configuration data in its MTGJSON response."
        )
        return

    if requested_booster:
        if requested_booster not in booster_config:
            available = ", ".join(booster_config.keys())

            raise ValueError(
                f"Booster configuration '{requested_booster}' "
                f"was not found for this set.\n"
                f"Available configurations: {available}"
            )

        print(f"\n{requested_booster.title()} Booster configuration:")
        print(
            json.dumps(
                booster_config[requested_booster],
                indent=2
            )
        )

    else:
        print(
            "\nNo specific booster selected. "
            "Use --booster to inspect one configuration."
        )


def main():
    args = parse_arguments()

    set_code = args.set_code.strip().upper()
    booster_type = (
        args.booster.strip().lower()
        if args.booster
        else None
    )

    if not set_code:
        raise ValueError("Set code cannot be empty.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    set_data = download_set(set_code)

    # Save the complete set data before inspecting configurations.
    save_json(set_data, set_code)

    save_card_csv(set_data, set_code)

    inspect_booster_config(set_data, booster_type)

    print("\nDOWNLOAD COMPLETE")
    print(f"Set: {set_data.get('name')}")
    print(f"Set code: {set_code}")


if __name__ == "__main__":
    main()
