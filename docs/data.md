# Data Differences

## 2026+ Game Info: Overtime Fields

The JS-based extractor (`_extract_game_info.js`) produces two fields not present in 2025 data:

| Field | Type | Description |
|-------|------|-------------|
| `isOvertime` | boolean | Whether the game went to overtime |
| `overtimePeriods` | integer | Number of overtime periods (0 if regulation) |

These fields are written to `game_{id}_info.json` but **not yet loaded into the database**. The `games` table has no corresponding columns.

### Future Work

1. Add columns to `games` table: `is_overtime boolean DEFAULT false`, `overtime_periods smallint DEFAULT 0`
2. Update `load_games.py` INSERT to include the new columns
3. Backfill 2025 data by re-running the extractor or inferring from period count in play-by-play

## NCAA Box Score Error Flags

Some games on stats.ncaa.org display a banner: "This box score has errors and the data will not be reflected in season to date stats or national rankings until the following errors are fixed." These are typically stat total mismatches (e.g. team assist total != sum of player assists).

The fetcher saves these to `data/{season}/division{n}/games/flagged_games.json` with each entry containing:

| Field | Type | Description |
|-------|------|-------------|
| `gameID` | string | NCAA game ID |
| `error` | string | Full error text from the banner |
| `awayTeam` | string | Away team name |
| `homeTeam` | string | Home team name |
| `gameDate` | string | Game date MM/DD/YYYY |

The data is still fetched and saved — the flag is informational only.

### Future Work

1. Add `has_stat_errors boolean DEFAULT false` column to `games` table
2. Parse the error text to identify which stat(s) are wrong and for which team
3. Re-check flagged games on subsequent syncs (NCAA may fix the data)
4. Consider whether to exclude flagged games from rankings/aggregates

## Box Score Not Available

Some game IDs in `game_ids.json` point to pages with no data ("Box score not available"). These are typically future games or games where stats haven't been submitted. They are recorded in `failed_games.json` and skipped. Re-running the fetcher will retry them automatically since no output files are written.
