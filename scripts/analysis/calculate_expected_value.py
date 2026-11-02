
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RAW_DIR = PROJECT_DIR / "data" / "raw"
RESULTS_DIR = PROJECT_DIR / "results" / "individual_sets"

FOIL_SLOTS = {"foil", "foilLand"}

DEFAULT_PACK_PRICE = 4.99


# --------------------------------------------------
# Command-line arguments
# --------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Calculate MTG booster expected monetary value."
    )

    parser.add_argument(
        "set_code",
        type=str,
        help="MTG set code, such as DFT."
    )

    parser.add_argument(
        "booster_type",
        type=str,
        help="Booster type, such as play."
    )

    parser.add_argument(
        "--pack-price",
        type=float,
        default=DEFAULT_PACK_PRICE,
        help="Pack purchase price. Defaults to 4.99."
    )

    return parser.parse_args()


# --------------------------------------------------
# Price processing
# --------------------------------------------------

def load_price_pivot(price_file):
    """
    Convert long-format MTGJSON prices into one row per UUID,
    with separate foil and nonfoil price columns.
    """

    prices = pd.read_csv(price_file)

    required = {"uuid", "price"}

    missing = required - set(prices.columns)

    if missing:
        raise ValueError(
            f"Price file missing columns: {sorted(missing)}"
        )

    prices["price"] = pd.to_numeric(
        prices["price"], errors="coerce"
    )

    prices = prices.dropna(
        subset=["uuid", "price"]
    ).copy()

    # Support both the original and expanded price formats.
    if "price_finish" in prices.columns:
        prices["finish"] = prices["price_finish"]
    elif "cardFinish" in prices.columns:
        prices["finish"] = prices["cardFinish"]
    else:
        raise ValueError(
            "Price file needs price_finish or cardFinish."
        )

    prices["finish"] = (
        prices["finish"]
        .astype("string")
        .str.lower()
        .str.strip()
        .replace({
            "normal": "nonfoil",
            "nonfoil": "nonfoil",
            "foil": "foil"
        })
    )

    prices = prices[
        prices["finish"].isin(["foil", "nonfoil"])
    ].copy()

    # Retain the latest available price for each UUID/finish.
    if "date" in prices.columns:
        prices["date"] = pd.to_datetime(
            prices["date"], errors="coerce"
        )

        prices = prices.sort_values("date")

    prices = prices.drop_duplicates(
        ["uuid", "finish"], keep="last"
    )

    pivot = prices.pivot(
        index="uuid",
        columns="finish",
        values="price"
    ).reset_index()

    pivot.columns.name = None

    pivot = pivot.rename(columns={
        "foil": "price_foil_usd",
        "nonfoil": "price_nonfoil_usd"
    })

    for column in ["price_foil_usd", "price_nonfoil_usd"]:
        if column not in pivot.columns:
            pivot[column] = np.nan

    return pivot


# --------------------------------------------------
# Main analysis
# --------------------------------------------------

