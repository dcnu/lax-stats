# Database Migration Instructions

## Multi-Division Support Migration

This migration adds division tracking to your database schema. All existing data will default to Division I.

### Prerequisites

1. Back up your Supabase database
2. Ensure you have admin access to Supabase SQL Editor

### Migration Steps

#### Option 1: Manual Execution (Recommended)

1. Open your Supabase project
2. Navigate to SQL Editor
3. Open `scripts/loading/add_division_support.sql`
4. Copy the entire contents
5. Paste into Supabase SQL Editor
6. Click "Run" to execute

The migration will:
- Create `divisions` reference table
- Add `division_id` columns to all tables
- Update indexes and constraints
- Recreate materialized view with division support

All existing data defaults to `division_id = 1` (Division I).

#### Option 2: Using psql CLI

If you have direct database access:

```bash
psql "$DATABASE_URL" < scripts/loading/add_division_support.sql
```

### Verification

After migration, run these queries in SQL Editor:

```sql
-- Verify divisions table
SELECT * FROM divisions ORDER BY id;

-- Count records by division
SELECT
    'seasons' AS table_name,
    division_id,
    COUNT(*) AS count
FROM seasons
GROUP BY division_id
UNION ALL
SELECT 'teams', division_id, COUNT(*) FROM teams GROUP BY division_id
UNION ALL
SELECT 'players', division_id, COUNT(*) FROM players GROUP BY division_id
UNION ALL
SELECT 'games', division_id, COUNT(*) FROM games GROUP BY division_id
ORDER BY table_name, division_id;
```

Expected results:
- 3 divisions (1, 2, 3)
- All existing records should have `division_id = 1`

### Post-Migration

Update loading scripts to include `division_id` when inserting data:
- `scripts/loading/load_games_multi_season.py`
- `scripts/loading/load_player_stats_multi_season.py`

### Rollback

If migration fails or you need to rollback, run:

```sql
-- Remove division_id columns
ALTER TABLE seasons DROP COLUMN IF EXISTS division_id;
ALTER TABLE teams DROP COLUMN IF EXISTS division_id;
ALTER TABLE players DROP COLUMN IF EXISTS division_id;
ALTER TABLE games DROP COLUMN IF EXISTS division_id;
ALTER TABLE team_seasons DROP COLUMN IF EXISTS division_id;
ALTER TABLE player_seasons DROP COLUMN IF EXISTS division_id;
ALTER TABLE player_game_stats DROP COLUMN IF EXISTS division_id;
ALTER TABLE game_plays DROP COLUMN IF EXISTS division_id;

-- Drop divisions table
DROP TABLE IF EXISTS divisions CASCADE;

-- Recreate original materialized view
-- (Copy from scripts/loading/reset_database.sql)
```

### Next Steps

After successful migration:
1. Test database queries with division filtering
2. Update loading scripts to write division_id
3. Scrape D2/D3 data when NCAA access is restored
