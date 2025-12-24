# Taiwan FDA Food Nutrition Database

ETL pipeline that transforms Taiwan FDA nutrition data into a normalized SQLite database.

```
+----------------+     +----------------+     +----------------+
|   Taiwan FDA   |     |  ETL Pipeline  |     |    SQLite DB   |
|   Open Data    | --> |  (DuckDB)      | --> |  + FTS5 Search |
|   (JSON)       |     |                |     |                |
+----------------+     +----------------+     +----------------+
```

## Features

| Feature | Description |
|---------|-------------|
| Normalized Schema | 5 relational tables with proper foreign keys |
| Full-Text Search | FTS5 with trigram tokenizer for Chinese text |
| Automated Updates | Monthly builds via GitHub Actions |
| SQL Playground | Interactive queries in browser |

## Usage

| Method | Link |
|--------|------|
| Online Playground | [GitHub Pages](https://elct9620.github.io/tfda_nutrition) |
| Download Database | [GitHub Releases](https://github.com/elct9620/tfda_nutrition/releases) |
| Documentation | [USAGE.md](USAGE.md) |

```python
import sqlite3

conn = sqlite3.connect('nutrition.db')

# Find high-protein foods
for row in conn.execute('''
    SELECT f.name_zh, fn.value_per_100g AS protein
    FROM foods f
    JOIN food_nutrients fn ON f.id = fn.food_id
    JOIN nutrients n ON fn.nutrient_id = n.id
    WHERE n.name = '粗蛋白'
    ORDER BY protein DESC LIMIT 5
'''):
    print(f"{row[0]}: {row[1]}g")
```

## License

| Component | License |
|-----------|---------|
| Data | [Taiwan Open Government Data License](https://data.gov.tw/license) |
| Code | [MIT License](LICENSE) |
