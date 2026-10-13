
from pathlib import Path
import time
import requests
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================

SET_CODES = [
    "FRA", "HOB", "MSH", "SOS", "TMT", "ECL",
    "TLA", "SPM", "EOE", "FIN", "TDM", "DFT"
]

OUTPUT_DIR = Path("data")
SET_DIR = OUTPUT_DIR / "individual_sets"
COMBINED_FILE = OUTPUT_DIR / "all_sets.csv"

# Set to True to download every set again.
# Set to False to reuse existing CSV files.
REFRESH_EXISTING = True

BASE_URL = "https://api.scryfall.com/cards/search"

FIELDS = [
    "set",
    "set_name",
    "collector_number",
    "name",
    "rarity",
    "usd",
    "usd_foil",
    "usd_etched",
    "booster",
    "promo_types",
    "frame_effects",
    "border_color",
    "released_at",
    "type_line",
    "finishes",
    "variation",
]


# ============================================================
# DIRECTORIES AND HTTP SESSION
# ============================================================

SET_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "MTGPackProfitabilityResearch/1.0",
    "Accept": "application/json",
})


# ============================================================
# REQUEST WITH RETRIES
# ============================================================

def get_with_retry(url, params=None, max_attempts=7):
    """Request a URL, retrying rate limits and server errors."""

    for attempt in range(max_attempts):
        try:
            response = session.get(
                url,
                params=params,
                timeout=60,
            )

        except requests.RequestException as error:
            if attempt == max_attempts - 1:
                raise

            wait_seconds = min(10 * (2 ** attempt), 120)

            print(f"Connection error: {error}")
            print(f"Retrying in {wait_seconds} seconds...")
            time.sleep(wait_seconds)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == max_attempts - 1:
                response.raise_for_status()

            retry_after = response.headers.get("Retry-After")

            try:
                wait_seconds = max(1, int(retry_after)) + 1
            except (TypeError, ValueError):
                wait_seconds = min(10 * (2 ** attempt), 120)

            print(
                f"HTTP {response.status_code}. "
                f"Waiting {wait_seconds} seconds before retrying..."
            )

            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError(f"Request failed after {max_attempts} attempts.")


# ============================================================
# DOWNLOAD ONE SET
# ============================================================

def download_set(set_code):
    set_code = set_code.upper()
    output_file = SET_DIR / f"{set_code}.csv"

    # Reuse an existing file if refresh is disabled.
    if output_file.exists() and not REFRESH_EXISTING:
        try:
            existing_df = pd.read_csv(output_file)

            if not existing_df.empty:
                print(
                    f"\nSkipping {set_code}: "
                    f"{len(existing_df)} existing rows found."
                )
                return existing_df

        except (OSError, pd.errors.ParserError):
            print(f"Existing {set_code}.csv could not be read. Redownloading.")

    print(f"\nDownloading {set_code}...")

    params = {
        "q": f"set:{set_code.lower()}",
        "unique": "prints",
        "order": "set",
        "format": "json",
    }

    response = get_with_retry(BASE_URL, params=params)
    data = response.json()

    cards = []

    while True:
        for card in data.get("data", []):
            row = {
                field: card.get(field)
                for field in FIELDS
                if field not in {"usd", "usd_foil", "usd_etched"}
            }

            # Scryfall stores prices inside the nested "prices" object.
            prices = card.get("prices") or {}

            row["usd"] = prices.get("usd")
            row["usd_foil"] = prices.get("usd_foil")
            row["usd_etched"] = prices.get("usd_etched")

            row["set"] = card.get("set", set_code).upper()
            row["price_collected_date"] = (
                pd.Timestamp.now().date().isoformat()
            )

            cards.append(row)

        if not data.get("has_more", False):
            break

        next_page = data.get("next_page")

        if not next_page:
            raise RuntimeError(
                f"Scryfall indicated more results for {set_code}, "
                "but did not provide a next-page URL."
            )

        # Leave time between paginated requests.
        time.sleep(2)

        response = get_with_retry(next_page)
        data = response.json()

    if not cards:
        raise ValueError(
            f"No cards returned for {set_code}. "
            "Check that the set code is correct."
        )

    df = pd.DataFrame(cards)

    # Save to a temporary file first to avoid leaving a partial CSV.
    temporary_file = output_file.with_suffix(".tmp")

    df.to_csv(temporary_file, index=False)
    temporary_file.replace(output_file)

    print(f"Saved {len(df)} card printings to {output_file}")

    # Pause between set downloads to reduce rate-limit risk.
    time.sleep(3)

    return df


# ============================================================
# REBUILD COMBINED DATASET
# ============================================================

def rebuild_combined_file():
    """Combine the individual CSVs for the requested sets."""

    all_sets = []
    missing_sets = []

    for set_code in SET_CODES:
        file_path = SET_DIR / f"{set_code}.csv"

        if not file_path.exists():
            missing_sets.append(set_code)
            print(f"Missing file: {file_path}")
            continue

        try:
            df = pd.read_csv(file_path)

            if df.empty:
                missing_sets.append(set_code)
                print(f"Empty file: {file_path}")
                continue

            all_sets.append(df)

        except (OSError, pd.errors.ParserError) as error:
            missing_sets.append(set_code)
            print(f"Could not read {file_path}: {error}")

    if not all_sets:
        print("No valid set files were found. Combined CSV not created.")
        return

    combined = pd.concat(all_sets, ignore_index=True)

    COMBINED_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(COMBINED_FILE, index=False)

    print("\n" + "=" * 55)
    print("COMBINED DATASET SUMMARY")
    print("=" * 55)
    print(f"Total rows: {len(combined)}")
    print(f"Sets represented: {combined['set'].nunique()}")
    print(f"Combined file: {COMBINED_FILE}")

    print("\nRows per set:")
    print(combined.groupby("set").size().sort_index().to_string())

    if missing_sets:
        print("\nSets still missing or invalid:")
        print(", ".join(missing_sets))
    else:
        print("\nAll 12 requested set files are present.")


# ============================================================
# MAIN
# ============================================================

def main():
    print("MTG Pack Profitability - Scryfall Downloader")
    print("=" * 55)

    failed_sets = []

    for set_code in SET_CODES:
        try:
            download_set(set_code)

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
        ) as error:
            failed_sets.append(set_code)
            print(f"\nFAILED {set_code}: {error}")

    # Always rebuild from all existing individual files.
    rebuild_combined_file()

    if failed_sets:
        print("\nSome downloads failed:")
        print(", ".join(failed_sets))
        print(
            "\nWait before rerunning the script. "
            "Existing valid files will be reused."
        )
    else:
        print("\nAll requested downloads completed or were reused.")


if __name__ == "__main__":
    main()