def main():

    args = parse_arguments()

    set_code = args.set_code.upper()
    booster_type = args.booster_type.lower()
    pack_price = args.pack_price

    if pack_price <= 0:
        raise ValueError("Pack price must be greater than zero.")

    results_dir = RESULTS_DIR / set_code
    tables_dir = results_dir / "tables"
    reports_dir = results_dir / "reports"

    tables_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    probability_file = (
        PROCESSED_DIR
        / f"{set_code}_{booster_type}_card_probabilities.csv"
    )

    matched_price_file = (
        PROCESSED_DIR
        / f"{set_code}_cards_with_prices.csv"
    )

    all_price_file = (
        PROCESSED_DIR
        / f"{set_code}_tcgplayer_prices.csv"
    )

    spg_file = RAW_DIR / "SPG.json"

    for file in [
        probability_file,
        matched_price_file,
        all_price_file,
        spg_file
    ]:
        if not file.exists():
            raise FileNotFoundError(
                f"Could not find required input: {file}"
            )

    print(
        f"Calculating {set_code} {booster_type.title()} "
        "Booster expected value..."
    )

    probabilities = pd.read_csv(probability_file)

    # Use the expanded, matched card-price dataset.
    set_prices = load_price_pivot(matched_price_file)

    # Use the full extracted price dataset for Special Guests.
    all_prices = load_price_pivot(all_price_file)

    required_columns = {
        "uuid",
        "card_name",
        "rarity",
        "slot_name",
        "expected_copies_per_pack"
    }

    missing = required_columns - set(probabilities.columns)

    if missing:
        raise ValueError(
            f"Probability file missing columns: {sorted(missing)}"
        )

    probabilities["expected_copies_per_pack"] = pd.to_numeric(
        probabilities["expected_copies_per_pack"],
        errors="coerce"
    )

    if probabilities["expected_copies_per_pack"].isna().any():
        raise ValueError(
            "Some expected_copies_per_pack values are missing."
        )

    # --------------------------------------------------
    # Special Guest metadata
    # --------------------------------------------------

    with open(spg_file, "r", encoding="utf-8") as file:
        spg_json = json.load(file)

    spg_cards = pd.DataFrame([
        {
            "uuid": card["uuid"],
            "spg_card_name": card["name"],
            "spg_rarity": card.get("rarity"),
            "spg_finishes": ", ".join(
                card.get("finishes", [])
            )
        }
        for card in spg_json.get("cards", [])
        if card.get("uuid")
        and card.get("language", "English") == "English"
    ])

    if spg_cards.empty:
        spg_used = pd.DataFrame(
            columns=[
                "uuid",
                "price_foil_usd",
                "price_nonfoil_usd"
            ]
        )
    else:
        spg_prices = spg_cards.merge(
            all_prices,
            on="uuid",
            how="left",
            validate="one_to_one"
        )

        sg_uuids = set(
            probabilities.loc[
                probabilities["slot_name"].eq("specialGuest"),
                "uuid"
            ]
        )

        spg_used = spg_prices[
            spg_prices["uuid"].isin(sg_uuids)
        ].copy()

    # --------------------------------------------------
    # Match prices to probability rows
    # --------------------------------------------------

    data = probabilities.merge(
        set_prices,
        on="uuid",
        how="left",
        validate="many_to_one"
    )

    # Fill Special Guest prices from the full price snapshot.
    if not spg_used.empty:

        spg_lookup = spg_used[
            ["uuid", "price_foil_usd", "price_nonfoil_usd"]
        ].copy()

        data = data.merge(
            spg_lookup,
            on="uuid",
            how="left",
            suffixes=("", "_spg"),
            validate="many_to_one"
        )

        is_sg = data["slot_name"].eq("specialGuest")

        for column in [
            "price_foil_usd",
            "price_nonfoil_usd"
        ]:
            data.loc[is_sg, column] = data.loc[
                is_sg, f"{column}_spg"
            ].combine_first(
                data.loc[is_sg, column]
            )

            data.drop(
                columns=[f"{column}_spg"],
                inplace=True
            )

    else:
        is_sg = data["slot_name"].eq("specialGuest")

    # --------------------------------------------------
    # Calculate expected monetary value
    # --------------------------------------------------

    data["price_type_used"] = np.where(
        data["slot_name"].isin(FOIL_SLOTS),
        "foil",
        "nonfoil"
    )

    data["unit_price_usd"] = np.where(
        data["price_type_used"].eq("foil"),
        data["price_foil_usd"],
        data["price_nonfoil_usd"]
    )

    data["expected_value_contribution_usd"] = (
        data["expected_copies_per_pack"]
        * data["unit_price_usd"]
    )

    data["price_status"] = np.where(
        data["unit_price_usd"].notna(),
        "priced",
        "MISSING PRICE"
    )

    # Special Guest all-foil sensitivity scenario.
    data["special_guest_foil_scenario_usd"] = np.where(
        is_sg,
        data["expected_copies_per_pack"]
        * data["price_foil_usd"],
        data["expected_value_contribution_usd"]
    )

    # --------------------------------------------------
    # Save card-level results
    # --------------------------------------------------

    card_output = (
        PROCESSED_DIR
        / f"{set_code}_expected_value_by_card.csv"
    )

    data.to_csv(card_output, index=False)

    # --------------------------------------------------
    # Expected value by slot
    # --------------------------------------------------

    slot_summary = (
        data.groupby("slot_name", dropna=False)
        .agg(
            probability_rows=("uuid", "size"),
            priced_rows=("unit_price_usd", "count"),
            missing_price_rows=(
                "unit_price_usd",
                lambda x: x.isna().sum()
            ),
            expected_copies_per_pack=(
                "expected_copies_per_pack", "sum"
            ),
            known_expected_value_usd=(
                "expected_value_contribution_usd", "sum"
            )
        )
        .reset_index()
    )

    slot_output = (
        PROCESSED_DIR
        / f"{set_code}_expected_value_by_slot.csv"
    )

    slot_summary.to_csv(slot_output, index=False)

    # --------------------------------------------------
    # Top expected-value cards
    # --------------------------------------------------

    priced = data[
        data["unit_price_usd"].notna()
    ].copy()

    top_cards = (
        priced.groupby(
            ["uuid", "card_name", "rarity"],
            dropna=False
        )
        .agg(
            expected_copies_per_pack=(
                "expected_copies_per_pack", "sum"
            ),
            expected_value_contribution_usd=(
                "expected_value_contribution_usd", "sum"
            ),
            slots=(
                "slot_name",
                lambda x: ", ".join(sorted(set(x)))
            )
        )
        .reset_index()
        .sort_values(
            "expected_value_contribution_usd",
            ascending=False
        )
    )

    top_output = (
        tables_dir / f"{set_code}_top_value_cards.csv"
    )

    top_cards.head(25).to_csv(top_output, index=False)

    # --------------------------------------------------
    # Special Guest price audit
    # --------------------------------------------------

    sg_audit = spg_used.copy()

    if not sg_audit.empty:

        sg_audit["price_match_status"] = np.where(
            sg_audit["price_nonfoil_usd"].notna()
            & sg_audit["price_foil_usd"].notna(),
            "Both finishes priced",
            np.where(
                sg_audit["price_nonfoil_usd"].notna()
                | sg_audit["price_foil_usd"].notna(),
                "One finish priced",
                "No price found"
            )
        )

    sg_audit_output = (
        tables_dir / f"{set_code}_special_guest_price_audit.csv"
    )

    sg_audit.to_csv(sg_audit_output, index=False)

    # --------------------------------------------------
    # Final financial calculations
    # --------------------------------------------------

    known_ev = data[
        "expected_value_contribution_usd"
    ].sum()

    missing = data[
        data["unit_price_usd"].isna()
    ]

    missing_expected_copies = missing[
        "expected_copies_per_pack"
    ].sum()

    sg_probability = data.loc[
        is_sg, "expected_copies_per_pack"
    ].sum()

    all_sg_foil_ev = data[
        "special_guest_foil_scenario_usd"
    ].sum()

    sg_nonfoil_ev = (
        data.loc[is_sg, "expected_copies_per_pack"]
        * data.loc[is_sg, "price_nonfoil_usd"]
    ).sum()

    sg_foil_ev = (
        data.loc[is_sg, "expected_copies_per_pack"]
        * data.loc[is_sg, "price_foil_usd"]
    ).sum()

    profit = known_ev - pack_price
    roi = profit / pack_price * 100

    complete = missing.empty

    status = (
        "COMPLETE"
        if complete
        else "INCOMPLETE — SOME PRICES MISSING"
    )

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    report = [
        f"{set_code} {booster_type.upper()} BOOSTER "
        "— EXPECTED VALUE REPORT",
        "=" * 55,
        f"Pack price: ${pack_price:.2f}",
        f"Calculation status: {status}",
        "",
        f"Expected value (Special Guest nonfoil assumption): "
        f"${known_ev:.4f}",
        f"Expected profit/loss: ${profit:.4f}",
        f"Expected ROI: {roi:.2f}%",
        f"Expected value if Special Guest were all foil: "
        f"${all_sg_foil_ev:.4f}",
        "",
        f"Special Guest expected frequency: "
        f"{sg_probability:.6f} per pack",
        f"Special Guest nonfoil EV contribution: ${sg_nonfoil_ev:.4f}",
        f"Special Guest foil EV contribution: ${sg_foil_ev:.4f}",
        f"Special Guest cards matched: {len(sg_audit)}",
        "",
        f"Probability rows: {len(data):,}",
        f"Priced probability rows: "
        f"{data['unit_price_usd'].notna().sum():,}",
        f"Missing-price rows: {len(missing):,}",
        f"Expected copies in missing-price rows per pack: "
        f"{missing_expected_copies:.6f}",
        "",
        "ASSUMPTIONS",
        "- Expected copies per pack already includes variant probability.",
        "- Foil and foilLand slots use foil prices.",
        "- All other slots use nonfoil prices for the base estimate.",
        "- Special Guest finish probability is not supplied.",
        "- All-foil Special Guest is a sensitivity scenario.",
        "- Missing prices are not treated as zero.",
        "",
        "OUTPUT FILES",
        f"- {card_output}",
        f"- {slot_output}",
        f"- {top_output}",
        f"- {sg_audit_output}"
    ]

    report_path = (
        reports_dir
        / f"{set_code}_expected_value_report.txt"
    )

    report_path.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    # --------------------------------------------------
    # Terminal output
    # --------------------------------------------------

    print("\nCalculation complete.")

    print(f"Set: {set_code}")
    print(f"Booster type: {booster_type}")
    print(f"Pack price: ${pack_price:.2f}")
    print(f"Calculation status: {status}")

    print(
        f"Expected value (SPG nonfoil assumption): "
        f"${known_ev:.4f}"
    )

    print(f"Expected profit/loss: ${profit:.4f}")
    print(f"Expected ROI: {roi:.2f}%")

    print(
        f"Expected value (SPG all-foil sensitivity): "
        f"${all_sg_foil_ev:.4f}"
    )

    print(f"Special Guest expected frequency: {sg_probability:.6f}")
    print(f"Special Guest cards matched: {len(sg_audit)}")
    print(f"Missing-price rows: {len(missing)}")

    print("\nExpected value by slot:")
    print(slot_summary.to_string(index=False))

    print("\nSaved outputs:")

    for output in [
        card_output,
        slot_output,
        top_output,
        sg_audit_output,
        report_path
    ]:
        print(output)


if __name__ == "__main__":
    main()
