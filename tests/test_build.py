"""Unit tests for build.py ETL functions."""

from unittest.mock import patch


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
        assert table_names == {
            "categories",
            "nutrient_categories",
            "foods",
            "nutrients",
            "food_nutrients",
        }

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


class TestNumericFieldParsing:
    """Tests for numeric field parsing edge cases (TC-NUM-*)."""

    def test_tc_num_1_whitespace_trimming_waste_rate(self, numeric_edge_cases_table):
        """TC-NUM-1: Whitespace trimming on waste_rate."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT waste_rate FROM cleaned_data WHERE code = 'NUM1'
        """).fetchone()
        assert result[0] == 10.5

    def test_tc_num_2_percent_sign_removal(self, numeric_edge_cases_table):
        """TC-NUM-2: Percent sign removal from waste_rate."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT waste_rate FROM cleaned_data WHERE code = 'NUM2'
        """).fetchone()
        assert result[0] == 50.0

    def test_tc_num_3_values_over_100_accepted(self, numeric_edge_cases_table):
        """TC-NUM-3: Values >100 accepted for waste_rate."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT waste_rate FROM cleaned_data WHERE code = 'NUM3'
        """).fetchone()
        assert result[0] == 150.0

    def test_tc_num_4_negative_values_accepted(self, numeric_edge_cases_table):
        """TC-NUM-4: Negative values accepted for waste_rate."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT waste_rate FROM cleaned_data WHERE code = 'NUM4'
        """).fetchone()
        assert result[0] == -5.0

    def test_tc_num_5_invalid_format_returns_null(self, numeric_edge_cases_table):
        """TC-NUM-5: Invalid format returns NULL for waste_rate."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT waste_rate FROM cleaned_data WHERE code = 'NUM5'
        """).fetchone()
        assert result[0] is None

    def test_tc_num_6_chinese_suffix_removal(self, numeric_edge_cases_table):
        """TC-NUM-6: Chinese '克' suffix removal from serving_size."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT serving_size FROM cleaned_data WHERE code = 'NUM6'
        """).fetchone()
        assert result[0] == 100.0

    def test_tc_num_7_full_width_space_removal(self, numeric_edge_cases_table):
        """TC-NUM-7: Full-width space (U+3000) removal from serving_size."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT serving_size FROM cleaned_data WHERE code = 'NUM7'
        """).fetchone()
        assert result[0] == 50.0

    def test_tc_num_8_empty_string_returns_null(self, numeric_edge_cases_table):
        """TC-NUM-8: Empty string returns NULL for serving_size."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT serving_size FROM cleaned_data WHERE code = 'NUM8'
        """).fetchone()
        assert result[0] is None

    def test_tc_num_9_scientific_notation_supported(self, numeric_edge_cases_table):
        """TC-NUM-9: Scientific notation is supported for std_deviation."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT std_deviation FROM cleaned_data WHERE code = 'NUM9'
        """).fetchone()
        assert result[0] == 0.0015

    def test_tc_num_10_negative_decimals_accepted(self, numeric_edge_cases_table):
        """TC-NUM-10: Negative decimals accepted for std_deviation."""
        clean_data(numeric_edge_cases_table)
        result = numeric_edge_cases_table.execute("""
            SELECT std_deviation FROM cleaned_data WHERE code = 'NUM10'
        """).fetchone()
        assert result[0] == -0.5


