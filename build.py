#!/usr/bin/env python3
"""
Taiwan FDA Food Nutrition Database ETL Pipeline

Converts Taiwan FDA nutrition open data (JSON) into a normalized SQLite database
with FTS5 full-text search support.
"""

import argparse
import json
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import duckdb

FDA_DATA_URL = "https://data.fda.gov.tw/data/opendata/export/20/json"


def download_data(output_dir: Path) -> Path:
    """Download and unzip FDA nutrition data."""
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_path = output_dir / "food_data.zip"
    print(f"Downloading FDA data from {FDA_DATA_URL}...")

    urllib.request.urlretrieve(FDA_DATA_URL, zip_path)
    print(f"Downloaded to {zip_path}")

    print("Extracting ZIP file...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(output_dir)

    # Find the extracted JSON file
    json_files = list(output_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError("No JSON file found in ZIP archive")

    json_path = json_files[0]
    print(f"Extracted: {json_path}")

    # Clean up zip file
    zip_path.unlink()

    return json_path


def load_json(conn: duckdb.DuckDBPyConnection, json_path: Path) -> int:
    """Load JSON data into DuckDB raw_data table."""
    print(f"Loading JSON from {json_path}...")

    conn.execute("""
        CREATE TABLE raw_data AS
        SELECT * FROM read_json_auto(?)
    """, [str(json_path)])

    count = conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
    print(f"Loaded {count} records into raw_data")

    return count


def clean_data(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply data cleaning transformations."""
    print("Cleaning data...")

    # Create cleaned_data table with transformations
    # Column name mapping from actual FDA JSON:
    # 食品分類 -> category
    # 整合編號 -> code
    # 樣品名稱 -> name_zh
    # 樣品英文名稱 -> name_en
    # 俗名 -> alias
    # 內容物描述 -> description
    # 廢棄率 -> waste_rate
    # 每單位重 -> serving_size
    # 分析項分類 -> nutrient_category
    # 分析項 -> nutrient_name
    # 含量單位 -> unit
    # 每100克含量 -> value_raw
    # 樣本數 -> sample_count
    # 標準差 -> std_deviation
    conn.execute("""
        CREATE TABLE cleaned_data AS
        SELECT
            TRIM("整合編號") AS code,
            TRIM("樣品名稱") AS name_zh,
            NULLIF(TRIM("樣品英文名稱"), '') AS name_en,
            TRIM("食品分類") AS category,
            NULLIF(TRIM("俗名"), '') AS alias,
            NULLIF(TRIM("內容物描述"), '') AS description,
            TRY_CAST(
                REPLACE(REPLACE(TRIM("廢棄率"), '%', ''), '　', '')
                AS DOUBLE
            ) AS waste_rate,
            TRY_CAST(
                REPLACE(REPLACE(TRIM("每單位重"), '克', ''), '　', '')
                AS DOUBLE
            ) AS serving_size,
            REPLACE(TRIM("分析項分類"), '  ', ' ') AS nutrient_category,
            TRIM("分析項") AS nutrient_name,
            NULLIF(TRIM("含量單位"), '') AS unit,
            TRIM("每100克含量") AS value_raw,
            TRY_CAST(TRIM("樣本數") AS INTEGER) AS sample_count,
            TRY_CAST(TRIM("標準差") AS DOUBLE) AS std_deviation
        FROM raw_data
    """)

    count = conn.execute("SELECT COUNT(*) FROM cleaned_data").fetchone()[0]
    print(f"Cleaned {count} records")


def create_normalized_tables(conn: duckdb.DuckDBPyConnection) -> dict:
    """Create normalized tables from cleaned data."""
    print("Creating normalized tables...")

    # 1. Create categories table
    conn.execute("""
        CREATE TABLE categories AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY category) AS id,
            category AS name
        FROM (SELECT DISTINCT category FROM cleaned_data WHERE category IS NOT NULL)
    """)

    # 2. Create nutrient_categories table
    conn.execute("""
        CREATE TABLE nutrient_categories AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY nutrient_category) AS id,
            nutrient_category AS name
        FROM (SELECT DISTINCT nutrient_category FROM cleaned_data WHERE nutrient_category IS NOT NULL)
    """)

    # 3. Create foods table
    conn.execute("""
        CREATE TABLE foods AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY code) AS id,
            code,
            name_zh,
            name_en,
            c.id AS category_id,
            alias,
            description,
            waste_rate,
            serving_size
        FROM (
            SELECT DISTINCT
                code, name_zh, name_en, category, alias, description, waste_rate, serving_size
            FROM cleaned_data
        ) d
        LEFT JOIN categories c ON d.category = c.name
    """)

    # 4. Create nutrients table (handle P/M/S ratio split)
    # First, create regular nutrients
    conn.execute("""
        CREATE TABLE nutrients AS
        WITH regular_nutrients AS (
            SELECT DISTINCT
                nutrient_category,
                nutrient_name,
                unit
            FROM cleaned_data
            WHERE nutrient_name != 'P/M/S'
        ),
        pms_nutrients AS (
            SELECT DISTINCT nutrient_category, '脂肪酸比例-多元不飽和(P)' AS nutrient_name, NULL AS unit
            FROM cleaned_data WHERE nutrient_name = 'P/M/S'
            UNION ALL
            SELECT DISTINCT nutrient_category, '脂肪酸比例-單元不飽和(M)' AS nutrient_name, NULL AS unit
            FROM cleaned_data WHERE nutrient_name = 'P/M/S'
            UNION ALL
            SELECT DISTINCT nutrient_category, '脂肪酸比例-飽和(S)' AS nutrient_name, NULL AS unit
            FROM cleaned_data WHERE nutrient_name = 'P/M/S'
        ),
        all_nutrients AS (
            SELECT * FROM regular_nutrients
            UNION ALL
            SELECT * FROM pms_nutrients
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY nutrient_category, nutrient_name) AS id,
            nc.id AS category_id,
            nutrient_name AS name,
            unit
        FROM all_nutrients n
        LEFT JOIN nutrient_categories nc ON n.nutrient_category = nc.name
    """)

    # 5. Create food_nutrients table (handle P/M/S ratio split)
    conn.execute("""
        CREATE TABLE food_nutrients AS
        WITH regular_values AS (
            SELECT
                f.id AS food_id,
                n.id AS nutrient_id,
                TRY_CAST(d.value_raw AS DOUBLE) AS value_per_100g,
                d.sample_count,
                d.std_deviation
            FROM cleaned_data d
            JOIN foods f ON d.code = f.code
            JOIN nutrients n ON d.nutrient_name = n.name
            WHERE d.nutrient_name != 'P/M/S'
        ),
        pms_values AS (
            SELECT
                f.id AS food_id,
                n.id AS nutrient_id,
                TRY_CAST(TRIM(SPLIT_PART(d.value_raw, '/', idx)) AS DOUBLE) AS value_per_100g,
                d.sample_count,
                d.std_deviation
            FROM cleaned_data d
            JOIN foods f ON d.code = f.code
            CROSS JOIN (VALUES (1), (2), (3)) AS t(idx)
            JOIN nutrients n ON n.name = CASE idx
                WHEN 1 THEN '脂肪酸比例-多元不飽和(P)'
                WHEN 2 THEN '脂肪酸比例-單元不飽和(M)'
                WHEN 3 THEN '脂肪酸比例-飽和(S)'
            END
            WHERE d.nutrient_name = 'P/M/S'
              AND d.value_raw IS NOT NULL
              AND d.value_raw LIKE '%/%/%'
        )
        SELECT food_id, nutrient_id, value_per_100g, sample_count, std_deviation
        FROM regular_values
        WHERE nutrient_id IS NOT NULL
        UNION ALL
        SELECT food_id, nutrient_id, value_per_100g, sample_count, std_deviation
        FROM pms_values
        WHERE nutrient_id IS NOT NULL
    """)

    # Get counts
    counts = {
        "categories": conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "nutrient_categories": conn.execute("SELECT COUNT(*) FROM nutrient_categories").fetchone()[0],
        "foods": conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0],
        "nutrients": conn.execute("SELECT COUNT(*) FROM nutrients").fetchone()[0],
        "food_nutrients": conn.execute("SELECT COUNT(*) FROM food_nutrients").fetchone()[0],
    }

    print(f"Created tables: {counts}")
    return counts


def export_sqlite(conn: duckdb.DuckDBPyConnection, output_path: Path) -> None:
    """Export normalized tables to SQLite database."""
    print(f"Exporting to SQLite: {output_path}...")

    # Remove existing database
    if output_path.exists():
        output_path.unlink()

    # Install and load sqlite extension
    conn.execute("INSTALL sqlite; LOAD sqlite;")

    # Attach SQLite database
    conn.execute(f"ATTACH '{output_path}' AS sqlite_db (TYPE sqlite)")

    # Export tables
    tables = ["categories", "nutrient_categories", "foods", "nutrients", "food_nutrients"]
    for table in tables:
        conn.execute(f"CREATE TABLE sqlite_db.{table} AS SELECT * FROM {table}")
        print(f"  Exported {table}")

    conn.execute("DETACH sqlite_db")
    print("  Tables exported")

    # Create indexes using system sqlite3
    print("  Creating indexes...")
    index_sql = """
