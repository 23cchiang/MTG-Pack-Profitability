
"""
Project-wide validation for MTG Pack Profitability.

Run from the project root:

    python3 scripts/validation/validate_project.py

Checks:
    - Required files exist
    - Booster variant probabilities sum to 1
    - Card probabilities within each variant and slot sum to 1
    - Expected pack composition equals 14 cards
    - Card price coverage
    - Expected-value calculations
    - Monte Carlo simulation accuracy
    - Cross-set comparison outputs

Output:
    results/project_validation_report.txt
"""

from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SETS = {
    "DFT": {
        "name": "Aetherdrift",
        "pack_price": 4.99,
        "simulation_column": "pack_value_spg_nonfoil_usd",
        "simulation_scenario": "SPG nonfoil baseline",
    },
    "FIN": {
        "name": "Final Fantasy",
        "pack_price": 9.34,
        "simulation_column": "pack_value_baseline_usd",
        "simulation_scenario": "Baseline",
    },
}

TOLERANCE = 0.05
PROBABILITY_TOLERANCE = 0.000001
EXPECTED_PACK_SIZE = 14

results = []


def record(status, check, details):
    results.append({
        "status": status,
        "check": check,
        "details": str(details),
    })

    print(f"[{status}] {check}: {details}")


def check_file(path, description):
    if path.exists():
        record("PASS", description, "File exists.")
        return True

    record("FAIL", description, f"Missing file: {path}")
    return False


def check_close(actual, expected, tolerance):
    return abs(actual - expected) <= tolerance


