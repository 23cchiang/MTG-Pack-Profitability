
import bz2
import json
import requests
import ijson

from decimal import Decimal
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw"

FIN_PATH = RAW_DIR / "FIN.json"
SPG_PATH = RAW_DIR / "SPG.json"

URL = "https://mtgjson.com/api/v5/AllIdentifiers.json.bz2"

DOWNLOAD_PATH = RAW_DIR / "AllIdentifiers.json.bz2"
OUTPUT_PATH = RAW_DIR / "FIN_external_cards.json"


def main():
    print("Loading FIN and SPG card UUIDs...")

    with FIN_PATH.open(encoding="utf-8") as f:
        fin = json.load(f)

    with SPG_PATH.open(encoding="utf-8") as f:
        spg = json.load(f)

    required_uuids = set(
        fin["booster"]["play"]["sheets"]["throughTheAges"]["cards"]
    )

    known_uuids = {
        card["uuid"]
        for card in fin.get("cards", []) + spg.get("cards", [])
        if card.get("uuid")
    }

    required_uuids -= known_uuids

    print(f"External UUIDs needed: {len(required_uuids)}")

    if not DOWNLOAD_PATH.exists():
        print("Downloading MTGJSON AllIdentifiers...")

        response = requests.get(URL, stream=True, timeout=60)
        response.raise_for_status()

        with DOWNLOAD_PATH.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
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

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
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
    print(f"Output: {OUTPUT_PATH}")

    if missing:
        print("\nMissing UUIDs:")
        for uuid in sorted(missing):
            print(uuid)


if __name__ == "__main__":
    main()
