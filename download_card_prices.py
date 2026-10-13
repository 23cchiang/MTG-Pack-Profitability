import requests
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://mtgjson.com/api/v5/csv/cardPrices.csv.bz2"
OUTPUT_PATH = RAW_DIR / "cardPrices.csv.bz2"

print("Downloading MTGJSON card prices")

response = requests.get(URL, timeout=120)
response.raise_for_status()
