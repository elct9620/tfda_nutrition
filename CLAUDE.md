# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Taiwan FDA Nutrition Database ETL pipeline - converts Taiwan Food and Drug Administration nutrition data (JSON) to a normalized SQLite database with full-text search support.

## Development Commands

```bash
# Enter development environment (provides uv package manager)
devbox shell

# Or use direnv for automatic activation
# The .envrc file auto-activates the .venv when entering the directory

# Run the main script
uv run main.py

# Add dependencies
uv add <package>

# Tests (not yet configured)
devbox run test

# Browser Automation
npx agent-browser install --with-deps
npx agent-browser open example.com
npx agent-browser snapshot                    # Get accessibility tree with refs
npx agent-browser click @e2                   # Click by ref from snapshot
npx agent-browser fill @e3 "test@example.com" # Fill by ref
npx agent-browser get text @e1                # Get text by ref
npx agent-browser screenshot page.png
npx agent-browser close
```


## Architecture

### ETL Pipeline Flow
1. Download FDA JSON data from `https://data.fda.gov.tw/data/opendata/export/20/json`
2. Process with DuckDB (in-memory)
3. Transform and normalize into relational tables
4. Export to SQLite with FTS5 full-text search
5. Validate and generate report

### Database Schema (5 normalized tables)
- `categories` - Food categories
- `nutrient_categories` - Nutrient type classifications
- `foods` - Food items with metadata
- `nutrients` - Nutrient definitions with units
- `food_nutrients` - M:N relationship with values, sample counts, std deviation

### Key Technologies
- **DuckDB**: In-memory data processing and transformation
- **SQLite + FTS5**: Output database with Chinese full-text search (trigram tokenizer)
- **UV**: Python package manager
- **Devbox**: Nix-based reproducible development environment

## Specification

See `SPEC.md` for comprehensive details including:
- Data cleaning rules and transformation logic
- Complete database schema with indexes
- GitHub Actions workflow configuration
- Test cases (16 scenarios including FTS tests)
- Use case decision tables
