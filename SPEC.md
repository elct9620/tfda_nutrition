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

| Trigger | Condition | Jobs |
|---------|-----------|------|
| Schedule | Monthly on 1st (`0 0 1 * *`) | etl, release, pages |
| Manual | `workflow_dispatch` with release option | etl, (release), pages |
| Push | `main` branch | etl, pages |

```yaml
on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly on 1st
  workflow_dispatch: ...  # Manual trigger with release option
  push:
    branches: [main]
jobs:
  etl: ...     # Download → Clean → Normalize → Export → Validate
  release: ... # GoReleaser for GitHub Releases (schedule/manual only)
  pages: ...   # Deploy playground to GitHub Pages
```

#### ETL Job Key Steps

| Step | Purpose |
|------|---------|
| Generate version | Date-based versioning (vYYYYMMDD) with suffix for same-day runs |
| Setup Python | Python 3.13 with DuckDB |
| Install sqlite3 | System sqlite3 for FTS5 support |
| Verify FTS5 | Fail early if trigram tokenizer unavailable |
| Download FDA data | Fetch and unzip from official API |
| Run ETL | Execute `build.py` with input/output paths |
| Verify FTS enabled | Ensure FTS tables created (CI requirement) |
| Run validation | Execute `validate.py` for data quality checks |
| Upload artifacts | `nutrition.db`, `report.json`, `USAGE.md` |
| Write Job Summary | Generate markdown report to `$GITHUB_STEP_SUMMARY` |

#### Job Summary Format

The ETL job writes a markdown summary for GitHub Actions UI:

```markdown
## Food Nutrition ETL Report

**Version**: v20251224
**Trigger**: schedule

| Metric | Value |
|--------|-------|
| Total Records | 233527 |
| Foods | 2181 |
| Nutrients | 107 |
| Categories | 18 |
| FTS5 Full-Text Search | Enabled |
```

#### Workflow Stages

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

### 5.2 GoReleaser Configuration

```yaml
project_name: taiwan-food-nutrition
builds: []  # No binary builds needed
release:
  extra_files:
    - glob: nutrition.db
    - glob: USAGE.md
checksum:
  name_template: 'checksums.txt'
changelog: ...
```

### 5.3 GitHub Pages Architecture

#### Page Structure

| Section | Purpose |
|---------|---------|
| Hero | Project overview, statistics, download button |
| Playground | Interactive SQL query interface with schema reference |

#### Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#0f2540` | Headers, dark backgrounds |
| Secondary | `#51a8dd` | Links, Run Query button |
| Accent 2 | `#f9bf45` | Download button |
| Surface | `#f5f7fa` | Code blocks, result tables |

Style: Sharp corners (`border-radius: 0`), system fonts, no external dependencies.

#### CDN Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| Vue.js | 3.x | Reactive UI (Composition API) |
| TailwindCSS | 3.x | Styling with custom config |
| SQL.js | 1.11.0 | SQLite in browser (WASM) |

> **FTS5 is not available in the web playground.** Standard sql.js does not include FTS5, and available FTS5 forks lack the trigram tokenizer. Use `LIKE` queries for text search in the browser. FTS5 works with the downloaded database using native SQLite.

#### Example Queries

| Label | Description |
|-------|-------------|
| High Protein Foods | Top 10 foods with highest protein |
| Search by Name (LIKE) | Search foods using LIKE pattern |
| Food Nutrients | All nutrients for a specific food |
| High Protein + Low Fat | Filter protein >20g and fat <5g |
| Recipe Calculation | Calculate nutrients for ingredients |
| Vitamin Search | Search nutrients containing vitamin |
| Category List | All categories with food counts |

#### Schema Reference Panel

The playground includes a sticky "Schema Reference" panel with tabbed navigation for all 5 tables, showing columns, types, and foreign key relationships.

#### Loading Progress Bar

Multi-stage progress indicator for database loading (~13 MB):

| Stage | Display | Progress Bar |
|-------|---------|--------------|
| 1. SQL.js init | "Loading SQL.js..." | Indeterminate (pulsing) |
| 2. Download | "Downloading database... X.X MB / Y.Y MB" | Determinate (fills with progress) |
| 3. Initialize | "Initializing database..." | Indeterminate (pulsing) |

- Uses `fetch` with streaming to track download progress via `Content-Length` header
- Falls back to estimated size (~13 MB) if header unavailable
- Visual bar follows design tokens: `bg-secondary` fill, `bg-gray-200` track, sharp corners

#### Page Layout

```
+-------------------------------------------------------------------+
|                       GitHub Pages                                 |
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

### 5.4 Test Workflow

| Trigger | Jobs |
|---------|------|
| Push to `main` | test |
| Pull request to `main` | test |

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  test:
    steps:
      - uses: actions/checkout@v6
      - name: Set up Python ...
      - name: Install uv ...
      - name: Install dependencies ...
      - run: uv run pytest tests/ -v
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

### 7.6 Key Test Query Examples

Representative SQL patterns for implementing the test cases above:

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

#### T6-1: Recipe Calculation (Weighted Sum)
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

#### T-FTS-1: FTS Search (3+ Characters)
```sql
-- FTS MATCH for 3+ character queries
SELECT * FROM foods_fts WHERE foods_fts MATCH '雞胸肉';
SELECT * FROM nutrients_fts WHERE nutrients_fts MATCH '維生素';

-- LIKE for 1-2 character queries (still uses FTS index)
SELECT * FROM foods_fts WHERE name_zh LIKE '%蛋%';
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

#### Environment Behavior

| Environment | Behavior | Database Capability |
|-------------|----------|---------------------|
| CI (GitHub Actions) | FTS5 **required** - workflow fails if unavailable | Full FTS5 support |
| Local (FTS5 supported) | Creates FTS indexes | Full functionality |
| Local (FTS5 not supported) | Skips FTS creation with warning | Basic LIKE queries only |

The `fts_enabled` field in the report file records the FTS status.

#### FTS5 Tables

```sql
CREATE VIRTUAL TABLE foods_fts USING fts5(
    name_zh, name_en, alias,
    content='foods', content_rowid='id',
    tokenize='trigram'
);

CREATE VIRTUAL TABLE nutrients_fts USING fts5(
    name,
    content='nutrients', content_rowid='id',
    tokenize='trigram'
);
```

#### Search Strategy

| Query Length | Method | Example |
|--------------|--------|---------|
| 3+ characters | FTS MATCH | `WHERE foods_fts MATCH '雞胸肉'` |
| 1-2 characters | LIKE (indexed) | `WHERE name_zh LIKE '%蛋%'` |

## 11. License & Attribution

- **Data Source**: Taiwan Food and Drug Administration
- **Data License**: Taiwan Open Government Data License
- **Project License**: MIT (for ETL code)

---

*Last Updated: 2025-12-24*
*Version: 1.0.0*
