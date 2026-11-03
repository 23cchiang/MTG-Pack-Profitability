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

  ### Current Results
