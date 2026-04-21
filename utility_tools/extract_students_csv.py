#!/usr/bin/env python3
"""
Extract students.csv from the latest full_load.iqr for scanner deployment.

Downloads the latest encrypted student data from the IQRight API, decrypts it
using offline.key, and writes a slim CSV with only the columns the scanner
needs. The resulting students.csv serves BOTH the fuzzy name search
(StudentMatcher) and the validation mode lookup — one file, one source of
truth, guaranteed consistency.

Prerequisites (run on a computer with network access to the IQRight API):
    - data/offline.key present (for decryption)
    - data/credentials.iqr + data/credentials.key present (for API auth)
    - utils/config.py configured for the target facility (IDFACILITY)
    - Python dependencies from configs/requirements.server.txt

Usage:
    # From project root, with LOCAL mode active so paths resolve to ./data:
    LOCAL=TRUE python utility_tools/extract_students_csv.py

    # Custom output location:
    LOCAL=TRUE python utility_tools/extract_students_csv.py --output /tmp/students.csv

    # Skip API call, just re-extract from an already-downloaded full_load.iqr:
    LOCAL=TRUE python utility_tools/extract_students_csv.py --no-download

Output columns (in order):
    FirstName, LastName, ChildName, DeviceID, ClassCode,
    HierarchyLevel1, HierarchyLevel2

Consumed by:
    - StudentMatcher (fuzzy search):  FirstName, LastName, DeviceID, ClassCode
    - Validation mode lookup:         ChildName, DeviceID, HierarchyLevel1,
                                       HierarchyLevel2
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path so `utils.*` imports work when the script is
# launched from any directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Columns extracted from full_load.iqr into students.csv
OUTPUT_COLUMNS = [
    "FirstName",
    "LastName",
    "ChildName",
    "DeviceID",
    "ClassCode",
    "HierarchyLevel1",
    "HierarchyLevel2",
]


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_dataframe(skip_download: bool):
    """Load the full_load.iqr DataFrame via OfflineData (downloads if needed)."""
    if skip_download:
        # Use decrypt_file directly without triggering the download chain
        from utils.config import OFFLINE_FULL_LOAD_FILENAME, LORASERVICE_PATH
        from utils.offline_data import OfflineData

        basepath = Path(LORASERVICE_PATH)
        filepath = basepath / "data"
        datafile = filepath / OFFLINE_FULL_LOAD_FILENAME
        if not datafile.exists():
            logging.error(f"No existing full_load.iqr at {datafile}. Run without --no-download first.")
            return None

        # Use a bare decrypt without invoking __init__ side effects
        od = OfflineData.__new__(OfflineData)
        od._basepath = basepath
        od._filepath = filepath
        df = od.decrypt_file(datafile=datafile)
        if df is None:
            logging.error(f"Failed to decrypt {datafile}")
        return df

    from utils.offline_data import OfflineData

    logging.info("Initializing OfflineData (will download if new version available)...")
    od = OfflineData()
    df = od.getAppUsers()
    return df


def _extract_and_write(df, output_path: Path) -> bool:
    """Extract the needed columns and write to CSV."""
    if df is None or df.empty:
        logging.error("No data to extract (DataFrame is empty or None)")
        return False

    missing = [c for c in OUTPUT_COLUMNS if c not in df.columns]
    if missing:
        logging.error(f"Missing columns in source data: {missing}")
        logging.error(f"Available columns: {list(df.columns)}")
        return False

    slim = df[OUTPUT_COLUMNS].copy()

    # Normalize types — DeviceID as string, trim whitespace on name fields
    slim["DeviceID"] = slim["DeviceID"].astype(str).str.strip()
    for col in ("FirstName", "LastName", "ChildName", "HierarchyLevel1", "HierarchyLevel2"):
        slim[col] = slim[col].astype(str).str.strip()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    slim.to_csv(output_path, index=False)
    logging.info(f"Wrote {len(slim)} rows to {output_path}")

    # Summary stats
    unique_devices = slim["DeviceID"].nunique()
    unique_teachers = slim["HierarchyLevel2"].nunique()
    unique_grades = slim["HierarchyLevel1"].nunique()
    logging.info(
        f"Summary: {unique_devices} unique DeviceIDs, "
        f"{unique_teachers} teachers, {unique_grades} grades"
    )
    return True


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output", "-o",
        default="data/students.csv",
        help="Output CSV path (default: data/students.csv)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip API download; re-extract from existing local full_load.iqr",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    # If LOCAL is not set, warn — paths default to /home/iqright/data on the server
    if os.getenv("LOCAL", "FALSE") != "TRUE":
        logging.warning(
            "LOCAL env var is not set to TRUE. Paths will resolve to server defaults "
            "(/home/iqright/data). Re-run with `LOCAL=TRUE` if you want ./data."
        )

    df = _load_dataframe(skip_download=args.no_download)
    if df is None:
        logging.error("Failed to load student data")
        sys.exit(1)

    output_path = Path(args.output).resolve()
    success = _extract_and_write(df, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