def validate_set(set_code, config):
    print("\n" + "=" * 65)
    print(f"VALIDATING {config['name'].upper()} ({set_code})")
    print("=" * 65)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    tables_dir = (
        PROJECT_ROOT
        / "results"
        / "individual_sets"
        / set_code
        / "tables"
    )

    # Required input files.
    probability_path = (
        processed_dir
        / f"{set_code}_play_card_probabilities.csv"
    )

    slot_summary_path = (
        processed_dir
        / f"{set_code}_play_slot_summary.csv"
    )

    expected_card_path = (
        processed_dir
        / f"{set_code}_expected_value_by_card.csv"
    )

    expected_slot_path = (
        processed_dir
        / f"{set_code}_expected_value_by_slot.csv"
    )

    price_path = (
        processed_dir
        / f"{set_code}_tcgplayer_prices.csv"
    )

    simulation_summary_path = (
        tables_dir
        / f"{set_code}_monte_carlo_summary.csv"
    )

    simulation_values_path = (
        tables_dir
        / f"{set_code}_monte_carlo_pack_values.csv"
    )

    required_files = [
        (probability_path, "Booster probability data"),
        (slot_summary_path, "Booster slot summary"),
        (expected_card_path, "Expected value by card"),
        (expected_slot_path, "Expected value by slot"),
        (price_path, "TCGplayer price data"),
        (simulation_summary_path, "Monte Carlo summary"),
        (simulation_values_path, "Monte Carlo pack values"),
    ]

    missing_files = []

    for path, description in required_files:
        if not check_file(path, description):
            missing_files.append(description)

    if missing_files:
        record(
            "FAIL",
            f"{set_code} data validation",
            "Cannot complete checks because required files are missing."
        )
        return

    # Load data.
    probabilities = pd.read_csv(probability_path)
    slots = pd.read_csv(slot_summary_path)
    expected_cards = pd.read_csv(expected_card_path)
    expected_slots = pd.read_csv(expected_slot_path)
    prices = pd.read_csv(price_path)
    simulation_summary = pd.read_csv(simulation_summary_path)
    simulation_values = pd.read_csv(simulation_values_path)

    # ---------------------------------------------------------
    # 1. Booster variant probabilities
    # ---------------------------------------------------------

    variants = probabilities[
        ["variant_number", "variant_probability"]
    ].drop_duplicates()

    variant_total = variants["variant_probability"].sum()

    if check_close(
        variant_total,
        1.0,
        PROBABILITY_TOLERANCE
    ):
        record(
            "PASS",
            f"{set_code} variant probabilities",
            f"Sum = {variant_total:.8f}"
        )
    else:
        record(
            "FAIL",
            f"{set_code} variant probabilities",
            f"Expected 1.0, found {variant_total:.8f}"
        )

    # ---------------------------------------------------------
    # 2. Card probabilities within each variant and slot
    # ---------------------------------------------------------

    sheet_totals = (
        probabilities
        .groupby(["variant_number", "slot_name"])
        ["probability_within_sheet"]
        .sum()
    )

    invalid_sheets = sheet_totals[
        (sheet_totals - 1.0).abs() > PROBABILITY_TOLERANCE
    ]

    if invalid_sheets.empty:
        record(
            "PASS",
            f"{set_code} card sheet probabilities",
            f"All {len(sheet_totals)} variant-slot groups sum to 1."
        )
    else:
        record(
            "FAIL",
            f"{set_code} card sheet probabilities",
            f"{len(invalid_sheets)} groups do not sum to 1."
        )

    # ---------------------------------------------------------
    # 3. Expected pack composition
    # ---------------------------------------------------------

    total_cards = slots["expected_cards_per_pack"].sum()

    if check_close(
        total_cards,
        EXPECTED_PACK_SIZE,
        PROBABILITY_TOLERANCE
    ):
        record(
            "PASS",
            f"{set_code} pack composition",
            f"Expected cards per pack = {total_cards:.6f}"
        )
    else:
        record(
            "FAIL",
            f"{set_code} pack composition",
            f"Expected {EXPECTED_PACK_SIZE}, found {total_cards:.6f}"
        )

    # ---------------------------------------------------------
    # 4. Expected copies by slot
    # ---------------------------------------------------------

    probability_slot_totals = (
        probabilities
        .groupby("slot_name")["expected_copies_per_pack"]
        .sum()
        .sort_index()
    )

    summary_slot_totals = (
        slots
        .set_index("slot_name")["expected_cards_per_pack"]
        .sort_index()
    )

    aligned_probability, aligned_summary = (
        probability_slot_totals.align(
            summary_slot_totals,
            join="outer",
            fill_value=0
        )
    )

    slot_difference = (
        aligned_probability - aligned_summary
    ).abs().max()

    if slot_difference <= PROBABILITY_TOLERANCE:
        record(
            "PASS",
            f"{set_code} slot quantity consistency",
            "Probability data matches slot summary."
        )
    else:
        record(
            "FAIL",
            f"{set_code} slot quantity consistency",
            f"Maximum difference = {slot_difference:.8f}"
        )

    # ---------------------------------------------------------
    # 5. Price coverage
    # ---------------------------------------------------------

    if "price_status" in expected_cards.columns:
        missing_prices = (
            expected_cards["price_status"]
            .astype(str)
            .str.lower()
            .ne("priced")
            .sum()
        )

        if missing_prices == 0:
            record(
                "PASS",
                f"{set_code} price coverage",
                "All expected-value card rows are priced."
            )
        else:
            record(
                "WARNING",
                f"{set_code} price coverage",
                f"{missing_prices} rows are not marked priced."
            )
    else:
        record(
            "WARNING",
            f"{set_code} price coverage",
            "price_status column is missing."
        )

    if "missing_price_rows" in expected_slots.columns:
        missing_slot_prices = expected_slots[
            "missing_price_rows"
        ].sum()

        if missing_slot_prices == 0:
            record(
                "PASS",
                f"{set_code} slot price coverage",
                "No missing price rows in slot summary."
            )
        else:
            record(
                "WARNING",
                f"{set_code} slot price coverage",
                f"{missing_slot_prices} missing price rows."
            )

    # ---------------------------------------------------------
    # 6. Analytical expected value
    # ---------------------------------------------------------

    analytical_ev = expected_cards[
        "expected_value_contribution_usd"
    ].sum()

    slot_ev = expected_slots[
        "known_expected_value_usd"
    ].sum()

    if check_close(analytical_ev, slot_ev, TOLERANCE):
        record(
            "PASS",
            f"{set_code} analytical expected value",
            f"Card total ${analytical_ev:.4f}; "
            f"slot total ${slot_ev:.4f}"
        )
    else:
        record(
            "FAIL",
            f"{set_code} analytical expected value",
            f"Card total ${analytical_ev:.4f}; "
            f"slot total ${slot_ev:.4f}"
        )

    # ---------------------------------------------------------
    # 7. Monte Carlo scenario
    # ---------------------------------------------------------

    scenario = simulation_summary[
        simulation_summary["scenario"]
        == config["simulation_scenario"]
    ]

    if scenario.empty:
        record(
            "FAIL",
            f"{set_code} Monte Carlo scenario",
            f"Scenario '{config['simulation_scenario']}' not found."
        )
        return

    simulation_mean = float(
        scenario.loc[
            scenario["metric"] == "mean_pack_value_usd",
            "value"
        ].iloc[0]
    )

    simulated_packs = int(
        scenario.loc[
            scenario["metric"] == "packs_simulated",
            "value"
        ].iloc[0]
    )

    difference = abs(analytical_ev - simulation_mean)

    if difference <= TOLERANCE:
        record(
            "PASS",
            f"{set_code} analytical vs. simulation",
            f"Analytical ${analytical_ev:.4f}; "
            f"simulated ${simulation_mean:.4f}; "
            f"difference ${difference:.4f}"
        )
    else:
        record(
            "WARNING",
            f"{set_code} analytical vs. simulation",
            f"Analytical ${analytical_ev:.4f}; "
            f"simulated ${simulation_mean:.4f}; "
            f"difference ${difference:.4f}"
        )

    if simulated_packs == 200000:
        record(
            "PASS",
            f"{set_code} simulation count",
            f"{simulated_packs:,} packs simulated."
        )
    else:
        record(
            "WARNING",
            f"{set_code} simulation count",
            f"Expected 200,000; found {simulated_packs:,}."
        )

    # ---------------------------------------------------------
    # 8. Simulation output integrity
    # ---------------------------------------------------------

    value_column = config["simulation_column"]

    if value_column not in simulation_values.columns:
        record(
            "FAIL",
            f"{set_code} simulation value column",
            f"Missing column: {value_column}"
        )
    else:
        value_count = simulation_values[value_column].notna().sum()

        if value_count == simulated_packs:
            record(
                "PASS",
                f"{set_code} simulation output integrity",
                f"{value_count:,} pack values available."
            )
        else:
            record(
                "FAIL",
                f"{set_code} simulation output integrity",
                f"Expected {simulated_packs:,}; found {value_count:,}."
            )

    # ---------------------------------------------------------
    # 9. Pack cost and expected profit/loss
    # ---------------------------------------------------------

    expected_profit = analytical_ev - config["pack_price"]

    record(
        "PASS",
        f"{set_code} expected profit/loss",
        f"Expected value ${analytical_ev:.4f} - "
        f"pack cost ${config['pack_price']:.2f} "
        f"= ${expected_profit:.4f}"
    )


