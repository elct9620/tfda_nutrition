# Taiwan Food Nutrition Database Specification

A specification for transforming Taiwan FDA open data into an accessible SQLite database.

## 1. Overview

### 1.1 Purpose

This project provides an automated ETL pipeline that transforms Taiwan FDA's food nutrition
open data (JSON format) into a normalized SQLite database, making nutritional information
easily accessible for developers, researchers, and health applications.

### 1.2 Data Source

| Attribute | Value |
|-----------|-------|
| Provider | Taiwan Food and Drug Administration (TFDA) |
| Dataset ID | 20 |
| Format | JSON |
| URL | `https://data.fda.gov.tw/data/opendata/export/20/json` |
| Update Frequency | Periodic (check source for schedule) |
| License | Taiwan Open Government Data License |

#### Source JSON Fields

| JSON Field | Description | Maps To |
|------------|-------------|---------|
| 食品分類 | Food category | categories.name |
| 整合編號 | Integration code | foods.code |
| 樣品名稱 | Chinese food name | foods.name_zh |
| 樣品英文名稱 | English food name | foods.name_en |
| 俗名 | Common/alias name | foods.alias |
| 內容物描述 | Content description | foods.description |
| 廢棄率 | Waste percentage | foods.waste_rate |
| 每單位重 | Per-unit weight | foods.serving_size |
| 分析項分類 | Nutrient category | nutrient_categories.name |
| 分析項 | Nutrient name | nutrients.name |
| 含量單位 | Unit of measure | nutrients.unit |
| 每100克含量 | Value per 100g | food_nutrients.value_per_100g |
| 樣本數 | Sample count | food_nutrients.sample_count |
| 標準差 | Standard deviation | food_nutrients.std_deviation |

### 1.3 System Architecture

```
+------------------+     +------------------+     +------------------+
|   Taiwan FDA     |     |  GitHub Actions  |     |   GitHub         |
|   Open Data API  |---->|  ETL Pipeline    |---->|   Releases       |
|   (JSON)         |     |  (Python/DuckDB) |     |   (SQLite DB)    |
+------------------+     +------------------+     +------------------+
                                  |
                                  v
                         +------------------+
                         |  Validation      |
                         |  & Test Suite    |
                         +------------------+
```

## 2. Data Flow

### 2.1 ETL Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions Workflow                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐  │
│  │ Download │   │  Clean   │   │Normalize │   │  Export SQLite   │  │
│  │   JSON   │──>│   Data   │──>│  Schema  │──>│  + Validation    │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────┘  │
│       │              │              │                   │            │
│       v              v              v                   v            │
│   food_data.zip  raw_data     5 normalized       nutrition.db       │
│                  (DuckDB)       tables           + report.json      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    v
                        ┌───────────────────────────────────────┐
                        │           GitHub Release              │
                        │  - nutrition.db                       │
                        │  - report.json                        │
                        │  - checksums.txt                      │
                        ├───────────────────────────────────────┤
                        │           GitHub Pages                │
                        │  - Download Page + Remote Access      │
                        └───────────────────────────────────────┘
```

### 2.2 Data Transformation Steps

| Step | Input | Process | Output |
|------|-------|---------|--------|
| 1. Download | FDA API URL | curl + unzip | `dataset.json` |
| 2. Load | JSON file | DuckDB read_json_auto | In-memory table |
| 3. Clean | Raw records | TRIM, REPLACE, TRY_CAST | Cleaned data |
| 4. Normalize | Flat records | GROUP BY, JOIN | 5 relational tables |
| 5. Export | DuckDB tables | SQLite INSERT | `nutrition.db` |
| 6. Validate | SQLite DB | SQL assertions | `report.json` |

## 3. Database Schema

### 3.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│   categories    │       │nutrient_categories│
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ name            │       │ name            │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │ 1:N                     │ 1:N
         │                         │
         v                         v
┌─────────────────┐       ┌─────────────────┐
│     foods       │       │    nutrients    │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ code (UNIQUE)   │       │ category_id (FK)│───┐
│ name_zh         │       │ name            │   │
│ name_en         │       │ unit            │   │
│ category_id (FK)│───┐   └────────┬────────┘   │
│ alias           │   │            │            │
│ description     │   │            │ M:N        │
│ waste_rate      │   │            │            │
│ serving_size    │   │            v            │
└────────┬────────┘   │   ┌─────────────────┐   │
         │            │   │ food_nutrients  │   │
         │            │   ├─────────────────┤   │
         │ 1:N        │   │ food_id (FK,PK) │<──┘
         │            │   │ nutrient_id(FK,PK)│
         └────────────┴──>│ value_per_100g  │
                          │ sample_count    │
                          │ std_deviation   │
                          └─────────────────┘
```

### 3.2 Table Definitions

#### categories
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| name | TEXT | NOT NULL, UNIQUE | Category name (e.g., "魚貝類") |

#### nutrient_categories
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| name | TEXT | NOT NULL, UNIQUE | Nutrient category (e.g., "維生素A") |

#### foods
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| code | TEXT | NOT NULL, UNIQUE | Integration code (整合編號) |
| name_zh | TEXT | NOT NULL | Chinese name (樣品名稱) |
| name_en | TEXT | NULLABLE | English name |
| category_id | INTEGER | FK → categories | Food category reference |
| alias | TEXT | NULLABLE | Common name (俗名) |
| description | TEXT | NULLABLE | Content description |
| waste_rate | REAL | NULLABLE | Waste percentage (%) |
| serving_size | REAL | NULLABLE | Per-unit weight (grams) |

#### nutrients
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| category_id | INTEGER | FK → nutrient_categories | Nutrient category reference |
| name | TEXT | NOT NULL | Nutrient name (分析項) |
| unit | TEXT | NULLABLE | Unit (mg/g/ug/kcal/I.U.) |