class TestPMSRatioEdgeCases:
    """Tests for P/M/S ratio splitting edge cases (TC-PMS-*)."""

    def test_tc_pms_1_normal_splitting(self, pms_edge_cases_table):
        """TC-PMS-1: Normal P/M/S splitting creates 3 records."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT n.name, fn.value_per_100g
            FROM food_nutrients fn
            JOIN nutrients n ON fn.nutrient_id = n.id
            JOIN foods f ON fn.food_id = f.id
            WHERE f.code = 'PMS1' AND n.name LIKE '脂肪酸比例%'
            ORDER BY n.name
        """).fetchall()
        values = {r[0]: r[1] for r in result}
        assert len(values) == 3
        assert values["脂肪酸比例-多元不飽和(P)"] == 1.52
        assert values["脂肪酸比例-單元不飽和(M)"] == 1.89
        assert values["脂肪酸比例-飽和(S)"] == 1.00

    def test_tc_pms_2_insufficient_parts_filtered(self, pms_edge_cases_table):
        """TC-PMS-2: P/M/S with only 2 parts is filtered out."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT COUNT(*)
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS2' AND n.name LIKE '脂肪酸比例%'
        """).fetchone()
        assert result[0] == 0

    def test_tc_pms_3_extra_parts_uses_first_three(self, pms_edge_cases_table):
        """TC-PMS-3: P/M/S with 4 parts uses first 3 only."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT n.name, fn.value_per_100g
            FROM food_nutrients fn
            JOIN nutrients n ON fn.nutrient_id = n.id
            JOIN foods f ON fn.food_id = f.id
            WHERE f.code = 'PMS3' AND n.name LIKE '脂肪酸比例%'
            ORDER BY n.name
        """).fetchall()
        values = {r[0]: r[1] for r in result}
        assert len(values) == 3
        assert values["脂肪酸比例-多元不飽和(P)"] == 1.52
        assert values["脂肪酸比例-單元不飽和(M)"] == 1.89
        assert values["脂肪酸比例-飽和(S)"] == 1.00

    def test_tc_pms_4_spaces_around_slashes_trimmed(self, pms_edge_cases_table):
        """TC-PMS-4: Spaces around slashes are trimmed."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT n.name, fn.value_per_100g
            FROM food_nutrients fn
            JOIN nutrients n ON fn.nutrient_id = n.id
            JOIN foods f ON fn.food_id = f.id
            WHERE f.code = 'PMS4' AND n.name LIKE '脂肪酸比例%'
            ORDER BY n.name
        """).fetchall()
        values = {r[0]: r[1] for r in result}
        assert len(values) == 3
        assert values["脂肪酸比例-多元不飽和(P)"] == 1.52
        assert values["脂肪酸比例-單元不飽和(M)"] == 1.89
        assert values["脂肪酸比例-飽和(S)"] == 1.00

    def test_tc_pms_5_leading_trailing_spaces_handled(self, pms_edge_cases_table):
        """TC-PMS-5: Leading/trailing spaces in P/M/S are handled."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT n.name, fn.value_per_100g
            FROM food_nutrients fn
            JOIN nutrients n ON fn.nutrient_id = n.id
            JOIN foods f ON fn.food_id = f.id
            WHERE f.code = 'PMS5' AND n.name LIKE '脂肪酸比例%'
            ORDER BY n.name
        """).fetchall()
        values = {r[0]: r[1] for r in result}
        assert len(values) == 3
        assert values["脂肪酸比例-多元不飽和(P)"] == 1.52

    def test_tc_pms_6_non_numeric_values_create_nulls(self, pms_edge_cases_table):
        """TC-PMS-6: Non-numeric P/M/S values create NULL values."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT fn.value_per_100g
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS6' AND n.name LIKE '脂肪酸比例%'
        """).fetchall()
        # All 3 records should have NULL values
        assert len(result) == 3
        for r in result:
            assert r[0] is None

    def test_tc_pms_7_empty_string_filtered(self, pms_edge_cases_table):
        """TC-PMS-7: Empty string P/M/S is filtered out."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT COUNT(*)
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS7' AND n.name LIKE '脂肪酸比例%'
        """).fetchone()
        assert result[0] == 0

    def test_tc_pms_8_null_input_filtered(self, pms_edge_cases_table):
        """TC-PMS-8: NULL P/M/S input is filtered out."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT COUNT(*)
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS8' AND n.name LIKE '脂肪酸比例%'
        """).fetchone()
        assert result[0] == 0

    def test_tc_pms_9_zero_values_valid(self, pms_edge_cases_table):
        """TC-PMS-9: Zero P/M/S values are valid."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT fn.value_per_100g
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS9' AND n.name LIKE '脂肪酸比例%'
        """).fetchall()
        assert len(result) == 3
        for r in result:
            assert r[0] == 0.0

    def test_tc_pms_10_negative_values_accepted(self, pms_edge_cases_table):
        """TC-PMS-10: Negative P/M/S values are accepted."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT fn.value_per_100g
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS10' AND n.name = '脂肪酸比例-多元不飽和(P)'
        """).fetchone()
        assert result[0] == -1.52

    def test_tc_pms_11_empty_parts_create_nulls(self, pms_edge_cases_table):
        """TC-PMS-11: Empty P/M/S parts (///) create NULL values."""
        clean_data(pms_edge_cases_table)
        create_normalized_tables(pms_edge_cases_table)
        result = pms_edge_cases_table.execute("""
            SELECT fn.value_per_100g
            FROM food_nutrients fn
            JOIN foods f ON fn.food_id = f.id
            JOIN nutrients n ON fn.nutrient_id = n.id
            WHERE f.code = 'PMS11' AND n.name LIKE '脂肪酸比例%'
        """).fetchall()
        # All 3 records should have NULL values
        assert len(result) == 3
        for r in result:
            assert r[0] is None


