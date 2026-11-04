
import bz2
import json
import requests
import ijson

from decimal import Decimal
from pathlib import Path
import argparse


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw"

URL = "https://mtgjson.com/api/v5/AllIdentifiers.json.bz2"
DOWNLOAD_PATH = RAW_DIR / "AllIdentifiers.json.bz2"


def main():
    parser = argparse.ArgumentParser(
        description="Download external booster card metadata."
    )
    parser.add_argument(
        "set_code",
        help="MTGJSON set code, such as EOE or FIN."
    )
    args = parser.parse_args()

    set_code = args.set_code.upper()

    set_path = RAW_DIR / f"{set_code}.json"
    spg_path = RAW_DIR / "SPG.json"
    output_path = RAW_DIR / f"{set_code}_external_cards.json"

    if not set_path.exists():
        raise FileNotFoundError(f"Set file not found: {set_path}")

    print(f"Loading {set_code} and SPG card UUIDs...")

    with set_path.open(encoding="utf-8") as f:
        set_data = json.load(f)

    spg_cards = []
    if spg_path.exists():
        with spg_path.open(encoding="utf-8") as f:
            spg_cards = json.load(f).get("cards", [])

    known_uuids = {
        card["uuid"]
        for card in set_data.get("cards", []) + spg_cards
        if card.get("uuid")
    }

    play_config = set_data.get("booster", {}).get("play", {})
    sheets = play_config.get("sheets", {})

    required_uuids = set()

    for sheet_name, sheet in sheets.items():
        sheet_uuids = set(sheet.get("cards", {}).keys())
        required_uuids.update(sheet_uuids)

    required_uuids -= known_uuids

    print(f"Set: {set_code}")
    print(f"Booster sheets inspected: {len(sheets)}")
    print(f"External UUIDs needed: {len(required_uuids)}")

    if not required_uuids:
        print("No external card metadata is needed.")
        output_path.write_text("{}", encoding="utf-8")
        return

    if not DOWNLOAD_PATH.exists():
        print("Downloading MTGJSON AllIdentifiers...")

        response = requests.get(URL, stream=True, timeout=60)
        response.raise_for_status()

        with DOWNLOAD_PATH.open("wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

        print("Download complete.")

    print("Searching AllIdentifiers for required cards...")

    found_cards = {}

    with bz2.open(DOWNLOAD_PATH, "rb") as f:
        for uuid, card in ijson.kvitems(f, "data"):
            if uuid in required_uuids:
                found_cards[uuid] = card

                if len(found_cards) == len(required_uuids):
                    break

    def convert_decimal(value):
        if isinstance(value, Decimal):
            return float(value)

        raise TypeError(
            f"Object of type {type(value).__name__} "
            "is not JSON serializable"
        )

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            found_cards,
            f,
            indent=2,
            default=convert_decimal
        )

    missing = required_uuids - set(found_cards)

    print("\nLookup complete.")
    print(f"Cards found: {len(found_cards)}")
    print(f"Cards missing: {len(missing)}")
    print(f"Output: {output_path}")

    if missing:
        print("\nMissing UUIDs:")
        for uuid in sorted(missing):
            print(uuid)


if __name__ == "__main__":
    main()