#### food_nutrients
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| food_id | INTEGER | FK → foods, PK | Food reference |
| nutrient_id | INTEGER | FK → nutrients, PK | Nutrient reference |
| value_per_100g | REAL | NULLABLE | Value per 100g |
| sample_count | INTEGER | NULLABLE | Number of samples |
| std_deviation | REAL | NULLABLE | Standard deviation |

### 3.3 Indexes

| Index Name | Table | Column(s) | Purpose |
|------------|-------|-----------|---------|
| idx_foods_category | foods | category_id | Category filtering |
| idx_foods_name | foods | name_zh | Name search |
| idx_foods_code | foods | code | Code lookup |
| idx_nutrients_category | nutrients | category_id | Nutrient category filtering |
| idx_nutrients_name | nutrients | name | Nutrient search |
| idx_food_nutrients_food | food_nutrients | food_id | Food-based queries |
| idx_food_nutrients_nutrient | food_nutrients | nutrient_id | Nutrient-based queries |

## 4. Data Cleaning Rules

### 4.1 Transformation Rules

| Field | Issue | Solution | Example |
|-------|-------|----------|---------|
| Numeric values | Leading spaces | `TRIM()` | `"    0.74"` → `0.74` |
| 維生素B群 & C | Double spaces | `REPLACE('  ', ' ')` | `"B群  & C"` → `"B群 & C"` |
| P/M/S ratio | Slash format | Split to 3 nutrients | `"1.52/1.89/1.00"` → 3 records |
| 每單位重 | "克" suffix | `REPLACE('克', '')` | `"601.0克"` → `601.0` |
| 廢棄率 | Optional "%" | `REPLACE('%', '')` | `"19.4%"` → `19.4` |
| NULL values | Various | Preserve as NULL | No default filling |

### 4.2 P/M/S Ratio Handling

The P/M/S (Polyunsaturated/Monounsaturated/Saturated) ratio requires special processing:

```
Input:  "1.52/1.89/1.00" in "每100克含量" field

Output: 3 separate nutrient records:
        - 脂肪酸比例-多元不飽和(P): 1.52
        - 脂肪酸比例-單元不飽和(M): 1.89
        - 脂肪酸比例-飽和(S): 1.00
```

## 5. GitHub Actions Workflow

### 5.1 Workflow Configuration

```yaml
# .github/workflows/etl.yml
name: Food Nutrition ETL

on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly on 1st
  workflow_dispatch:
    inputs:
      release:
        description: 'Create a GitHub release'
        required: false
        type: boolean
        default: false

jobs:
  etl:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.version }}
    steps:
      - uses: actions/checkout@v6

      - name: Generate version
        id: version
        run: |
          git fetch --tags
          BASE_VERSION="v$(date +%Y%m%d)"
          SUFFIX=0
          VERSION="$BASE_VERSION"
          while git rev-parse "$VERSION" >/dev/null 2>&1; do
            SUFFIX=$((SUFFIX + 1))
            VERSION="${BASE_VERSION}.${SUFFIX}"
          done
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Setup Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install duckdb
          # Ensure system sqlite3 with FTS5 support is available
          sudo apt-get update && sudo apt-get install -y sqlite3

      - name: Verify FTS5 support
        run: |
          echo "SQLite version: $(sqlite3 --version)"
          sqlite3 :memory: "CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram');"
          echo "✅ FTS5 trigram tokenizer supported"

      - name: Download FDA data
        run: |
          curl -L -o food_data.zip \
            "https://data.fda.gov.tw/data/opendata/export/20/json"
          unzip food_data.zip -d data/

      - name: Run ETL
        run: python build.py nutrition.db --input data/*.json --report report.json

      - name: Verify FTS enabled
        run: |
          # Ensure FTS was created successfully
          FTS_ENABLED=$(jq -r '.fts_enabled' report.json)
          if [ "$FTS_ENABLED" != "true" ]; then
            echo "❌ FTS5 was not enabled in the database"
            exit 1
          fi
          # Verify FTS tables exist
          FTS_COUNT=$(sqlite3 nutrition.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'")
          if [ "$FTS_COUNT" != "2" ]; then
            echo "❌ Expected 2 FTS tables, found $FTS_COUNT"
            exit 1
          fi
          echo "✅ FTS5 verification passed"

      - name: Run validation
        run: python validate.py nutrition.db

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: etl-output
          path: |
            nutrition.db
            report.json
            USAGE.md

      - name: Write Job Summary
        run: |
          echo "## 🍎 Food Nutrition ETL Report" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Version**: ${{ steps.version.outputs.version }}" >> $GITHUB_STEP_SUMMARY
          echo "**Trigger**: ${{ github.event_name }}" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Metric | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|--------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Total Records | $(jq .counts.total_records report.json) |" >> $GITHUB_STEP_SUMMARY
          echo "| Foods | $(jq .counts.foods report.json) |" >> $GITHUB_STEP_SUMMARY
          echo "| Nutrients | $(jq .counts.nutrients report.json) |" >> $GITHUB_STEP_SUMMARY
          echo "| Categories | $(jq .counts.categories report.json) |" >> $GITHUB_STEP_SUMMARY
          FTS_STATUS=$(jq -r '.fts_enabled | if . then "✅ Enabled" else "⚠️ Disabled" end' report.json)
          echo "| FTS5 Full-Text Search | $FTS_STATUS |" >> $GITHUB_STEP_SUMMARY

  release:
    needs: etl
    if: github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && inputs.release == true)
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0  # Required for GoReleaser changelog

      - name: Download artifacts
        uses: actions/download-artifact@v5
        with:
          name: etl-output

      - name: Create Git tag
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag ${{ needs.etl.outputs.version }}
          git push origin ${{ needs.etl.outputs.version }}

      - name: Run GoReleaser
        uses: goreleaser/goreleaser-action@v6
        with:
          distribution: goreleaser
          version: "~> v2"
          args: release --clean
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  pages:
    needs: etl
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v6

      - name: Download artifacts
        uses: actions/download-artifact@v5
        with:
          name: etl-output

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Build site
        run: |
          mkdir -p dist
          cp nutrition.db dist/
          cp web/index.html dist/

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### 5.2 Workflow Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       GitHub Actions Pipeline                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │
│  │Schedule │  │ Setup   │  │Download │  │  Run    │  │ Job Summary │   │
│  │   or    │─>│  Env    │─>│  Data   │─>│  ETL    │─>│  (Markdown) │   │
│  │ Manual  │  │         │  │         │  │         │  │             │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └──────┬──────┘   │
│                                                              │          │
│                              ┌───────────────────────────────┼───────┐  │
│                              │                               │       │  │
│                              v                               v       │  │
│                       ┌─────────────┐                 ┌───────────┐ │  │
│                       │ GoReleaser  │                 │  GitHub   │ │  │
│                       │  (Release)  │                 │   Pages   │ │  │
│                       └─────────────┘                 └───────────┘ │  │
│                              │                               │       │  │
│                              v                               v       │  │
│                       nutrition.db                    Download Page  │  │
│                       + checksums                     + Remote Access│  │
│                                                                      │  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 GoReleaser Configuration

```yaml
# .goreleaser.yaml
project_name: taiwan-food-nutrition

