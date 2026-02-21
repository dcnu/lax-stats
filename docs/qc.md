# QC Validation

Data quality checks run after loading to detect mismatches between source data and database state.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/qc/assess_data_quality.py` | Scan all games for data quality issues; output terminal table or JSON |
| `scripts/qc/fill_missing_stats.py` | Reconstruct `player_game_stats` from play-by-play for games with missing or mismatched data |
| `scripts/transform/qc.py` | Pre-load validation on canonical types (errors block loading, warnings are logged) |

## Check Inventory

### assess_data_quality.py

| Check | Type | Trigger |
|-------|------|---------|
| `MISSING_FILE` | Error | No `player_stats.json` file and no loaded stats for the game |
| `GOAL_MISMATCH` | Error | Sum of player goals in DB does not match game score |
| `NO_PBP` | Info | No play-by-play file exists (limits recovery options) |

### transform/qc.py (validate_game_package)

| Check | Type | Trigger |
|-------|------|---------|
| Score mismatch | Error | Sum of player goals != game score for either side |
| Missing players | Warning | Game has zero player stats |
| Empty plays | Warning | Game has zero play-by-play entries |

## Errors vs Warnings

- **Errors** block loading. A game with QC errors is skipped by the loader and logged to stderr. Fix the underlying data and re-run.
- **Warnings** are logged to stderr but do not block loading. They indicate data that is loadable but potentially incomplete.

## Recovery Paths

### Re-fetch specific games

```bash
python scripts/fetching/fetch_games_ncaa.py --season 2026 --division 1 \
	--force-games 12345,12346
```

### Fill missing stats from play-by-play

```bash
# Single game
python scripts/qc/fill_missing_stats.py --game 12345

# All games with missing files
python scripts/qc/fill_missing_stats.py --all-missing --season 2026

# Preview without writing
python scripts/qc/fill_missing_stats.py --all-missing --dry-run
```

### Re-run the full pipeline

```bash
python scripts/sync_daily.py --season 2026
```

This re-discovers game IDs, re-fetches, re-loads, and re-enriches. All steps are idempotent.
