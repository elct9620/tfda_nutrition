# Taiwan Food Nutrition Database

SQLite database containing nutritional information for Taiwanese foods.

## Data Source

- **Provider**: Taiwan Food and Drug Administration (TFDA)
- **License**: Taiwan Open Government Data License

## Database Schema

### Entity Relationship

```
categories 1──N foods N──M nutrients N──1 nutrient_categories
                     └──────food_nutrients──────┘
```

### Table Definitions

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

### Indexes

| Index Name | Table | Column(s) | Purpose |
|------------|-------|-----------|---------|
| idx_foods_category | foods | category_id | Category filtering |
| idx_foods_name | foods | name_zh | Name search |
| idx_foods_code | foods | code | Code lookup |
| idx_nutrients_category | nutrients | category_id | Nutrient category filtering |
| idx_nutrients_name | nutrients | name | Nutrient search |
| idx_food_nutrients_food | food_nutrients | food_id | Food-based queries |
| idx_food_nutrients_nutrient | food_nutrients | nutrient_id | Nutrient-based queries |

### Full-Text Search (FTS5)

Two FTS5 virtual tables with trigram tokenizer for Chinese text search:

#### foods_fts

| Column | Source |
|--------|--------|
| name_zh | foods.name_zh |
| name_en | foods.name_en |
| alias | foods.alias |

#### nutrients_fts

| Column | Source |
|--------|--------|
| name | nutrients.name |

**Search Strategy:**

| Query Length | Method | Example |
|--------------|--------|---------|
| 3+ characters | FTS MATCH | `WHERE foods_fts MATCH '雞胸肉'` |
| 1-2 characters | LIKE | `WHERE name_zh LIKE '%蛋%'` |

## Example Queries

### Find high-protein foods

```sql
SELECT f.name_zh, fn.value_per_100g as protein
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.name = '粗蛋白'
ORDER BY protein DESC LIMIT 10;
```

### Get all nutrients for a food

```sql
SELECT n.name, fn.value_per_100g, n.unit
FROM food_nutrients fn
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE fn.food_id = 1;
```

### Full-text search (if FTS enabled)

```sql
-- Search for foods containing "雞肉"
SELECT * FROM foods_fts WHERE foods_fts MATCH '雞肉';

-- Search for nutrients containing "維生素"
SELECT * FROM nutrients_fts WHERE nutrients_fts MATCH '維生素';
```

### Find foods by category

```sql
SELECT f.name_zh, f.code
FROM foods f
JOIN categories c ON f.category_id = c.id
WHERE c.name = '魚貝類'
LIMIT 10;
```

### Calculate recipe nutrition

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
