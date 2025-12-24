#!/usr/bin/env python3
"""
Taiwan FDA Food Nutrition Database Validation Script

Validates the generated SQLite database against expected criteria.
"""

import argparse
import sqlite3
import sys
from pathlib import Path


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_counts(conn: sqlite3.Connection) -> list[str]:
    """Validate record counts."""
    errors = []

    # Food count > 2000
    food_count = conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
    if food_count <= 2000:
        errors.append(f"Food count {food_count} should be > 2000")
    else:
        print(f"  Foods: {food_count} (> 2000)")

    # Category count = 18
    category_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if category_count != 18:
        errors.append(f"Category count {category_count} should be 18")
    else:
        print(f"  Categories: {category_count} (= 18)")

    # Nutrient category count = 11
    nutrient_category_count = conn.execute(
        "SELECT COUNT(*) FROM nutrient_categories"
    ).fetchone()[0]
    if nutrient_category_count != 11:
        errors.append(f"Nutrient category count {nutrient_category_count} should be 11")
    else:
        print(f"  Nutrient categories: {nutrient_category_count} (= 11)")

    # Nutrient count > 100
    nutrient_count = conn.execute("SELECT COUNT(*) FROM nutrients").fetchone()[0]
    if nutrient_count <= 100:
        errors.append(f"Nutrient count {nutrient_count} should be > 100")
    else:
        print(f"  Nutrients: {nutrient_count} (> 100)")

    return errors


def validate_referential_integrity(conn: sqlite3.Connection) -> list[str]:
    """Validate foreign key relationships."""
    errors = []

    # No orphan foods
    orphan_foods = conn.execute("""
        SELECT COUNT(*) FROM foods
        WHERE category_id NOT IN (SELECT id FROM categories)
    """).fetchone()[0]
    if orphan_foods > 0:
        errors.append(f"Found {orphan_foods} foods with invalid category_id")
    else:
        print("  No orphan foods")

    # No orphan nutrients
    orphan_nutrients = conn.execute("""
        SELECT COUNT(*) FROM nutrients
        WHERE category_id NOT IN (SELECT id FROM nutrient_categories)
    """).fetchone()[0]
    if orphan_nutrients > 0:
        errors.append(f"Found {orphan_nutrients} nutrients with invalid category_id")
    else:
        print("  No orphan nutrients")

    # No orphan food_nutrients
    orphan_fn_food = conn.execute("""
        SELECT COUNT(*) FROM food_nutrients
        WHERE food_id NOT IN (SELECT id FROM foods)
    """).fetchone()[0]
    orphan_fn_nutrient = conn.execute("""
        SELECT COUNT(*) FROM food_nutrients
        WHERE nutrient_id NOT IN (SELECT id FROM nutrients)
    """).fetchone()[0]
    if orphan_fn_food > 0:
        errors.append(f"Found {orphan_fn_food} food_nutrients with invalid food_id")
    if orphan_fn_nutrient > 0:
        errors.append(
            f"Found {orphan_fn_nutrient} food_nutrients with invalid nutrient_id"
        )
    if orphan_fn_food == 0 and orphan_fn_nutrient == 0:
        print("  No orphan food_nutrients")

    return errors


def validate_pms_nutrients(conn: sqlite3.Connection) -> list[str]:
    """Validate P/M/S ratio nutrients exist."""
    errors = []

    pms_nutrients = conn.execute("""
        SELECT name FROM nutrients
        WHERE name LIKE '脂肪酸比例%'
        ORDER BY name
    """).fetchall()

    expected = [
        "脂肪酸比例-單元不飽和(M)",
        "脂肪酸比例-多元不飽和(P)",
        "脂肪酸比例-飽和(S)",
    ]

    found = [row[0] for row in pms_nutrients]

    for exp in expected:
        if exp not in found:
            errors.append(f"Missing P/M/S nutrient: {exp}")

    if not errors:
        print(f"  P/M/S nutrients: {len(found)} found")

    return errors


