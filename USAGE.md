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

```
categories 1──N foods N──M nutrients N──1 nutrient_categories
                     └──────food_nutrients──────┘
```

### Key Columns

**foods**: id, code, name_zh, name_en, category_id, waste_rate, serving_size

**nutrients**: id, category_id, name, unit

**food_nutrients**: food_id, nutrient_id, value_per_100g, sample_count, std_deviation

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