def validate_comparison_outputs():
    print("\n" + "=" * 65)
    print("VALIDATING CROSS-SET COMPARISON")
    print("=" * 65)

    comparison_dir = PROJECT_ROOT / "results" / "comparisons"

    required_outputs = [
        comparison_dir / "set_comparison.csv",
        comparison_dir / "multi_pack_comparison.csv",
        comparison_dir / "set_comparison_report.txt",
        comparison_dir / "figures" / "set_value_vs_cost.png",
        comparison_dir / "figures" / "market_price_sensitivity.png",
    ]

    for path in required_outputs:
        check_file(
            path,
            f"Comparison output: {path.name}"
        )

    comparison_path = comparison_dir / "set_comparison.csv"

    if comparison_path.exists():
        comparison = pd.read_csv(comparison_path)

        found_sets = set(comparison["set_code"].unique())
        expected_sets = {"DFT", "FIN"}

        if found_sets == expected_sets:
            record(
                "PASS",
                "Cross-set comparison contents",
                "Both DFT and FIN are included."
            )
        else:
            record(
                "FAIL",
                "Cross-set comparison contents",
                f"Expected {expected_sets}; found {found_sets}."
            )

        baseline = comparison[
            comparison["market_price_decline_percent"] == 0
        ]

        if len(baseline) == 2:
            record(
                "PASS",
                "Cross-set baseline scenarios",
                "Exactly two baseline rows found."
            )
        else:
            record(
                "FAIL",
                "Cross-set baseline scenarios",
                f"Expected 2 rows; found {len(baseline)}."
            )


def write_report():
    report_path = (
        PROJECT_ROOT
        / "results"
        / "project_validation_report.txt"
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)

    passed = sum(r["status"] == "PASS" for r in results)
    warnings = sum(r["status"] == "WARNING" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)

    with report_path.open("w", encoding="utf-8") as f:
        f.write("MTG PACK PROFITABILITY PROJECT VALIDATION\n")
        f.write("=" * 65 + "\n\n")

        f.write("VALIDATION SUMMARY\n")
        f.write("-" * 30 + "\n")
        f.write(f"Passed: {passed}\n")
        f.write(f"Warnings: {warnings}\n")
        f.write(f"Failed: {failed}\n\n")

        f.write("DETAILED RESULTS\n")
        f.write("-" * 30 + "\n")

        for result in results:
            f.write(
                f"[{result['status']}] "
                f"{result['check']}\n"
                f"    {result['details']}\n\n"
            )

        f.write("\nFINAL STATUS\n")
        f.write("-" * 30 + "\n")

        if failed:
            f.write("VALIDATION FAILED: Review failed checks.\n")
        elif warnings:
            f.write("VALIDATION PASSED WITH WARNINGS.\n")
        else:
            f.write("ALL VALIDATION CHECKS PASSED.\n")

    print(f"\nValidation report saved to:\n{report_path}")


def main():
    print("=" * 65)
    print("MTG PACK PROFITABILITY PROJECT VALIDATION")
    print("=" * 65)

    for set_code, config in SETS.items():
        validate_set(set_code, config)

    validate_comparison_outputs()

    write_report()

    passed = sum(r["status"] == "PASS" for r in results)
    warnings = sum(r["status"] == "WARNING" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)

    print("\n" + "=" * 65)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 65)
    print(f"Passed:   {passed}")
    print(f"Warnings: {warnings}")
    print(f"Failed:   {failed}")

    if failed:
        print("\nVALIDATION FAILED. Review the report.")
    elif warnings:
        print("\nVALIDATION PASSED WITH WARNINGS.")
    else:
        print("\nALL VALIDATION CHECKS PASSED!")


if __name__ == "__main__":
    main()