def validate_data_quality(conn: sqlite3.Connection) -> list[str]:
    """Validate data quality metrics."""
    errors = []

    # NULL ratio in calories < 10%
    total_foods = conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
    # Count foods that have a non-NULL calorie value
    foods_with_calories = conn.execute("""
        SELECT COUNT(DISTINCT f.id)
        FROM foods f
        JOIN food_nutrients fn ON f.id = fn.food_id
        JOIN nutrients n ON fn.nutrient_id = n.id
        WHERE n.name = '熱量' AND fn.value_per_100g IS NOT NULL
    """).fetchone()[0]
    null_calories = total_foods - foods_with_calories
    null_ratio = null_calories / total_foods * 100 if total_foods > 0 else 0
    if null_ratio >= 10:
        errors.append(f"NULL ratio in calories {null_ratio:.1f}% should be < 10%")
    else:
        print(f"  Calorie NULL ratio: {null_ratio:.1f}% (< 10%)")

    # No negative nutrient values
    negative_values = conn.execute("""
        SELECT COUNT(*) FROM food_nutrients
        WHERE value_per_100g < 0
    """).fetchone()[0]
    if negative_values > 0:
        errors.append(f"Found {negative_values} negative nutrient values")
    else:
        print("  No negative nutrient values")

    # No duplicate food codes
    duplicate_codes = conn.execute("""
        SELECT code, COUNT(*) as cnt
        FROM foods
        GROUP BY code
        HAVING cnt > 1
    """).fetchall()
    if duplicate_codes:
        errors.append(f"Found {len(duplicate_codes)} duplicate food codes")
    else:
        print("  No duplicate food codes")

    return errors


def validate_fts(conn: sqlite3.Connection) -> list[str]:
    """Validate FTS5 tables if they exist."""
    errors = []

    # Check if FTS tables exist
    fts_tables = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name LIKE '%_fts'
    """).fetchall()

    if not fts_tables:
        print("  FTS tables: not present (optional)")
        return errors

    fts_names = [row[0] for row in fts_tables]
    expected_fts = ["foods_fts", "nutrients_fts"]

    for exp in expected_fts:
        if exp not in fts_names:
            errors.append(f"Missing FTS table: {exp}")

    if not errors:
        print(f"  FTS tables: {len(fts_names)} found ({', '.join(fts_names)})")

        # Test FTS search (trigram tokenizer requires 3+ characters for MATCH)
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM nutrients_fts WHERE nutrients_fts MATCH '維生素'"
            ).fetchone()[0]
            print(f"    FTS MATCH test: {result} results for '維生素' in nutrients")
        except sqlite3.OperationalError as e:
            errors.append(f"FTS query failed: {e}")

    return errors


def validate_indexes(conn: sqlite3.Connection) -> list[str]:
    """Validate expected indexes exist."""
    errors = []

    expected_indexes = [
        "idx_foods_category",
        "idx_foods_name",
        "idx_foods_code",
        "idx_nutrients_category",
        "idx_nutrients_name",
        "idx_food_nutrients_food",
        "idx_food_nutrients_nutrient",
    ]

    existing = conn.execute("""
        SELECT name FROM sqlite_master WHERE type = 'index'
    """).fetchall()
    existing_names = [row[0] for row in existing]

    missing = [idx for idx in expected_indexes if idx not in existing_names]
    if missing:
        errors.append(f"Missing indexes: {', '.join(missing)}")
    else:
        print(f"  Indexes: {len(expected_indexes)} present")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate Taiwan FDA Food Nutrition Database"
    )
    parser.add_argument(
        "database",
        type=Path,
        help="SQLite database path to validate",
    )

    args = parser.parse_args()

    if not args.database.exists():
        print(f"Error: Database not found: {args.database}")
        sys.exit(1)

    print(f"Validating database: {args.database}\n")

    conn = sqlite3.connect(args.database)
    all_errors = []

    try:
        print("Record counts:")
        all_errors.extend(validate_counts(conn))

        print("\nReferential integrity:")
        all_errors.extend(validate_referential_integrity(conn))

        print("\nP/M/S nutrients:")
        all_errors.extend(validate_pms_nutrients(conn))

        print("\nData quality:")
        all_errors.extend(validate_data_quality(conn))

        print("\nFTS5 full-text search:")
        all_errors.extend(validate_fts(conn))

        print("\nIndexes:")
        all_errors.extend(validate_indexes(conn))

    finally:
        conn.close()

    print()
    if all_errors:
        print(f"VALIDATION FAILED with {len(all_errors)} error(s):")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
