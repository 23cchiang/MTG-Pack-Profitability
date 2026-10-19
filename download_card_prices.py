import requests
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://mtgjson.com/api/v5/csv/cardPrices.csv.bz2"
OUTPUT_PATH = RAW_DIR / "cardPrices.csv.bz2"

print("Downloading MTGJSON card prices")
print(f"URL: {URL}")
print(f"Destination: {OUTPUT_PATH}")

try:
    response = requests.get(URL, timeout=120)
    print(f"HTTP status: {response.status_code}")
    response.raise_for_status()

    OUTPUT_PATH.write_bytes(response.content)

    print("Download complete")
    print(f"Saved to: {OUTPUT_PATH}")
    print(
        f"File size: "
        f"{OUTPUT_PATH.stat().st_size / (1024 * 1024):.2f} MB"
    )
    print(f"Downloaded at : {datetime.now().isoformat(timespec='seconds')}")

except requests.RequestException as error:
    print(f"Download failed: {error}")
