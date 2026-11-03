# MTG-Pack-Profitability Analysis
This project was developed as my final project for MATH-421- Mathematical Modeling at RIT.

The goal of this project is to investigate the financial value of opening Magic: The Gathering booster packs by comparing the expected market value of the cards pulled against the cost of purchasing a pack. Using probability distributions, expected value calculations, and Monte Carlo simulations, the project examines how profitable opening booster packs may be across different sets.

## Research Objectives

- Calculate the expected market value of a booster pack based on its possible card contents.
- Analyze booster pack composition and the probability of receiving individual cards.
- Compare expected card value against the retail cost of a booster pack.
- Use Monte Carlo simulations to model the variability of pack-opening outcomes.
- Evaluate the probability of recovering the cost of a pack or multiple packs.
- Investigate how changes in card market prices affect expected profitability.
- Compare results across different Magic: The Gathering sets from the past 2 years, including collaboration sets (universe beyond) and in-universe sets.

## Sets Analyzed 

| Set | Set Code | Booster Type | Pack Price |
| -------- | -------- | -------- | -------- | 
| Aetherdrift | DFT  | Play Booster  | $4.99 |
| Final Fantasy  | FIN | Play Booster | $9.34 |

## Methodology
### 1. Data Collection


Card information and booster pack configurations are collected from MTGJSON. Market price information is collected using TCGplayer Market Price data.
The project uses:
- Card names, UUIDs, rarities, and set information.
- Booster pack configurations and card slot probabilities.
- Normal and foil card finishes.
- TCGplayer Market Price data.

The current price snapshot used for the analysis was collected on October 19th, 2026

### 2. Booster Pack Probability Analysis

Booster configurations are processed to determine the probability of receiving each eligible card.
The analysis accounts for:
- Different booster pack slots.
- Common, uncommon, rare, and mythic rare cards.
- Foil and nonfoil cards.
- Wildcard slot.
- Set-specific special card treatments and bonus slots.

### 3. Expected Value Calculations

Expected market value is calculated by combining the probability of receiving each card with its corresponding market price.
The expected value of a pack is compared against its purchase price:
** Expected Profit/Loss = Expected Pack Value - Pack Cost **
** Expected ROI = (Expected Profit/Loss / Pack Cost) x 100 **

### 4. Monte Carlo Simulation

Monte Carlo simulations are used to generate 200,000 simulated booster pack opening for each set.

The simulations help estimate:
- Mean and median pack value.
- Probability of recovering the cost of a pack.
- Probability of pulling cards above selected value thresholds.
- Variability in pack-opening outcomes.
- Financial outcomes when opening multiple packs.

### 5. Market Price Sensitivity Analysis

The project examines how changes in card market prices affect pack profitability.

Market prices are reduced by 10%, 20%, and 30% to evaluate how price fluctuations influence:
- Expected pack value.
- Expected profit or loss.
- Cost recovery probability.
- Multi-pack financial outcomes.
 
### 6.Multi-Pack Analysis

Simulations also examine the outcomes of opening 10, 20, 36, and 100 booster packs.

This analysis compares total purchase cost against the combined market value of the cards obtained.

## Current Results

The following results use the October 19th, 2026 TCGplayer Market Price snapshot.

| Metric | Aetherdrift (DFT) | Final Fantasy (FIN) |
| -------- | -------- | -------- |
| Pack Cost | $4.99  | $9.34  |
| Expected Pack Value  | $5.3067 | $8.9484 |
| Expected Profit/Loss | +$.03167 | -$0.3916 |
| Expected ROI | 6.35% | -4.19% |
| Probability of Recovering Pack Cost | 22.34%| 23.21% |

* Note: Expected values are analytical estimates based on card probabilities and market prices. They are not guaranteed resale proceeds. *

### Aetherdrift (DFT)
- Expected market value exceeds the pack cost.
- The expected profit is approximately $0.32 per pack.
- The probability of recovering the full pack cost in a single opening is approximately 22.34%.
- The estimated break-even market-price decline is approximately 6.25%.

### Final Fantasy (FIN)
- Expected market value is below the pack cost.
- The expected loss is approximately $0.39 per pack.
- The probability of recovering the full pack cost in a single opening is approximately 23.21%.
- The expected value is already below the purchase price before applying additional market-price declines.

## Project Structure
MTG-Pack-Profitability/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── set_probabilities/
│
├── results/
│   ├── individual_sets/
│   │   ├── DFT/
│   │   └── FIN/
│   └── comparisons/
│
├── scripts/
│   ├── analysis/
│   ├── data_collection/
│   ├── data_processing/
│   └── validation/
│
├── reports/
│
├── README.md
└── requirements.txt

Large source datasets and raw downloads are excluded from GitHub when appropriate. In particular, data/raw/AllIdentifiers.json.bz2 is downloaded locally when needed and is excluded through .gitignore

## Running the Project
### Requirements
- Python 3
- pandas
- numpy
- matplotlib
- ijson

Install dependencies:
pip install -r requirements.txt

### Example Commands
Download MTGJSON data:
python3 scripts/data_collection/download_mtgjson.py DFT - booster play

Extract booster probabilities:
python3 scripts/data_processing/extract_booster_probabilities.py DFT play

Extract TCGplayer prices:
python3 scripts/data_processing/extract_tcgplayer_prices.py DFT

Match card prices:
python3 scripts/data_processing/match_set_prices.py DFT

Calculate expected value:
python3 scripts/analysis/calculate_expected_value.py DFT play --pack-price 4.99

Run Monte Carlo simulations:
python3 scripts/analysis/simulate_pack_profitability.py DFT play --pack-price 4.99

Run market sensitivity analysis:
python3 scripts/analysis/analyze_market_value_sensitivity.py DFT play --pack-price 4.99

Replace DFT with FIN and use --pack-price 9.34 to analyze Final Fantasy.

### Data Sources

[MTGJSON](https://mtgjson.com/) – Card information, UUIDs, and booster pack configurations.

[TCGplayer](https://www.tcgplayer.com/) – Market price data used for card valuations.

[Scryfall API](https://api.scryfall.com/cards/search?format=csv&order=set&q=s:SETCODE) – Additional card and price data reference.

[Wizards of the Coast: Reality Fracture – Collecting](https://magic.wizards.com/en/news/feature/collecting-reality-fracture) – Booster pack composition and product information.

### Limitations

- Market prices fluctuate and may change after the data collection date.
- Market value does not guarantee that a card can be sold for that amount.
- The analysis does not deduct seller fees, shipping, or other resale expenses.
- Simulated outcomes depend on the accuracy of the booster probability configurations.
- The analysis currently covers selected sets rather than every Magic: The Gathering expansion.
- Multi-pack simulations model probabilistic outcomes and do not guarantee actual pack-opening results.

### Author
Developed by Chloe Chiang as a mathematical modeling and data analysis project for MATH 421 at Rochester Institute of Technology.