builds: []  # No binary builds needed

release:
  extra_files:
    - glob: nutrition.db
    - glob: USAGE.md

checksum:
  name_template: 'checksums.txt'

changelog:
  sort: asc
  filters:
    exclude:
      - '^docs:'
      - '^test:'
```

### 5.4 GitHub Pages Architecture

#### 5.4.1 Page Structure

The GitHub Pages site is a single-page application with two main sections:

| Section | Purpose |
|---------|---------|
| Hero | Project overview, statistics, download button |
| Playground | Interactive SQL query interface |

```
web/
  index.html       # Single-page application
  nutrition.db     # SQLite database (copied during build)
```

#### 5.4.2 Design System

**Design Tokens:**

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#0f2540` | Headers, primary text, dark backgrounds |
| Secondary | `#51a8dd` | Links, interactive elements, highlights |
| Accent 1 | `#eb7a77` | Error states, warnings |
| Accent 2 | `#f9bf45` | CTA buttons, success states |
| Background | `#ffffff` | Main page background |
| Surface | `#f5f7fa` | Code blocks, result tables |
| Border | `#e5e7eb` | Table borders, separators |

**Style Guidelines:**
- Border radius: `0` (sharp corners throughout)
- Typography: System fonts (no external fonts)
- Spacing scale: 8px, 16px, 24px, 32px

#### 5.4.3 CDN Dependencies

| Library | Version | CDN URL | Purpose |
|---------|---------|---------|---------|
| TailwindCSS | 3.x | `https://cdn.tailwindcss.com` | Styling with custom config |
| SQL.js | 1.11.0 | `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/sql-wasm.js` | SQLite in browser |
| SQL.js WASM | 1.11.0 | `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/sql-wasm.wasm` | WASM binary |

**Notes:**
- **FTS5 is not available in the web playground.** Standard sql.js does not include FTS5, and available FTS5 forks lack the trigram tokenizer required by this database. Use `LIKE` queries for text search in the browser. FTS5 works when using the downloaded database with native SQLite.
- Tailwind CDN mode allows inline configuration without build step
- No npm/yarn installation required

#### 5.4.4 HTML Structure

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Taiwan Food Nutrition Database</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#0f2540',
                        secondary: '#51a8dd',
                        accent1: '#eb7a77',
                        accent2: '#f9bf45',
                        surface: '#f5f7fa'
                    },
                    borderRadius: {
                        DEFAULT: '0',
                        'none': '0'
                    }
                }
            }
        }
    </script>
</head>
<body>
    <header><!-- Project title, GitHub link --></header>
    <section id="hero"><!-- Statistics, Download button --></section>
    <section id="playground"><!-- Query input, Example selector, Results --></section>
    <footer><!-- Attribution, License --></footer>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/sql-wasm.js"></script>
    <script>/* Application logic */</script>
</body>
</html>
```

#### 5.4.5 Component Specifications

| Component | Height | Background | Content |
|-----------|--------|------------|---------|
| Header | 64px | Primary (`#0f2540`) | Project title, GitHub link |
| Hero | Auto | White | Statistics cards, Download button |
| Playground | Auto | Surface (`#f5f7fa`) | Query textarea, Example dropdown, Results table, Schema reference (side panel) |
| Footer | Auto | Surface (`#f5f7fa`) | Data source, License, Version |

**Button Styles:**
- Download: Accent 2 (`#f9bf45`) background, Primary text
- Run Query: Secondary (`#51a8dd`) background, White text

#### 5.4.6 Example Queries for Playground

| Label | Description |
|-------|-------------|
| High Protein Foods | Top 10 foods with highest protein |
| Search by Name (LIKE) | Search foods using LIKE pattern |
| Food Nutrients | All nutrients for a specific food |
| High Protein + Low Fat | Filter protein >20g and fat <5g |
| Recipe Calculation | Calculate nutrients for ingredients |
| Vitamin Search | Search nutrients containing vitamin |
| Category List | All categories with food counts |

> **Note:** FTS5 full-text search is not available in the web playground due to sql.js limitations. Use `LIKE` queries for text search. FTS5 works with the downloaded database using native SQLite.

**Query Implementations:**