CREATE INDEX idx_foods_category ON foods(category_id);
CREATE INDEX idx_foods_name ON foods(name_zh);
CREATE INDEX idx_foods_code ON foods(code);
CREATE INDEX idx_nutrients_category ON nutrients(category_id);
CREATE INDEX idx_nutrients_name ON nutrients(name);
CREATE INDEX idx_food_nutrients_food ON food_nutrients(food_id);
CREATE INDEX idx_food_nutrients_nutrient ON food_nutrients(nutrient_id);
"""
    result = subprocess.run(
        ["sqlite3", str(output_path)],
        input=index_sql,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Warning: Index creation failed: {result.stderr}")
    else:
        print("  Created 7 indexes")

    print("SQLite export complete")


def check_fts5_support() -> bool:
    """Check if system sqlite3 supports FTS5 with trigram tokenizer."""
    try:
        result = subprocess.run(
            ["sqlite3", ":memory:", "CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram');"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def create_fts_indexes(db_path: Path) -> bool:
    """Create FTS5 virtual tables using system sqlite3."""
    if not check_fts5_support():
        print("Warning: FTS5 with trigram tokenizer not supported, skipping FTS creation")
        return False

    print("Creating FTS5 indexes...")

    fts_sql = """
-- Create FTS5 virtual tables with trigram tokenizer
CREATE VIRTUAL TABLE foods_fts USING fts5(
    name_zh,
    name_en,
    alias,
    content='foods',
    content_rowid='id',
    tokenize='trigram'
);

