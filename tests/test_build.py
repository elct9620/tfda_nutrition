"""Unit tests for build.py ETL functions."""

import subprocess
from unittest.mock import patch

import pytest

from build import (
    check_fts5_support,
    clean_data,
    create_normalized_tables,
)


class TestCleanData:
    """Tests for the clean_data function."""

    def test_trims_whitespace_from_numeric_values(self, raw_data_table):
        """Verify TRIM removes leading/trailing spaces from values."""
        clean_data(raw_data_table)

        result = raw_data_table.execute("""
            SELECT value_raw FROM cleaned_data
            WHERE nutrient_name = '粗蛋白' AND code = 'A0001'
        """).fetchone()

        assert result[0] == "2.5"

    def test_removes_percent_sign_from_waste_rate(self, raw_data_table):
        """Verify waste_rate removes % suffix and casts to DOUBLE."""
        clean_data(raw_data_table)

        result = raw_data_table.execute("""
            SELECT waste_rate FROM cleaned_data
            WHERE code = 'B0001'
            LIMIT 1
        """).fetchone()

        assert result[0] == 5.0

    def test_removes_gram_suffix_from_serving_size(self, raw_data_table):
        """Verify serving_size removes '克' suffix and casts to DOUBLE."""
        clean_data(raw_data_table)

        result = raw_data_table.execute("""
            SELECT serving_size FROM cleaned_data
            WHERE code = 'A0001'
            LIMIT 1
        """).fetchone()

        assert result[0] == 100.0

    def test_nullifies_empty_strings(self, raw_data_table):
        """Verify empty strings become NULL."""
        clean_data(raw_data_table)

        result = raw_data_table.execute("""
            SELECT alias FROM cleaned_data
            WHERE code = 'B0001'
            LIMIT 1
        """).fetchone()

        assert result[0] is None

    def test_replaces_double_spaces_in_nutrient_category(self, duckdb_conn):
        """Verify double spaces are replaced with single space."""
        duckdb_conn.execute("""
            CREATE TABLE raw_data AS
            SELECT * FROM (VALUES
                ('穀物類', 'A0001', '白飯', '', '', '', '0', '100', '維生素B群  & C', '維生素B1', 'mg', '0.1', '1', '0.01')
            ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
        """)

        clean_data(duckdb_conn)

        result = duckdb_conn.execute("""
            SELECT nutrient_category FROM cleaned_data
        """).fetchone()

        assert result[0] == "維生素B群 & C"


class TestCreateNormalizedTables:
    """Tests for the create_normalized_tables function."""

    def test_creates_five_tables(self, raw_data_table):
        """Verify all 5 normalized tables are created."""
        clean_data(raw_data_table)
        create_normalized_tables(raw_data_table)

        tables = raw_data_table.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
            AND table_name IN ('categories', 'nutrient_categories', 'foods', 'nutrients', 'food_nutrients')
        """).fetchall()

        table_names = {t[0] for t in tables}
        assert table_names == {"categories", "nutrient_categories", "foods", "nutrients", "food_nutrients"}

    def test_categories_are_unique(self, raw_data_table):
        """Verify categories table has unique entries."""
        clean_data(raw_data_table)
        create_normalized_tables(raw_data_table)

        result = raw_data_table.execute("""
            SELECT COUNT(*) FROM categories
        """).fetchone()

        # 3 categories: 穀物類, 肉類, 油脂類
        assert result[0] == 3

    def test_foods_have_category_reference(self, raw_data_table):
        """Verify foods table has valid category_id references."""
        clean_data(raw_data_table)
        create_normalized_tables(raw_data_table)

        result = raw_data_table.execute("""
            SELECT f.code, c.name
            FROM foods f
            JOIN categories c ON f.category_id = c.id
            WHERE f.code = 'A0001'
        """).fetchone()

        assert result[0] == "A0001"
        assert result[1] == "穀物類"

    def test_pms_ratio_splits_into_three_nutrients(self, raw_data_table):
        """Verify P/M/S ratio creates 3 separate nutrient records."""
        clean_data(raw_data_table)
        create_normalized_tables(raw_data_table)

        result = raw_data_table.execute("""
            SELECT name FROM nutrients
            WHERE name LIKE '脂肪酸比例%'
            ORDER BY name
        """).fetchall()

        nutrient_names = [r[0] for r in result]
        assert "脂肪酸比例-多元不飽和(P)" in nutrient_names
        assert "脂肪酸比例-單元不飽和(M)" in nutrient_names
        assert "脂肪酸比例-飽和(S)" in nutrient_names

    def test_pms_values_are_split_correctly(self, raw_data_table):
        """Verify P/M/S value '1.52/1.89/1.00' splits into correct values."""
        clean_data(raw_data_table)
        create_normalized_tables(raw_data_table)

        result = raw_data_table.execute("""
            SELECT n.name, fn.value_per_100g
            FROM food_nutrients fn
            JOIN nutrients n ON fn.nutrient_id = n.id
            JOIN foods f ON fn.food_id = f.id
            WHERE f.code = 'C0001' AND n.name LIKE '脂肪酸比例%'
            ORDER BY n.name
        """).fetchall()

        values = {r[0]: r[1] for r in result}
        assert values["脂肪酸比例-多元不飽和(P)"] == 1.52
        assert values["脂肪酸比例-單元不飽和(M)"] == 1.89
        assert values["脂肪酸比例-飽和(S)"] == 1.00

    def test_returns_correct_counts(self, raw_data_table):
        """Verify function returns correct table counts."""
        clean_data(raw_data_table)
        counts = create_normalized_tables(raw_data_table)

        assert counts["categories"] == 3
        assert counts["foods"] == 3  # A0001, B0001, C0001
        assert counts["nutrients"] >= 5  # 熱量, 粗蛋白, 粗脂肪, + 3 P/M/S


class TestCheckFts5Support:
    """Tests for the check_fts5_support function."""

    def test_returns_true_when_fts5_available(self):
        """Verify returns True when sqlite3 supports FTS5 trigram."""
        with patch("build.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            assert check_fts5_support() is True

    def test_returns_false_when_fts5_not_available(self):
        """Verify returns False when sqlite3 does not support FTS5."""
        with patch("build.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            assert check_fts5_support() is False

    def test_returns_false_when_sqlite3_not_found(self):
        """Verify returns False when sqlite3 command not found."""
        with patch("build.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert check_fts5_support() is False