```sql
-- 1. High Protein Foods
SELECT f.name_zh, fn.value_per_100g as protein_g
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name = '粗蛋白'
ORDER BY protein_g DESC LIMIT 10;

-- 2. Search by Name
SELECT f.code, f.name_zh, f.name_en, c.name as category
FROM foods f
JOIN categories c ON f.category_id = c.id
WHERE f.name_zh LIKE '%雞%' LIMIT 20;

-- 3. Food Nutrients
SELECT n.name, fn.value_per_100g, n.unit
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE f.name_zh = '白飯'
ORDER BY n.id;

-- 4. High Protein + Low Fat
SELECT f.name_zh,
    MAX(CASE WHEN n.name = '粗蛋白' THEN fn.value_per_100g END) as protein,
    MAX(CASE WHEN n.name = '粗脂肪' THEN fn.value_per_100g END) as fat
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name IN ('粗蛋白', '粗脂肪')
GROUP BY f.id HAVING protein > 20 AND fat < 5
ORDER BY protein DESC LIMIT 10;

-- 5. Recipe Calculation
WITH recipe AS (
    SELECT '大番茄平均值(紅色系)' as ingredient, 200.0 as grams
    UNION ALL SELECT '土雞蛋', 120.0
    UNION ALL SELECT '調合植物油', 10.0
)
SELECT n.name, ROUND(SUM(fn.value_per_100g * r.grams / 100), 1) as value, n.unit
FROM recipe r
JOIN foods f ON f.name_zh = r.ingredient
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name IN ('熱量', '粗蛋白', '粗脂肪', '總碳水化合物')
GROUP BY n.name, n.unit;

-- 6. Vitamin Search
SELECT n.name, n.unit FROM nutrients n
WHERE n.name LIKE '%維生素%' ORDER BY n.name;

-- 7. Category List
SELECT c.name, COUNT(f.id) as food_count
FROM categories c LEFT JOIN foods f ON f.category_id = c.id
GROUP BY c.id ORDER BY food_count DESC;
```

#### 5.4.7 Schema Reference

The playground includes a "Schema Reference" panel on the right side with tabbed navigation:
- 5 tabs: `categories`, `nutrient_categories`, `foods`, `nutrients`, `food_nutrients`
- Each tab displays the table's columns and types
- Foreign key relationships shown below each table

The panel is sticky, allowing users to reference the database structure while writing SQL queries. On mobile, the schema panel appears below the query area.

#### 5.4.8 JavaScript Application Logic

**Initialization Flow:**
1. Load SQL.js WASM module
2. Fetch `nutrition.db` via HTTP
3. Initialize database in memory
4. Extract statistics for hero section
5. Enable playground interface

**Key Functions:**

| Function | Description |
|----------|-------------|
| `initSqlJs()` | Load SQL.js library and WASM binary |
| `loadDatabase()` | Fetch and load nutrition.db into memory |
| `executeQuery(sql)` | Run SQL query and return results |
| `displayResults(results)` | Render results as HTML table |
| `loadExampleQuery(id)` | Populate textarea with example query |
| `updateStatistics()` | Fetch and display counts in hero section |

**Error Handling:**
- Display user-friendly messages for SQL syntax errors
- Show loading states during database fetch
- Handle network failures gracefully

#### 5.4.9 Architecture Diagram

```
+-------------------------------------------------------------------+
|                       GitHub Pages                                 |
|                  https://user.github.io/repo                       |
+-------------------------------------------------------------------+
|                                                                    |
|  +--------------------------------------------------------------+ |
|  |  Header (#0f2540)  Taiwan Food Nutrition DB    [GitHub Link] | |
|  +--------------------------------------------------------------+ |
|  |                                                                | |
|  |  +----------------------------------------------------------+ | |
|  |  |                   Hero Section                            | | |
|  |  |  +------------+  +------------+  +------------+           | | |
|  |  |  | Foods      |  | Nutrients  |  | Categories |           | | |
|  |  |  | 2,181      |  | 107        |  | 18         |           | | |
|  |  |  +------------+  +------------+  +------------+           | | |
|  |  |                                                            | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  |  |     Download SQLite Database (#f9bf45 button)      |   | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  +----------------------------------------------------------+ | |
|  |                                                                | |
|  |  +----------------------------------------------------------+ | |
|  |  |                  SQL Playground (#f5f7fa)                 | | |
|  |  |  +----------------------+  +-------------------------+    | | |
|  |  |  | Example Queries  [v] |  |   Run Query (#51a8dd)   |    | | |
|  |  |  +----------------------+  +-------------------------+    | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  |  | SELECT * FROM foods LIMIT 10;                      |   | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  |  |  Results Table                                      |   | | |
|  |  |  |  | id | name_zh | name_en | category |              |   | | |
|  |  |  |  | 1  | 白飯    | Rice    | 穀物類   |              |   | | |
|  |  |  +----------------------------------------------------+   | | |
|  |  +----------------------------------------------------------+ | |
|  |                                                                | |
|  |  +----------------------------------------------------------+ | |
|  |  |  Footer - Data: Taiwan FDA | License: OGL | v2025xxxx    | | |
|  |  +----------------------------------------------------------+ | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  nutrition.db  <-- Loaded via fetch() into SQL.js (~13 MB)        |
|                                                                    |
+-------------------------------------------------------------------+
```

## 6. Use Cases & Decision Tables

### 6.1 Target Users

| User Type | Primary Use Case | Key Requirements |
|-----------|-----------------|------------------|
| Diet Managers | Track daily nutrition | Accurate calorie/macro data |
| Nutritionists | Patient dietary planning | Complete nutrient profiles |
| Fitness Enthusiasts | Optimize protein intake | High-protein food search |
| Chronic Disease Patients | Sodium/sugar restrictions | Filtering capabilities |
| App Developers | Build nutrition apps | Simple SQLite integration |
| AI/ML Researchers | Food recognition training | Structured food database |

### 6.2 Scenario Decision Table

