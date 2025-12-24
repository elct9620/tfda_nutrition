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