CREATE VIRTUAL TABLE nutrients_fts USING fts5(
    name,
    content='nutrients',
    content_rowid='id',
    tokenize='trigram'
);

-- Populate FTS tables
INSERT INTO foods_fts(rowid, name_zh, name_en, alias)
SELECT id, name_zh, COALESCE(name_en, ''), COALESCE(alias, '') FROM foods;

INSERT INTO nutrients_fts(rowid, name)
SELECT id, name FROM nutrients;
"""

    result = subprocess.run(
        ["sqlite3", str(db_path)],
        input=fts_sql,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Warning: FTS creation failed: {result.stderr}")
        return False

    print("  Created foods_fts and nutrients_fts")
    return True


def generate_report(
    db_path: Path,
    input_file: str,
    total_records: int,
    counts: dict,
    fts_enabled: bool,
    report_path: Path,
) -> None:
    """Generate ETL report JSON file."""
    print(f"Generating report: {report_path}...")

    # Count P/M/S records
    result = subprocess.run(
        ["sqlite3", str(db_path), "SELECT COUNT(*) FROM nutrients WHERE name LIKE '脂肪酸比例%'"],
        capture_output=True,
        text=True,
    )
    pms_count = int(result.stdout.strip()) if result.returncode == 0 else 0

    report = {
        "input_file": input_file,
        "counts": {
            "total_records": total_records,
            "foods": counts["foods"],
            "categories": counts["categories"],
            "nutrient_categories": counts["nutrient_categories"],
            "nutrients": counts["nutrients"],
            "food_nutrients": counts["food_nutrients"],
        },
        "pms_records_processed": pms_count,
        "fts_enabled": fts_enabled,
        "warnings": [],
    }

    if not fts_enabled:
        report["warnings"].append("FTS5 not available - full-text search disabled")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Report generated")


def main():
    parser = argparse.ArgumentParser(
        description="Taiwan FDA Food Nutrition Database ETL Pipeline"
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output SQLite database path (e.g., nutrition.db)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input JSON file path (skip download if provided)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Output report JSON path (e.g., report.json)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory for downloaded data (default: data/)",
    )

    args = parser.parse_args()

    # Download or use existing JSON
    if args.input:
        json_path = args.input
        if not json_path.exists():
            raise FileNotFoundError(f"Input file not found: {json_path}")
    else:
        json_path = download_data(args.data_dir)

    # Create in-memory DuckDB connection
    conn = duckdb.connect(":memory:")

    try:
        # ETL pipeline
        total_records = load_json(conn, json_path)
        clean_data(conn)
        counts = create_normalized_tables(conn)
        export_sqlite(conn, args.output)

        # Create FTS indexes (using system sqlite3)
        fts_enabled = create_fts_indexes(args.output)

        # Generate report
        if args.report:
            generate_report(
                args.output,
                str(json_path),
                total_records,
                counts,
                fts_enabled,
                args.report,
            )

        print(f"\nETL complete! Database: {args.output}")
        print(f"  Foods: {counts['foods']}")
        print(f"  Nutrients: {counts['nutrients']}")
        print(f"  FTS enabled: {fts_enabled}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