| ID | Scenario | Input Type | Query Type | Output | AI Required |
|----|----------|------------|------------|--------|-------------|
| S1 | Food nutrition lookup | Text | Exact/Fuzzy | Nutrient table | No |
| S2 | Image-based estimation | Image | Classification + Query | Estimated nutrition | High |
| S3 | Label verification | Image + Text | OCR + Compare | Diff report | Medium |
| S4 | Daily intake tracking | Multiple records | Batch + SUM | Daily totals | No |
| S5 | Nutritional filtering | Conditions | Range query | Food list | No |
| S6 | Recipe calculation | Ingredient list | Batch + Weighted SUM | Recipe nutrition | Low |
| S7 | Food substitution | Reference food | Similarity | Suggestion list | Medium |
| S8 | Food comparison | Multiple foods | Parallel query | Comparison table | No |

### 6.3 Database Operation Matrix

| Scenario | SQL Operations | Tables Used | Index Usage | FTS Usage |
|----------|---------------|-------------|-------------|-----------|
| S1 | SELECT + JOIN + FTS | foods, food_nutrients, nutrients | idx_foods_name | foods_fts MATCH/LIKE |
| S2 | SELECT + JOIN | foods, food_nutrients, nutrients | idx_foods_category | - |
| S3 | SELECT + JOIN | foods, food_nutrients, nutrients | idx_foods_name | foods_fts (optional) |
| S4 | SELECT + JOIN + SUM | foods, food_nutrients, nutrients | idx_food_nutrients_food | - |
| S5 | SELECT + WHERE + ORDER | foods, food_nutrients, nutrients | idx_food_nutrients_nutrient | - |
| S6 | SELECT + JOIN + SUM | foods, food_nutrients, nutrients | idx_food_nutrients_food | foods_fts (optional) |
| S7 | SELECT + Calculation + FTS | foods, food_nutrients, nutrients | Multiple indexes | foods_fts MATCH/LIKE |
| S8 | SELECT + JOIN | foods, food_nutrients, nutrients | idx_foods_name | foods_fts (optional) |

### 6.4 Feature Coverage Matrix

| Feature | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Name search | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ |
| Category filter | | ✓ | | | ✓ | | ✓ | |
| Nutrient calculation | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ |
| Condition filter | | | | | ✓ | | ✓ | |
| Aggregation (SUM) | | | | ✓ | | ✓ | | |
| Multi-food handling | | | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Waste rate calculation | | | | | | ✓ | | |

## 7. Test Cases

### 7.1 Testing Architecture

The project uses two complementary testing approaches:

| Type | Tool | Purpose | When Run |
|------|------|---------|----------|
| Unit Tests | pytest | Test build.py functions/behavior | Development (`uv run pytest`) |
| Data Validation | validate.py | Verify output data quality | ETL pipeline (CI) |

**Unit Tests** (`tests/test_build.py`):
- Test ETL function behavior with mock data
- Verify data cleaning transformations work correctly
- Verify P/M/S ratio splitting logic
- NOT part of ETL pipeline (tests code, not data)

**Data Validation** (`validate.py`):
- Run during ETL pipeline in CI
- Verify record counts, referential integrity, data quality
- See Section 8 for validation requirements

### 7.2 Data Cleaning Decision Tables

Decision tables document the transformation logic (conditions → actions):

#### 7.2.1 Numeric Field Parsing

| Condition | Action |
|-----------|--------|
| Has leading/trailing whitespace | TRIM before cast |
| Contains `%` suffix | REPLACE('%', '') then cast |
| Contains `克` suffix | REPLACE('克', '') then cast |
| Contains full-width space `　` | REPLACE to remove |
| Invalid numeric format | TRY_CAST returns NULL |
| Empty string | Returns NULL |
| Scientific notation (e.g., `1.5e-3`) | Supported, converts to decimal |
| Negative numbers | Accepted as-is |

#### 7.2.2 P/M/S Ratio Splitting

| Condition | Has 2+ slashes | Values are numeric | Action |
|-----------|:--------------:|:-----------------:|--------|
| Valid P/M/S | Y | Y | Split into 3 nutrient records |
| Missing part (e.g., `1.52/1.89`) | N | - | Filter out (no records) |
| Extra parts (e.g., `1.52/1.89/1.00/0.5`) | Y | Y | Use first 3 values only |
| Spaces around slashes | Y | Y | TRIM each part, then split |
| Non-numeric values | Y | N | Create records with NULL values |
| Empty string | N | - | Filter out |
| NULL input | - | - | Filter out |

#### 7.2.3 String Normalization

| Condition | Field Applies To | Action |
|-----------|------------------|--------|
| Leading/trailing whitespace | All text fields | TRIM |
| Double space `"  "` | nutrient_category | REPLACE with single space |
| Triple+ spaces | nutrient_category | Only first double→single applied |
| Empty string after TRIM | Optional fields (name_en, alias, description) | NULLIF to NULL |
| Special chars (Greek, etc.) | All text fields | Preserve as-is |
| Tab characters | All text fields | Preserve as-is |

#### 7.2.4 NULL Propagation

| Input State | Field Type | Action |
|-------------|------------|--------|
| NULL | Required (code, name_zh) | Stays NULL (validation catches) |
| NULL | Optional (alias, etc.) | Stays NULL |
| Empty string `""` | Optional fields | Convert to NULL via NULLIF |
| Whitespace only `"   "` | All fields | TRIM to empty, then NULLIF |

### 7.3 Unit Test Cases

Test case tables document what each unit test verifies:

#### 7.3.1 Numeric Parsing Test Cases

| Test ID | Input | Field | Expected | Verifies |
|---------|-------|-------|----------|----------|
| TC-NUM-1 | `"  10.5  "` | waste_rate | `10.5` | Whitespace trimming |
| TC-NUM-2 | `"50%"` | waste_rate | `50.0` | Percent sign removal |
| TC-NUM-3 | `"150%"` | waste_rate | `150.0` | Values >100 accepted |
| TC-NUM-4 | `"-5%"` | waste_rate | `-5.0` | Negative values accepted |
| TC-NUM-5 | `"abc"` | waste_rate | `NULL` | Invalid format handling |
| TC-NUM-6 | `"100克"` | serving_size | `100.0` | Chinese suffix removal |
| TC-NUM-7 | `"　50　"` | serving_size | `50.0` | Full-width space removal |
| TC-NUM-8 | `""` | serving_size | `NULL` | Empty string handling |
| TC-NUM-9 | `"1.5e-3"` | std_deviation | `0.0015` | Scientific notation supported |
| TC-NUM-10 | `"-0.5"` | std_deviation | `-0.5` | Negative decimals |

