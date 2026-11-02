"""
Calculate expected monetary value of an Aetherdrift (DFT) Play Booster.

Inputs (relative to this script's project folder):
    data/processed/DFT_play_card_probabilities.csv
    data/processed/DFT_cards_with_prices.csv
    data/processed/DFT_tcgplayer_prices.csv
    data/raw/SPG.json

The Special Guest slot can have foil and nonfoil versions. Because the
probability file does not specify a finish probability, the main estimate
uses nonfoil SPG prices and a separate all-foil sensitivity estimate.
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RAW_DIR = PROJECT_DIR / "data" / "raw"
RESULTS_DIR = PROJECT_DIR / "results"

PROBABILITY_FILE = PROCESSED_DIR / "DFT_play_card_probabilities.csv"
DFT_PRICE_FILE = PROCESSED_DIR / "DFT_cards_with_prices.csv"
ALL_PRICE_FILE = PROCESSED_DIR / "DFT_tcgplayer_prices.csv"
SPG_FILE = RAW_DIR / "SPG.json"

PACK_PRICE = 4.99
FOIL_SLOTS = {"foil", "foilLand"}


def load_price_pivot(price_file):
    """Return one row per UUID with latest normal/nonfoil and foil prices."""
    prices = pd.read_csv(price_file)
    required = {"uuid", "cardFinish", "price"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Price file missing columns: {sorted(missing)}")

    prices["price"] = pd.to_numeric(prices["price"], errors="coerce")
    prices = prices.dropna(subset=["uuid", "price"]).copy()

    # In the extracted MTGJSON file, 'normal' is the nonfoil finish.
    prices["finish"] = prices["cardFinish"].replace({"normal": "nonfoil"})
    prices = prices[prices["finish"].isin(["foil", "nonfoil"])]

    # Keep the latest record per UUID/finish.
    if "date" in prices.columns:
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
        prices = prices.sort_values("date")

    prices = prices.drop_duplicates(["uuid", "finish"], keep="last")
    return prices.pivot(index="uuid", columns="finish", values="price").reset_index()


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for file in [PROBABILITY_FILE, DFT_PRICE_FILE, ALL_PRICE_FILE, SPG_FILE]:
        if not file.exists():
            raise FileNotFoundError(f"Could not find required input: {file}")

    print("Loading Aetherdrift probabilities, prices, and Special Guest data...")
    probabilities = pd.read_csv(PROBABILITY_FILE)
    dft_prices = pd.read_csv(DFT_PRICE_FILE)
    all_prices = load_price_pivot(ALL_PRICE_FILE)

    required_probability_columns = {
        "uuid", "card_name", "rarity", "slot_name",
        "expected_copies_per_pack"
    }
    missing = required_probability_columns - set(probabilities.columns)
    if missing:
        raise ValueError(f"Probability file missing columns: {sorted(missing)}")

    probabilities["expected_copies_per_pack"] = pd.to_numeric(
        probabilities["expected_copies_per_pack"], errors="coerce"
    )
    if probabilities["expected_copies_per_pack"].isna().any():
        raise ValueError("Some expected_copies_per_pack values are missing/nonnumeric.")

    # Build SPG lookup from the English card records in SPG.json.
    with open(SPG_FILE, "r", encoding="utf-8") as f:
        spg_json = json.load(f)

    spg_cards = pd.DataFrame([
        {
            "uuid": card["uuid"],
            "spg_card_name": card["name"],
            "spg_rarity": card.get("rarity"),
            "spg_finishes": ", ".join(card.get("finishes", [])),
        }
        for card in spg_json.get("cards", [])
        if card.get("language", "English") == "English"
    ])

    # SPG prices are drawn from the same extracted TCGplayer price file.
    spg_prices = spg_cards.merge(all_prices, on="uuid", how="left")
    spg_prices = spg_prices.rename(columns={
        "foil": "price_foil_usd",
        "nonfoil": "price_nonfoil_usd",
    })

    # Keep only SPG cards actually used by the DFT Play Booster configuration.
    sg_uuids = set(probabilities.loc[
        probabilities["slot_name"].eq("specialGuest"), "uuid"
    ])
    spg_used = spg_prices[spg_prices["uuid"].isin(sg_uuids)].copy()

    # Merge DFT card prices onto all probability rows.
    dft_required = {"uuid", "price_foil_usd", "price_nonfoil_usd"}
    missing = dft_required - set(dft_prices.columns)
    if missing:
        raise ValueError(f"DFT price file missing columns: {sorted(missing)}")

    price_lookup = dft_prices[["uuid", "price_foil_usd", "price_nonfoil_usd"]].copy()
    price_lookup = price_lookup.drop_duplicates("uuid", keep="last")

    data = probabilities.merge(
        price_lookup, on="uuid", how="left", validate="many_to_one"
    )

    # Replace missing DFT prices for Special Guest rows with SPG price records.
    spg_lookup = spg_used[["uuid", "price_foil_usd", "price_nonfoil_usd"]].copy()
    data = data.merge(
        spg_lookup, on="uuid", how="left", suffixes=("", "_spg"),
        validate="many_to_one"
    )
    is_sg = data["slot_name"].eq("specialGuest")
    for col in ["price_foil_usd", "price_nonfoil_usd"]:
        data.loc[is_sg, col] = data.loc[is_sg, f"{col}_spg"]
        data.drop(columns=[f"{col}_spg"], inplace=True)

    # Explicit finish assumptions: foil slots use foil; all other slots,
    # including Special Guest, use nonfoil for the primary/base estimate.
    data["price_type_used"] = np.where(
        data["slot_name"].isin(FOIL_SLOTS), "foil", "nonfoil"
    )
    data["unit_price_usd"] = np.where(
        data["price_type_used"].eq("foil"),
        data["price_foil_usd"], data["price_nonfoil_usd"]
    )
    data["expected_value_contribution_usd"] = (
        data["expected_copies_per_pack"] * data["unit_price_usd"]
    )
    data["price_status"] = np.where(data["unit_price_usd"].notna(),
                                    "priced", "MISSING PRICE")

    # Also calculate the alternative if Special Guest cards are all foil.
    data["special_guest_foil_scenario_usd"] = np.where(
        is_sg,
        data["expected_copies_per_pack"] * data["price_foil_usd"],
        data["expected_value_contribution_usd"]
    )

    card_output = PROCESSED_DIR / "DFT_expected_value_by_card.csv"
    data.to_csv(card_output, index=False)

    slot_summary = (
        data.groupby("slot_name", dropna=False)
        .agg(
            probability_rows=("uuid", "size"),
            priced_rows=("unit_price_usd", "count"),
            missing_price_rows=("unit_price_usd", lambda x: x.isna().sum()),
            expected_copies_per_pack=("expected_copies_per_pack", "sum"),
            known_expected_value_usd=("expected_value_contribution_usd", "sum"),
        )
        .reset_index()
    )
    slot_output = PROCESSED_DIR / "DFT_expected_value_by_slot.csv"
    slot_summary.to_csv(slot_output, index=False)

    priced = data[data["unit_price_usd"].notna()].copy()
    top_cards = (
        priced.groupby(["uuid", "card_name", "rarity"], dropna=False)
        .agg(
            expected_copies_per_pack=("expected_copies_per_pack", "sum"),
            expected_value_contribution_usd=("expected_value_contribution_usd", "sum"),
            slots=("slot_name", lambda x: ", ".join(sorted(set(x)))),
        )
        .reset_index()
        .sort_values("expected_value_contribution_usd", ascending=False)
    )
    top_output = RESULTS_DIR / "DFT_top_value_cards.csv"
    top_cards.head(25).to_csv(top_output, index=False)

    # Special Guest price match audit and finish sensitivity.
    sg_audit = spg_used.copy()
    sg_audit["price_match_status"] = np.where(
        sg_audit["price_nonfoil_usd"].notna() & sg_audit["price_foil_usd"].notna(),
        "Both finishes priced",
        np.where(sg_audit["price_nonfoil_usd"].notna() | sg_audit["price_foil_usd"].notna(),
                 "One finish priced", "No price found")
    )
    sg_audit_output = RESULTS_DIR / "DFT_special_guest_price_audit.csv"
    sg_audit.to_csv(sg_audit_output, index=False)

    known_ev = data["expected_value_contribution_usd"].sum()
    missing = data[data["unit_price_usd"].isna()]
    missing_expected_copies = missing["expected_copies_per_pack"].sum()
    sg_probability = data.loc[is_sg, "expected_copies_per_pack"].sum()

    # This is a sensitivity bound, not an asserted actual finish distribution.
    all_sg_foil_ev = data["special_guest_foil_scenario_usd"].sum()
    sg_nonfoil_ev = data.loc[is_sg, "expected_copies_per_pack"].mul(
        data.loc[is_sg, "price_nonfoil_usd"]
    ).sum()
    sg_foil_ev = data.loc[is_sg, "expected_copies_per_pack"].mul(
        data.loc[is_sg, "price_foil_usd"]
    ).sum()

    profit = known_ev - PACK_PRICE
    roi = profit / PACK_PRICE * 100
    complete = missing.empty
    status = "COMPLETE" if complete else "INCOMPLETE — SOME PRICES MISSING"

    report = [
        "AETHERDRIFT PLAY BOOSTER — EXPECTED VALUE REPORT",
        "=" * 55,
        f"Pack price: ${PACK_PRICE:.2f}",
        f"Calculation status: {status}",
        "",
        f"Expected value (Special Guest nonfoil assumption): ${known_ev:.4f}",
        f"Expected profit/loss: ${profit:.4f}",
        f"Expected ROI: {roi:.2f}%",
        f"Expected value if Special Guest were all foil: ${all_sg_foil_ev:.4f}",
        "",
        f"Special Guest expected slot frequency: {sg_probability:.6f} per pack",
        f"Special Guest nonfoil EV contribution: ${sg_nonfoil_ev:.4f}",
        f"Special Guest foil EV contribution: ${sg_foil_ev:.4f}",
        f"Special Guest cards matched: {len(sg_audit)}",
        f"Special Guest cards with both finishes priced: {(sg_audit['price_match_status'] == 'Both finishes priced').sum()}",
        "",
        f"Probability rows: {len(data):,}",
        f"Priced probability rows: {data['unit_price_usd'].notna().sum():,}",
        f"Missing-price rows: {len(missing):,}",
        f"Expected copies in missing-price rows per pack: {missing_expected_copies:.6f}",
        "",
        "ASSUMPTIONS",
        "- expected_copies_per_pack already includes booster variant probability.",
        "- foil and foilLand slots use foil prices.",
        "- all other slots use nonfoil prices for the main estimate.",
        "- Special Guest finish probability is not supplied; all-nonfoil is the base case.",
        "- an all-foil Special Guest estimate is reported as a sensitivity case.",
        "- missing prices are not treated as $0.",
        "",
        "OUTPUT FILES",
        f"- {card_output}",
        f"- {slot_output}",
        f"- {top_output}",
        f"- {sg_audit_output}",
    ]
    report_path = RESULTS_DIR / "DFT_expected_value_report.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print("\nCalculation complete.")
    print(f"Pack price: ${PACK_PRICE:.2f}")
    print(f"Expected value (SPG nonfoil assumption): ${known_ev:.4f}")
    print(f"Expected profit/loss: ${profit:.4f}")
    print(f"Expected ROI: {roi:.2f}%")
    print(f"Expected value (SPG all-foil sensitivity): ${all_sg_foil_ev:.4f}")
    print(f"Special Guest cards matched: {len(sg_audit)}")
    print(f"Missing-price rows: {len(missing)}")
    print("\nExpected value by slot:")
    print(slot_summary.to_string(index=False))
    print("\nSpecial Guest price audit:")
    print(sg_audit[["spg_card_name", "price_nonfoil_usd", "price_foil_usd",
                    "price_match_status"]].to_string(index=False))
    print("\nSaved outputs:")
    for output in [card_output, slot_output, top_output, sg_audit_output, report_path]:
        print(output)


if __name__ == "__main__":
    main()
