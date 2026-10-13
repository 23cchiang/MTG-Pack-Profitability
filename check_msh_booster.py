
import time
import requests

url = "https://api.scryfall.com/cards/search"
params = {
    "q": "set:msh",
    "unique": "prints",
    "order": "set",
}

headers = {
    "User-Agent": "MTGPackProfitabilityResearch/1.0",
    "Accept": "application/json",
}

total = 0
true_count = 0
false_count = 0

while url:
    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    for card in data["data"]:
        total += 1
        if card.get("booster") is True:
            true_count += 1
        elif card.get("booster") is False:
            false_count += 1

    url = data.get("next_page")
    params = None

    if url:
        time.sleep(2)

print(f"Total printings: {total}")
print(f"Booster=True: {true_count}")
print(f"Booster=False: {false_count}")