#### 7.3.2 P/M/S Ratio Test Cases

| Test ID | Input | Expected Records | Verifies |
|---------|-------|------------------|----------|
| TC-PMS-1 | `"1.52/1.89/1.00"` | 3 (P=1.52, M=1.89, S=1.00) | Normal splitting |
| TC-PMS-2 | `"1.52/1.89"` | 0 (filtered) | Insufficient parts rejection |
| TC-PMS-3 | `"1.52/1.89/1.00/0.5"` | 3 (extra ignored) | Extra parts handling |
| TC-PMS-4 | `"1.52 / 1.89 / 1.00"` | 3 (P=1.52, M=1.89, S=1.00) | Spaces around slashes |
| TC-PMS-5 | `" 1.52 / 1.89 / 1.00 "` | 3 | Leading/trailing spaces |
| TC-PMS-6 | `"a/b/c"` | 3 (all NULL values) | Non-numeric handling |
| TC-PMS-7 | `""` | 0 (filtered) | Empty string rejection |
| TC-PMS-8 | `NULL` | 0 (filtered) | NULL rejection |
| TC-PMS-9 | `"0/0/0"` | 3 (all zeros) | Zero values valid |
| TC-PMS-10 | `"-1.52/1.89/1.00"` | 3 (negative accepted) | Negative values |
| TC-PMS-11 | `"///"` | 3 (all NULL values) | Empty parts handling |

#### 7.3.3 String Normalization Test Cases

| Test ID | Input | Field | Expected | Verifies |
|---------|-------|-------|----------|----------|
| TC-STR-1 | `"維生素B群  & C"` | nutrient_category | `"維生素B群 & C"` | Double space collapse |
| TC-STR-2 | `"維生素B群   C"` | nutrient_category | `"維生素B群  C"` | Only first double→single |
| TC-STR-3 | `"  白飯  "` | name_zh | `"白飯"` | Trim whitespace |
| TC-STR-4 | `""` | name_en | `NULL` | Empty to NULL |
| TC-STR-5 | `"β-胡蘿蔔素"` | nutrient_name | `"β-胡蘿蔔素"` | Greek letters preserved |
| TC-STR-6 | `"維生素\tB群"` | nutrient_category | `"維生素\tB群"` | Tab preserved |

#### 7.3.4 NULL Handling Test Cases

| Test ID | Input | Field | Expected | Verifies |
|---------|-------|-------|----------|----------|
| TC-NULL-1 | `NULL` | code | `NULL` | NULL passthrough |
| TC-NULL-2 | `""` | alias | `NULL` | Empty to NULL via NULLIF |
| TC-NULL-3 | `"   "` | description | `NULL` | Whitespace-only to NULL |
| TC-NULL-4 | `NULL` | value_raw | `NULL` | NULL stays string type |

### 7.4 Unit Test Coverage

| Function | Test Focus | File |
|----------|------------|------|
| `clean_data()` | TRIM, REPLACE, TRY_CAST transformations | `tests/test_build.py` |
| `create_normalized_tables()` | Table creation, P/M/S splitting | `tests/test_build.py` |
| `check_fts5_support()` | FTS5 detection returns correct bool | `tests/test_build.py` |

Run unit tests:
```bash
uv run pytest tests/ -v
# or via devbox
devbox run test
```

### 7.5 Query Test Case Summary

The following test cases are reference scenarios for database usage. They document expected query patterns and results:

| Test ID | Scenario | Test Type | Success Criteria |
|---------|----------|-----------|------------------|
| T1-1 | Exact name query | Query | Returns correct nutrients |
| T1-2 | Fuzzy name query | Query | Returns multiple variants |
| T1-3 | Specific nutrient query | Query | Returns filtered results |
| T2-1 | Single food recognition | Integration | Fuzzy match finds food |
| T2-2 | Composite meal | Integration | Aggregation is accurate |
| T3-1 | Label comparison | Validation | Difference within ±20% |
| T4-1 | Daily total | Calculation | Sum is mathematically correct |
| T4-2 | Macro ratio | Calculation | Percentages sum to 100% |
| T5-1 | High protein + low fat | Filter | Results meet criteria |
| T5-2 | Low sodium | Filter | Results below threshold |
| T6-1 | Recipe nutrition | Calculation | Weighted sum is correct |
| T6-2 | Waste rate applied | Calculation | Edible portion calculated |
| T7-1 | Protein substitute | Similarity | Similar protein content |
| T7-2 | Healthier alternative | Comparison | Lower fat, similar protein |
| T8-1 | Multi-food comparison | Query | All foods displayed |
| T8-2 | Cooking method impact | Analysis | Shows variation by method |
| T-FTS-1 | FTS 3+ char MATCH | FTS Query | Returns matching foods/nutrients |
| T-FTS-2 | FTS 2 char LIKE | FTS Query | Returns matching with indexed LIKE |
| T-FTS-3 | FTS Chinese search | FTS Query | 里肌肉 returns chicken/pork tenderloin |
| T-FTS-4 | FTS mixed chars | FTS Query | Greek/English chars correctly matched |
| T-FTS-5 | FTS special chars | FTS Query | β-胡蘿蔔素 style names matched |

### 7.6 Sample Test Queries

#### T1-1: Exact Name Query
```sql
SELECT f.name_zh, n.name, fn.value_per_100g, n.unit
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE f.name_zh = '白飯'
  AND n.name IN ('熱量', '粗蛋白', '總碳水化合物');
```
**Expected**: Returns calorie, protein, and carbohydrate values for white rice.

