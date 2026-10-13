
from pathlib import Path
import pandas as pd

# --------------------------------------------------
# File paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
CSV_FILE = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "slot_probabilities.csv"
)

EXPECTED_SETS = {
    "FRA", "HOB", "MSH", "SOS", "TMT", "ECL",
    "TLA", "SPM", "EOE", "FIN", "TDM", "DFT"
}

REQUIRED_COLUMNS = [
    "Set",
    "Booster Slot",
    "Card Category",
    "Rarity",
    "Probability (%)",
    "Treatment",
    "Source / Notes",
]

# --------------------------------------------------
# Load data
# --------------------------------------------------

print("=" * 65)
print("MTG SLOT PROBABILITY AUDIT")
print("=" * 65)

if not CSV_FILE.exists():
    raise FileNotFoundError(
        f"Could not find the CSV file:\n{CSV_FILE}"
    )


df = pd.read_csv(
    CSV_FILE,
    dtype=str,
    skiprows=1
).fillna("")


# Remove accidental whitespace from text fields
for column in df.columns:
    df[column] = df[column].str.strip()

print(f"\nFile: {CSV_FILE}")
print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# --------------------------------------------------
# 1. Check required columns
# --------------------------------------------------

print("\n1. REQUIRED COLUMNS")
print("-" * 45)

missing_columns = [
    column
    for column in REQUIRED_COLUMNS
    if column not in df.columns
]

if missing_columns:
    print("MISSING COLUMNS:", missing_columns)
    raise ValueError(
        "Fix the column headers before continuing."
    )

print("All required columns are present.")

# --------------------------------------------------
# 2. Check set coverage
# --------------------------------------------------

print("\n2. SET COVERAGE")
print("-" * 45)

found_sets = set(df["Set"].str.upper())
missing_sets = EXPECTED_SETS - found_sets
unexpected_sets = found_sets - EXPECTED_SETS

print("Sets found:", sorted(found_sets))
print("Missing sets:", sorted(missing_sets))
print("Unexpected set codes:", sorted(unexpected_sets))

# --------------------------------------------------
# 3. Check blank fields
# --------------------------------------------------

print("\n3. BLANK REQUIRED FIELDS")
print("-" * 45)

for column in REQUIRED_COLUMNS:
    blank_count = (
        df[column].eq("").sum()
    )
    print(f"{column}: {blank_count} blank rows")

# --------------------------------------------------
# 4. Check duplicate rows
# --------------------------------------------------

print("\n4. DUPLICATE ROWS")
print("-" * 45)

duplicate_count = df.duplicated(
    subset=REQUIRED_COLUMNS
).sum()

print("Exact duplicate rows:", duplicate_count)

# --------------------------------------------------
# 5. Parse probability values
# --------------------------------------------------

print("\n5. PROBABILITY FORMATS")
print("-" * 45)

def parse_probability(value):
    """
    Return a numeric percentage when possible.
    Preserve bounds and conditional values as unknown.
    """
    value = str(value).strip()

    if value == "":
        return None

    if value.lower() in {
        "conditional",
        "any",
        "n/a",
        "na",
        "unknown",
    }:
        return None

    if value.startswith("<"):
        return None

    try:
        number = float(value)

        if number < 0 or number > 100:
            return None

        return number

    except ValueError:
        return None


df["parsed_probability"] = df[
    "Probability (%)"
].apply(parse_probability)

unknown_values = df[
    df["parsed_probability"].isna()
]

print(
    "Rows with conditional, bounded, blank, "
    "or unrecognized probabilities:",
    len(unknown_values),
)

if not unknown_values.empty:
    print(
        unknown_values[
            ["Set", "Booster Slot", "Card Category",
             "Probability (%)"]
        ].to_string(index=False)
    )

# --------------------------------------------------
# 6. Summarize numeric percentages by slot
# --------------------------------------------------

print("\n6. NUMERIC SLOT TOTALS")
print("-" * 45)

numeric_rows = df[
    df["parsed_probability"].notna()
].copy()

slot_totals = (
    numeric_rows
    .groupby(["Set", "Booster Slot"])
    ["parsed_probability"]
    .agg(["sum", "count"])
    .reset_index()
)

slot_totals = slot_totals.rename(
    columns={
        "sum": "Numeric percentage total",
        "count": "Numeric rows",
    }
)

print(
    slot_totals.to_string(
        index=False,
        formatters={
            "Numeric percentage total": "{:.4f}".format
        },
    )
)

print(
    "\nIMPORTANT: These totals are diagnostic only."
)
print(
    "They are not final pass/fail checks because "
    "some slots include conditional outcomes, "
    "probability bounds, replacement events, "
    "or multiple treatments."
)

# --------------------------------------------------
# 7. Check suspicious probability text
# --------------------------------------------------

print("\n7. UNRECOGNIZED PROBABILITY VALUES")
print("-" * 45)

recognized_text = {
    "conditional",
    "any",
    "n/a",
    "na",
    "unknown",
}

def is_recognized(value):
    value = str(value).strip()

    if value.lower() in recognized_text:
        return True

    if value.startswith("<"):
        try:
            bound = float(value[1:])
            return 0 <= bound <= 100
        except ValueError:
            return False

    try:
        number = float(value)
        return 0 <= number <= 100
    except ValueError:
        return False


suspicious = df[
    ~df["Probability (%)"].apply(is_recognized)
]

if suspicious.empty:
    print("No unrecognized probability formats found.")
else:
    print(
        suspicious[
            ["Set", "Booster Slot", "Probability (%)"]
        ].to_string(index=False)
    )

# --------------------------------------------------
# Finish
# --------------------------------------------------

print("\n" + "=" * 65)
print("AUDIT COMPLETE")
print("No source CSV or Google Sheet was modified.")
print("=" * 65)