class TestStringNormalization:
    """Tests for string normalization edge cases (TC-STR-*)."""

    def test_tc_str_1_double_space_collapse(self, string_edge_cases_table):
        """TC-STR-1: Double space collapsed to single in nutrient_category."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT nutrient_category FROM cleaned_data WHERE code = 'STR1'
        """).fetchone()
        assert result[0] == "維生素B群 & C"

    def test_tc_str_2_triple_space_partial_reduction(self, string_edge_cases_table):
        """TC-STR-2: Triple spaces only reduce first double to single."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT nutrient_category FROM cleaned_data WHERE code = 'STR2'
        """).fetchone()
        # "維生素B群   C" -> "維生素B群  C" (only one double->single replacement)
        assert result[0] == "維生素B群  C"

    def test_tc_str_3_trim_whitespace_name_zh(self, string_edge_cases_table):
        """TC-STR-3: Leading/trailing whitespace trimmed from name_zh."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT name_zh FROM cleaned_data WHERE code = 'STR3'
        """).fetchone()
        assert result[0] == "白飯"

    def test_tc_str_4_empty_name_en_becomes_null(self, string_edge_cases_table):
        """TC-STR-4: Empty name_en becomes NULL."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT name_en FROM cleaned_data WHERE code = 'STR4'
        """).fetchone()
        assert result[0] is None

    def test_tc_str_5_greek_letters_preserved(self, string_edge_cases_table):
        """TC-STR-5: Greek letters preserved in nutrient_name."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT nutrient_name FROM cleaned_data WHERE code = 'STR5'
        """).fetchone()
        assert result[0] == "β-胡蘿蔔素"

    def test_tc_str_6_tab_preserved(self, string_edge_cases_table):
        """TC-STR-6: Tab characters preserved in nutrient_category."""
        clean_data(string_edge_cases_table)
        result = string_edge_cases_table.execute("""
            SELECT nutrient_category FROM cleaned_data WHERE code = 'STR6'
        """).fetchone()
        assert result[0] == "維生素\tB群"


class TestNullHandling:
    """Tests for NULL handling edge cases (TC-NULL-*)."""

    def test_tc_null_1_null_code_passthrough(self, null_edge_cases_table):
        """TC-NULL-1: NULL code passes through unchanged."""
        clean_data(null_edge_cases_table)
        result = null_edge_cases_table.execute("""
            SELECT code FROM cleaned_data WHERE name_zh = '測試1'
        """).fetchone()
        assert result[0] is None

    def test_tc_null_2_empty_alias_becomes_null(self, null_edge_cases_table):
        """TC-NULL-2: Empty alias becomes NULL via NULLIF."""
        clean_data(null_edge_cases_table)
        result = null_edge_cases_table.execute("""
            SELECT alias FROM cleaned_data WHERE code = 'NULL2'
        """).fetchone()
        assert result[0] is None

    def test_tc_null_3_whitespace_only_becomes_null(self, null_edge_cases_table):
        """TC-NULL-3: Whitespace-only description becomes NULL."""
        clean_data(null_edge_cases_table)
        result = null_edge_cases_table.execute("""
            SELECT description FROM cleaned_data WHERE code = 'NULL3'
        """).fetchone()
        assert result[0] is None

    def test_tc_null_4_null_value_raw_stays_null(self, null_edge_cases_table):
        """TC-NULL-4: NULL value_raw stays NULL."""
        clean_data(null_edge_cases_table)
        result = null_edge_cases_table.execute("""
            SELECT value_raw FROM cleaned_data WHERE code = 'NULL4'
        """).fetchone()
        assert result[0] is None