#### T5-1: High Protein + Low Fat Filter
```sql
SELECT f.name_zh, c.name as category,
    MAX(CASE WHEN n.name = '粗蛋白' THEN fn.value_per_100g END) as protein,
    MAX(CASE WHEN n.name = '粗脂肪' THEN fn.value_per_100g END) as fat
FROM foods f
JOIN categories c ON f.category_id = c.id
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name IN ('粗蛋白', '粗脂肪')
GROUP BY f.id
HAVING protein > 20 AND fat < 5
ORDER BY protein DESC LIMIT 10;
```
**Expected**: Returns foods with >20g protein and <5g fat per 100g.

#### T6-1: Recipe Calculation
```sql
WITH recipe AS (
    SELECT '大番茄平均值(紅色系)' as ingredient, 200.0 as grams
    UNION ALL SELECT '土雞蛋', 120.0
    UNION ALL SELECT '調合植物油', 10.0
)
SELECT n.name, ROUND(SUM(fn.value_per_100g * r.grams / 100), 1) as value, n.unit
FROM recipe r
JOIN foods f ON f.name_zh = r.ingredient
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name IN ('熱量', '粗蛋白', '粗脂肪')
GROUP BY n.name, n.unit;
```
**Expected**: Returns weighted sum of nutrients for the recipe.

#### T-FTS-1: FTS 3+ Character MATCH
```sql
-- Search using FTS MATCH for 3+ characters
SELECT * FROM foods_fts WHERE foods_fts MATCH '維生素';
SELECT * FROM nutrients_fts WHERE nutrients_fts MATCH '維生素';
```
**Expected**: Returns all vitamin-related nutrients (維生素A, B1, B12, etc.)

#### T-FTS-2: FTS 2 Character LIKE
```sql
-- Search using LIKE for 1-2 characters (still uses index)
SELECT * FROM foods_fts WHERE name_zh LIKE '%蛋白%';
SELECT * FROM nutrients_fts WHERE name LIKE '%脂肪%';
```
**Expected**: Returns 粗蛋白 and 粗脂肪 respectively with indexed performance.

#### T-FTS-3: FTS Chinese Search
```sql
-- Chinese food name search
SELECT * FROM foods_fts WHERE foods_fts MATCH '里肌肉';
```
**Expected**: Returns 里肌肉(土雞), 里肌肉(肉雞), 豬大里肌 etc.

#### T-FTS-4: FTS Mixed Characters
```sql
-- Mixed character search (alphanumeric)
SELECT * FROM nutrients_fts WHERE name LIKE '%B1%';
SELECT * FROM foods_fts WHERE name_zh LIKE '%DHA%';
```
**Expected**: Returns 維生素B1, B12 and DHA-related items.

#### T-FTS-5: FTS Special Characters
```sql
-- Special character search (Greek letters)
SELECT * FROM nutrients_fts WHERE nutrients_fts MATCH '胡蘿蔔';
```
**Expected**: Returns β-胡蘿蔔素 correctly.

#### Verify FTS Index Usage
```sql
-- Verify LIKE query uses FTS index
EXPLAIN QUERY PLAN SELECT * FROM foods_fts WHERE name_zh LIKE '%雞%';
-- Expected: VIRTUAL TABLE INDEX (not full table scan)
```

## 8. Validation Requirements

### 8.1 ETL Validation Checks

| Check | Query | Expected |
|-------|-------|----------|
| Food count | `SELECT COUNT(*) FROM foods` | > 2000 |
| Category count | `SELECT COUNT(*) FROM categories` | 18 |
| Nutrient category count | `SELECT COUNT(*) FROM nutrient_categories` | 11 |
| Nutrient count | `SELECT COUNT(*) FROM nutrients` | > 100 |
| No orphan foods | `SELECT COUNT(*) FROM foods WHERE category_id NOT IN (SELECT id FROM categories)` | 0 |
| No orphan nutrients | `SELECT COUNT(*) FROM nutrients WHERE category_id NOT IN (SELECT id FROM nutrient_categories)` | 0 |
| P/M/S processed | Check 3 P/M/S ratio nutrients exist | Yes |
| FTS enabled | Check `report.json` field `fts_enabled` | true (required in CI) |
| FTS tables exist | `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'` | 2 tables (required in CI) |

### 8.2 Data Quality Checks

| Check | Description | Threshold |
|-------|-------------|-----------|
| NULL ratio in calories | `熱量` should rarely be NULL | < 10% |
| Negative values | No negative nutrition values | 0 |
| Outlier detection | Values within reasonable range | Manual review |
| Duplicate foods | No duplicate food codes | 0 |

## 9. Output Artifacts

### 9.1 Release Contents

| File | Description | Size (approx) |
|------|-------------|---------------|
| `nutrition.db` | SQLite database | ~13 MB |
| `USAGE.md` | Database schema and usage guide | ~3 KB |
| `checksums.txt` | SHA256 checksums (by GoReleaser) | ~200 B |

**Artifacts only** (not included in release):
| File | Description |
|------|-------------|
| `report.json` | ETL execution report (for debugging) |

### 9.2 GitHub Pages Contents

| File | Description | Size |
|------|-------------|------|
| `index.html` | Single-page application with playground | ~15 KB |
| `nutrition.db` | SQLite database with FTS5 | ~13 MB |

**Features:**
- Statistics dashboard (foods, nutrients, categories counts)
- Download button for SQLite database
- Interactive SQL playground with SQL.js
- Pre-built example queries (7 common use cases)
- Full-text search support via FTS5 tables
- Sharp, minimal design following design tokens
- No build step required - pure HTML/CSS/JS via CDN

### 9.3 Report Schema

