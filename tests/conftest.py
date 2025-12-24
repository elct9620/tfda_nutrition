"""Test fixtures for build.py unit tests."""

import pytest
import duckdb


@pytest.fixture
def duckdb_conn():
    """Provide an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def raw_data_table(duckdb_conn):
    """Create a raw_data table with sample FDA-like data."""
    duckdb_conn.execute("""
        CREATE TABLE raw_data AS
        SELECT * FROM (VALUES
            ('穀物類', 'A0001', '白飯', 'White Rice', '米飯', '煮熟米飯', '0', '100克', '熱量', '熱量', 'kcal', '130', '5', '2.1'),
            ('穀物類', 'A0001', '白飯', 'White Rice', '米飯', '煮熟米飯', '0', '100克', '一般成分', '粗蛋白', 'g', '  2.5  ', '5', '0.3'),
            ('穀物類', 'A0001', '白飯', 'White Rice', '米飯', '煮熟米飯', '0', '100克', '一般成分', '粗脂肪', 'g', '0.3', '5', '0.1'),
            ('肉類', 'B0001', '雞胸肉', 'Chicken Breast', '', '去皮雞胸', '5%', '150.0克', '熱量', '熱量', 'kcal', '165', '3', '5.2'),
            ('肉類', 'B0001', '雞胸肉', 'Chicken Breast', '', '去皮雞胸', '5%', '150.0克', '一般成分', '粗蛋白', 'g', '31.0', '3', '1.5'),
            ('油脂類', 'C0001', '植物油', NULL, NULL, '調合油', '0', '10', '脂肪酸', 'P/M/S', NULL, '1.52/1.89/1.00', '2', '0.1')
        ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
    """)
    return duckdb_conn


@pytest.fixture
def numeric_edge_cases_table(duckdb_conn):
    """Create a raw_data table with numeric parsing edge cases (TC-NUM-*)."""
    duckdb_conn.execute("""
        CREATE TABLE raw_data AS
        SELECT
            "食品分類"::VARCHAR AS "食品分類",
            "整合編號"::VARCHAR AS "整合編號",
            "樣品名稱"::VARCHAR AS "樣品名稱",
            "樣品英文名稱"::VARCHAR AS "樣品英文名稱",
            "俗名"::VARCHAR AS "俗名",
            "內容物描述"::VARCHAR AS "內容物描述",
            "廢棄率"::VARCHAR AS "廢棄率",
            "每單位重"::VARCHAR AS "每單位重",
            "分析項分類"::VARCHAR AS "分析項分類",
            "分析項"::VARCHAR AS "分析項",
            "含量單位"::VARCHAR AS "含量單位",
            "每100克含量"::VARCHAR AS "每100克含量",
            "樣本數"::VARCHAR AS "樣本數",
            "標準差"::VARCHAR AS "標準差"
        FROM (VALUES
            -- TC-NUM-1: Whitespace trimming on waste_rate
            ('穀物類', 'NUM1', '測試1', NULL, NULL, NULL, '  10.5  ', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-2: Percent sign removal
            ('穀物類', 'NUM2', '測試2', NULL, NULL, NULL, '50%', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-3: Values >100 accepted
            ('穀物類', 'NUM3', '測試3', NULL, NULL, NULL, '150%', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-4: Negative values accepted
            ('穀物類', 'NUM4', '測試4', NULL, NULL, NULL, '-5%', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-5: Invalid format returns NULL
            ('穀物類', 'NUM5', '測試5', NULL, NULL, NULL, 'abc', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-6: Chinese suffix removal on serving_size
            ('穀物類', 'NUM6', '測試6', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-7: Full-width space removal (U+3000)
            ('穀物類', 'NUM7', '測試7', NULL, NULL, NULL, '0', '　50　', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-8: Empty string returns NULL for serving_size
            ('穀物類', 'NUM8', '測試8', NULL, NULL, NULL, '0', '', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NUM-9: Scientific notation not supported
            ('穀物類', 'NUM9', '測試9', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '1.5e-3'),
            -- TC-NUM-10: Negative decimals in std_deviation
            ('穀物類', 'NUM10', '測試10', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '-0.5')
        ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
    """)
    return duckdb_conn


@pytest.fixture
def pms_edge_cases_table(duckdb_conn):
    """Create a raw_data table with P/M/S ratio edge cases (TC-PMS-*)."""
    duckdb_conn.execute("""
        CREATE TABLE raw_data AS
        SELECT
            "食品分類"::VARCHAR AS "食品分類",
            "整合編號"::VARCHAR AS "整合編號",
            "樣品名稱"::VARCHAR AS "樣品名稱",
            "樣品英文名稱"::VARCHAR AS "樣品英文名稱",
            "俗名"::VARCHAR AS "俗名",
            "內容物描述"::VARCHAR AS "內容物描述",
            "廢棄率"::VARCHAR AS "廢棄率",
            "每單位重"::VARCHAR AS "每單位重",
            "分析項分類"::VARCHAR AS "分析項分類",
            "分析項"::VARCHAR AS "分析項",
            "含量單位"::VARCHAR AS "含量單位",
            "每100克含量"::VARCHAR AS "每100克含量",
            "樣本數"::VARCHAR AS "樣本數",
            "標準差"::VARCHAR AS "標準差"
        FROM (VALUES
            -- TC-PMS-1: Normal splitting
            ('油脂類', 'PMS1', '測試油1', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '1.52/1.89/1.00', '1', '0.1'),
            -- TC-PMS-2: Insufficient parts (should be filtered)
            ('油脂類', 'PMS2', '測試油2', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '1.52/1.89', '1', '0.1'),
            -- TC-PMS-3: Extra parts (use first 3 only)
            ('油脂類', 'PMS3', '測試油3', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '1.52/1.89/1.00/0.5', '1', '0.1'),
            -- TC-PMS-4: Spaces around slashes (should be trimmed)
            ('油脂類', 'PMS4', '測試油4', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '1.52 / 1.89 / 1.00', '1', '0.1'),
            -- TC-PMS-5: Leading/trailing spaces
            ('油脂類', 'PMS5', '測試油5', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, ' 1.52 / 1.89 / 1.00 ', '1', '0.1'),
            -- TC-PMS-6: Non-numeric values (should create NULL values)
            ('油脂類', 'PMS6', '測試油6', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, 'a/b/c', '1', '0.1'),
            -- TC-PMS-7: Empty string (should be filtered)
            ('油脂類', 'PMS7', '測試油7', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '', '1', '0.1'),
            -- TC-PMS-8: NULL input (should be filtered)
            ('油脂類', 'PMS8', '測試油8', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, NULL, '1', '0.1'),
            -- TC-PMS-9: Zero values
            ('油脂類', 'PMS9', '測試油9', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '0/0/0', '1', '0.1'),
            -- TC-PMS-10: Negative values
            ('油脂類', 'PMS10', '測試油10', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '-1.52/1.89/1.00', '1', '0.1'),
            -- TC-PMS-11: Empty parts (slashes only)
            ('油脂類', 'PMS11', '測試油11', NULL, NULL, NULL, '0', '10', '脂肪酸', 'P/M/S', NULL, '///', '1', '0.1')
        ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
    """)
    return duckdb_conn


@pytest.fixture
def string_edge_cases_table(duckdb_conn):
    """Create a raw_data table with string normalization edge cases (TC-STR-*)."""
    duckdb_conn.execute("""
        CREATE TABLE raw_data AS
        SELECT
            "食品分類"::VARCHAR AS "食品分類",
            "整合編號"::VARCHAR AS "整合編號",
            "樣品名稱"::VARCHAR AS "樣品名稱",
            "樣品英文名稱"::VARCHAR AS "樣品英文名稱",
            "俗名"::VARCHAR AS "俗名",
            "內容物描述"::VARCHAR AS "內容物描述",
            "廢棄率"::VARCHAR AS "廢棄率",
            "每單位重"::VARCHAR AS "每單位重",
            "分析項分類"::VARCHAR AS "分析項分類",
            "分析項"::VARCHAR AS "分析項",
            "含量單位"::VARCHAR AS "含量單位",
            "每100克含量"::VARCHAR AS "每100克含量",
            "樣本數"::VARCHAR AS "樣本數",
            "標準差"::VARCHAR AS "標準差"
        FROM (VALUES
            -- TC-STR-1: Double space collapse in nutrient_category
            ('穀物類', 'STR1', '測試1', NULL, NULL, NULL, '0', '100克', '維生素B群  & C', '維生素B1', 'mg', '0.1', '1', '0.01'),
            -- TC-STR-2: Triple spaces only reduce first double
            ('穀物類', 'STR2', '測試2', NULL, NULL, NULL, '0', '100克', '維生素B群   C', '維生素B2', 'mg', '0.2', '1', '0.01'),
            -- TC-STR-3: Trim whitespace on name_zh
            ('穀物類', 'STR3', '  白飯  ', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-STR-4: Empty name_en becomes NULL
            ('穀物類', 'STR4', '測試4', '', NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-STR-5: Greek letters preserved in nutrient_name
            ('穀物類', 'STR5', '測試5', NULL, NULL, NULL, '0', '100克', '維生素A', 'β-胡蘿蔔素', 'μg', '100', '1', '0.1'),
            -- TC-STR-6: Tab characters preserved
            ('穀物類', 'STR6', '測試6', NULL, NULL, NULL, '0', '100克', E'維生素\tB群', '維生素B6', 'mg', '0.1', '1', '0.01')
        ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
    """)
    return duckdb_conn


@pytest.fixture
def null_edge_cases_table(duckdb_conn):
    """Create a raw_data table with NULL handling edge cases (TC-NULL-*)."""
    duckdb_conn.execute("""
        CREATE TABLE raw_data AS
        SELECT
            "食品分類"::VARCHAR AS "食品分類",
            "整合編號"::VARCHAR AS "整合編號",
            "樣品名稱"::VARCHAR AS "樣品名稱",
            "樣品英文名稱"::VARCHAR AS "樣品英文名稱",
            "俗名"::VARCHAR AS "俗名",
            "內容物描述"::VARCHAR AS "內容物描述",
            "廢棄率"::VARCHAR AS "廢棄率",
            "每單位重"::VARCHAR AS "每單位重",
            "分析項分類"::VARCHAR AS "分析項分類",
            "分析項"::VARCHAR AS "分析項",
            "含量單位"::VARCHAR AS "含量單位",
            "每100克含量"::VARCHAR AS "每100克含量",
            "樣本數"::VARCHAR AS "樣本數",
            "標準差"::VARCHAR AS "標準差"
        FROM (VALUES
            -- TC-NULL-1: NULL code passthrough
            ('穀物類', NULL, '測試1', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NULL-2: Empty alias becomes NULL
            ('穀物類', 'NULL2', '測試2', NULL, '', NULL, '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NULL-3: Whitespace-only description becomes NULL
            ('穀物類', 'NULL3', '測試3', NULL, NULL, '   ', '0', '100克', '熱量', '熱量', 'kcal', '100', '1', '0.1'),
            -- TC-NULL-4: NULL value_raw stays NULL
            ('穀物類', 'NULL4', '測試4', NULL, NULL, NULL, '0', '100克', '熱量', '熱量', 'kcal', NULL, '1', '0.1')
        ) AS t("食品分類", "整合編號", "樣品名稱", "樣品英文名稱", "俗名", "內容物描述", "廢棄率", "每單位重", "分析項分類", "分析項", "含量單位", "每100克含量", "樣本數", "標準差")
    """)
    return duckdb_conn