```json
{
  "input_file": "string",
  "counts": {
    "total_records": "integer",
    "foods": "integer",
    "categories": "integer",
    "nutrient_categories": "integer",
    "nutrients": "integer",
    "food_nutrients": "integer"
  },
  "pms_records_processed": "integer",
  "fts_enabled": "boolean",
  "warnings": ["string"]
}
```

| Field | Description |
|-------|-------------|
| fts_enabled | `true` if FTS5 tables were created, `false` if environment lacks support |

### 9.4 USAGE.md Template

The release USAGE.md should contain database schema and usage information:

```markdown
# Taiwan Food Nutrition Database

SQLite database containing nutritional information for Taiwanese foods.

## Data Source

- **Provider**: Taiwan Food and Drug Administration (TFDA)
- **License**: Taiwan Open Government Data License

## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| categories | Food categories (18 types) |
| nutrient_categories | Nutrient groupings (11 types) |
| foods | Food items with metadata |
| nutrients | Nutrient definitions with units |
| food_nutrients | Nutrient values per food (M:N relation) |

### Entity Relationship

    categories 1──N foods N──M nutrients N──1 nutrient_categories
                         └──────food_nutrients──────┘

### Key Columns

**foods**: id, code, name_zh, name_en, category_id, waste_rate, serving_size
**nutrients**: id, category_id, name, unit
**food_nutrients**: food_id, nutrient_id, value_per_100g, sample_count, std_deviation

## Example Queries

### Find high-protein foods
    SELECT f.name_zh, fn.value_per_100g as protein
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.name = '粗蛋白'
    ORDER BY protein DESC LIMIT 10;

### Get all nutrients for a food
    SELECT n.name, fn.value_per_100g, n.unit
    FROM food_nutrients fn
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE fn.food_id = 1;
```

## 10. Future Enhancements

### 10.1 Planned Features

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| Full-Text Search (FTS) | SQLite FTS5 with trigram tokenizer | High | **Implemented** |
| Synonym Table | Map common names to official names | High | Planned |
| Daily Recommended Values | DRI/DRV reference table | Medium | Planned |
| Version Tracking | Track data changes across releases | Medium | Planned |
| Delta Updates | Incremental updates instead of full rebuild | Low | Planned |

### 10.2 FTS Implementation (Trigram)

FTS5 with trigram tokenizer is implemented, providing substring matching without external dependencies.

#### System Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| SQLite | 3.34.0+ with FTS5 | System `sqlite3` command must support FTS5 trigram |
| Python sqlite3 | Not required for FTS | Python module typically lacks FTS5; ETL uses subprocess |

#### CI Environment (GitHub Actions)

The GitHub Actions workflow explicitly installs `sqlite3` package to ensure FTS5 support:

```yaml
- name: Install dependencies
  run: |
    pip install duckdb
    sudo apt-get update && sudo apt-get install -y sqlite3

- name: Verify FTS5 support
  run: |
    sqlite3 :memory: "CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram');"
```

FTS5 is **required** in CI - the workflow will fail if FTS5 is not available.

#### Local Environment (Graceful Degradation)

For local development, the ETL pipeline detects FTS5 support at runtime:

```bash
# Check FTS5 trigram support
sqlite3 :memory: "CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram');"
```

| Environment | Behavior | Database Capability |
|-------------|----------|---------------------|
| FTS5 supported | Creates FTS indexes | Full functionality with fast full-text search |
| FTS5 not supported | Skips FTS creation with warning | Basic functionality using LIKE queries (slower) |

The `fts_enabled` field in the report file records the FTS status.

#### FTS5 Tables

```sql
-- FTS5 tables with trigram tokenizer (no external dependencies)
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
```

#### Search Strategy

| Query Length | Method | Example |
|--------------|--------|---------|
| 3+ characters | FTS MATCH | `WHERE foods_fts MATCH '雞胸肉'` |
| 1-2 characters | LIKE (indexed) | `WHERE name_zh LIKE '%蛋%'` |

Both methods use FTS indexes for acceleration (when FTS5 is available).

### 10.3 Future: Synonym Table

```sql
-- Synonym table for AI integration
CREATE TABLE food_synonyms (
    id INTEGER PRIMARY KEY,
    food_id INTEGER REFERENCES foods(id),
    synonym TEXT NOT NULL,
    source TEXT  -- 'common', 'ai', 'user'
);

-- Example synonyms
-- 雞胸肉 → 里肌肉(土雞), 里肌肉(肉雞)
-- 白飯 → 白飯, 米飯
```

## 11. Usage Examples

### 11.1 Basic Query

```python
import sqlite3

conn = sqlite3.connect('nutrition.db')

# Find high-protein foods
cursor = conn.execute('''
    SELECT f.name_zh, fn.value_per_100g as protein
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.name = '粗蛋白'
    ORDER BY protein DESC
    LIMIT 10
''')

for row in cursor:
    print(f"{row[0]}: {row[1]}g protein")
```

### 11.2 Integration with AI

```python
# Pseudo-code for AI food recognition integration
def get_nutrition_from_image(image_path):
    # Step 1: AI identifies food
    recognized_food = ai_model.recognize(image_path)
    # Result: "白飯" or ["白飯", "雞腿", "青菜"]

    # Step 2: Query database with fuzzy matching
    foods = db.query('''
        SELECT * FROM foods
        WHERE name_zh LIKE ?
    ''', f'%{recognized_food}%')

    # Step 3: Get nutrition data
    nutrition = db.query('''
        SELECT n.name, fn.value_per_100g, n.unit
        FROM food_nutrients fn
        JOIN nutrients n ON fn.nutrient_id = n.id
        WHERE fn.food_id = ?
    ''', foods[0]['id'])

    return nutrition
```

## 12. License & Attribution

- **Data Source**: Taiwan Food and Drug Administration
- **Data License**: Taiwan Open Government Data License
- **Project License**: MIT (for ETL code)

---

*Last Updated: 2025-12-24*
*Version: 1.0.0*
