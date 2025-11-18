# Lacrosse Stats

A complete system for scraping and storing NCAA men's lacrosse statistics across all divisions (D1, D2, D3). Features web scraping with intelligent rate limiting, Supabase database integration, and comprehensive data analysis capabilities.

## Overview

This project automates the collection and storage of NCAA men's lacrosse game data from the NCAA stats website across all three divisions. The system includes:

1. **Web Scraper**: Collects game data, player statistics, and play-by-play information
2. **Database System**: Stores all data in Supabase with optimized schema
3. **Data Loaders**: Batch processing scripts to populate the database

## Features

### Data Collection
- **Game Information**: Metadata, scores, venue, attendance
- **Player Statistics**: Individual performance metrics per game
- **Play-by-Play Data**: Detailed event-by-event game records
- **Team Rosters**: Player biographical information and positions

### Technical Features
- **Intelligent Rate Limiting**: Configurable delays with jitter and burst protection
- **Robust Error Handling**: Exponential backoff, retry logic, HTTP status code handling
- **Comprehensive Logging**: Performance metrics and error tracking
- **Multi-threaded Processing**: Parallel scraping with shared rate limiting
- **Database Integration**: Automated loading to Supabase with deduplication

## Database Schema

The system stores data in Supabase with the following structure:

### Core Tables
- **`teams`** - NCAA teams across all divisions (TEXT primary key using NCAA IDs)
- **`players`** - Player records with biographical information (BIGINT primary key using NCAA player IDs)
- **`games`** - Games with scores and metadata (TEXT primary key using NCAA game IDs)
- **`player_game_stats`** - Individual player statistics per game
- **`game_plays`** - Play-by-play events

### Multi-Season and Division Support Tables
- **`divisions`** - Division reference table (D1, D2, D3)
- **`seasons`** - Season reference table (2025, 2026, etc.) with division_id
- **`team_seasons`** - Season-specific team attributes (names, conferences) per division
- **`player_seasons`** - Season-specific player attributes (jersey numbers, positions) per division
- **`player_season_stats_view`** - Materialized view of aggregated season statistics by division

**Note**: Uses external NCAA IDs as primary keys (not UUIDs) for direct data correlation.

### Multi-Season Features

The database supports multiple seasons with per-season tracking of:
- Player jersey numbers and positions (which change between seasons)
- Team names and conference affiliations
- Player transfers between teams
- Historical season comparisons

See `TODO/MIGRATION_GUIDE.md` and `TODO/MULTI_SEASON_SUMMARY.md` for details on multi-season architecture and migration.

## Installation

### Prerequisites

- Python 3.8+
- Supabase account (for database storage)
- Required Python packages: `requests`, `beautifulsoup4`, `pytz`, `supabase`

### Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd lacrosse-stats
   ```

2. **Install Python dependencies**

   ```bash
   pip install requests beautifulsoup4 pytz supabase
   ```

3. **Configure Supabase**

   Create `.env.local` with your Supabase credentials:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your-service-role-key
   ```

   Update `config.json` with your Supabase URL and anon key:
   ```json
   {
     "supabase_url": "https://your-project.supabase.co",
     "supabase_key": "your-anon-key"
   }
   ```

4. **Initialize Database Schema**

   Execute `scripts/loading/reset_database.sql` in your Supabase SQL Editor to create tables.

5. **Set Up Database Keep-Alive (Optional)**

   Keep your Supabase free tier active with automated pings:
   ```bash
   bash scripts/utils/setup_cron.sh
   ```
   This schedules database pings twice per week (Tuesday 10am, Friday 2pm).

   Manual ping: `python3 scripts/utils/ping_database.py --verbose`

## Usage

### Directory Structure

Data is organized by season and division in the following structure:
```
data/
└── {season_id}/              # e.g., 2025, 2024, etc.
    ├── division1/            # Division I data
    │   ├── games/            # Game data files
    │   │   ├── game_{id}_info.json
    │   │   ├── game_{id}_player_stats.json
    │   │   └── game_{id}_plays.json
    │   └── raw/              # Raw scraping outputs
    │       ├── game_ids.json
    │       ├── team_ids.json
    │       └── rosters.json
    ├── division2/            # Division II data (when available)
    │   └── ...
    └── division3/            # Division III data (when available)
        └── ...
```

### Complete Workflow

#### 1. Scrape Game Data

```bash
# Get list of games for date range (specify season and optionally division)
python3 scripts/utils/get_game_ids.py --season 2025 --start-date 02/01/2025 --end-date 05/26/2025
python3 scripts/utils/get_game_ids.py --season 2025 --division 2  # For Division II

# Extract team IDs
python3 scripts/utils/team_list.py

# Get team rosters (optional)
python3 scripts/utils/get_rosters.py

# Scrape all game data (specify season and optionally division)
python3 main.py --season 2025                    # Division I (default)
python3 main.py --season 2025 --division 2       # Division II
python3 main.py --season 2025 --division 3       # Division III
```

This creates JSON files in `data/2025/division{n}/games/` with game info, player stats, and plays.

#### 2. Load Data to Supabase

**Note:** Before loading multi-division data, run the schema migration:
```bash
# Run this once to add division support to database
# Execute scripts/loading/add_division_support.sql in Supabase SQL Editor
```

```bash
# Load games (optionally filter by season and/or division)
python3 scripts/loading/load_games_multi_season.py
python3 scripts/loading/load_games_multi_season.py --season 2025
python3 scripts/loading/load_games_multi_season.py --season 2025 --division 1
python3 scripts/loading/load_games_multi_season.py --division 2  # All D2 seasons

# Load player stats
python3 scripts/loading/load_player_stats_multi_season.py
python3 scripts/loading/load_player_stats_multi_season.py --season 2025 --division 1
```

This loads:
- Seasons from game dates
- Teams from game files
- Team-season combinations
- Players from player stats files
- Player-season attributes
- Games with scores and metadata
- Player game statistics

#### 3. Verify Data

Execute verification queries in Supabase SQL Editor:

```sql
-- Check record counts
SELECT 'teams' as table_name, COUNT(*) FROM teams
UNION ALL SELECT 'players', COUNT(*) FROM players
UNION ALL SELECT 'games', COUNT(*) FROM games
UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats
UNION ALL SELECT 'game_plays', COUNT(*) FROM game_plays;

-- Test data relationships
SELECT g.id, t1.name as home_team, t2.name as away_team, g.home_score, g.away_score
FROM games g
JOIN teams t1 ON g.home_team_id = t1.id
JOIN teams t2 ON g.away_team_id = t2.id
LIMIT 10;
```

Full verification queries: `scripts/loading/verify_data.sql`

## Multi-Division Support

The system supports all three NCAA divisions (D1, D2, D3):

### Key Features
- **Data Organization**: Files organized by season and division (`data/{season}/division{n}/`)
- **Independent Scraping**: Each division can be scraped separately
- **Division Filtering**: All loading scripts support `--division` flag
- **Default Behavior**: Division 1 is the default if not specified

### Configuration

Division configuration is stored in `config.json`:

```json
{
  "division": 1,
  "season_division_ids": {
    "1": {
      "2025": 18484,
      "2024": 16520
    },
    "2": {},
    "3": {}
  }
}
```

**Note:** Division 2 and 3 `season_division_ids` must be discovered from the NCAA website. See `TODO/multi_division_plan.md` for research instructions.

### Database Schema

The database includes:
- `divisions` table (reference: D1, D2, D3)
- `division_id` column on all major tables
- Division-aware materialized views
- Indexes optimized for multi-division queries

Run `scripts/loading/add_division_support.sql` to migrate existing databases.

## Configuration

### Scraping Configuration (`config.json`)

```json
{
  "date_ranges": {
    "start_date": "02/01/2025",
    "end_date": "05/26/2025"
  },
  "rate_limiting": {
    "base_delay": 0.625,
    "random_jitter": [0.125, 0.375],
    "burst_protection": true,
    "daily_limit": 4000,
    "requests_per_minute": 60
  },
  "retry_strategy": {
    "max_attempts": 3,
    "base_delay": 5.0,
    "429_backoff_start": 30,
    "max_backoff": 300
  }
}
```

### Database Configuration

- **Service Role Key**: Used for data loading (stored in `.env.local`)
- **Anon Key**: Used for application queries (stored in `config.json`)
- **RLS**: Enabled with public read access for all stats data

## Project Structure

```
lacrosse-stats/
├── main.py                          # Main batch scraper
├── config.json                      # Configuration
├── .env.local                       # Supabase credentials
├── scripts/
│   ├── fetching/                    # Web scraping scripts
│   │   ├── fetch_game_data.py       # Game info and stats scraper
│   │   └── fetch_game_plays.py      # Play-by-play scraper
│   ├── loading/                     # Database loading scripts
│   │   ├── load_teams.py            # Team loader
│   │   ├── load_players.py          # Player loader
│   │   ├── load_games_multi_season.py        # Game loader (multi-season, multi-division)
│   │   ├── load_player_stats_multi_season.py # Player stats loader (multi-season, multi-division)
│   │   ├── load_plays.py            # Play-by-play loader
│   │   ├── add_division_support.sql # Schema migration for multi-division
│   │   ├── reset_database.sql       # Schema creation
│   │   ├── verify_data.sql          # Verification queries
│   │   └── verify_multi_season_migration.sql # Multi-season verification
│   └── utils/                       # Utility scripts
│       ├── get_game_ids.py          # Game discovery
│       ├── team_list.py             # Team extraction
│       ├── get_rosters.py           # Roster scraper
│       ├── migrate_to_division_structure.py  # Reorganize data files by division
│       ├── ping_database.py         # Keep Supabase free tier active
│       ├── setup_cron.sh            # Install database ping cron jobs
│       └── logging_config.py        # Logging setup
├── data/
│   ├── games/                       # Scraped JSON files (1,737 files)
│   └── raw/                         # Raw API data
│       ├── game_ids.json            # Master game list
│       ├── team_ids.json            # Team IDs
│       └── rosters.json             # Player rosters
├── outputs/
│   └── logs/                        # Scraper logs
├── supabase/
│   └── migrations/                  # Active migrations
│       └── 20250131000001_create_new_schema.sql
└── archive/                         # Archived files
    ├── migrations/                  # Old migration attempts
    ├── scripts/                     # Deprecated scripts
    ├── tests/                       # Old test files
    └── docs/                        # Historical docs
```

## Command Reference

### Scraping Commands

```bash
# Get game IDs for date range
python3 scripts/utils/get_game_ids.py

# Extract team IDs
python3 scripts/utils/team_list.py

# Get rosters (optional)
python3 scripts/utils/get_rosters.py [--limit N] [--dry-run]

# Scrape all games
python3 main.py [--config FILE] [--max-workers N] [--sequential]

# Scrape individual game
python3 scripts/fetching/fetch_game_data.py GAME_URL
python3 scripts/fetching/fetch_game_plays.py --test GAME_ID
```

### Data Loading Commands

```bash
# Load individual data types
python3 scripts/loading/load_teams.py [--data-dir DIR] [--dry-run]
python3 scripts/loading/load_players.py [--data-dir DIR] [--dry-run]
python3 scripts/loading/load_games_multi_season.py [--data-dir DIR] [--season YEAR] [--division N] [--dry-run]
python3 scripts/loading/load_player_stats_multi_season.py [--data-dir DIR] [--season YEAR] [--division N] [--dry-run]
python3 scripts/loading/load_plays.py [--data-dir DIR] [--dry-run]

# Ping database to keep free tier active
python3 scripts/utils/ping_database.py [--verbose]
```

**Note**: Use `*_multi_season.py` loaders for games and player stats to ensure proper season and division tracking.

### Monitoring Commands

```bash
# Watch scraper logs
tail -f outputs/logs/lacrosse_scraper_*.log

# Count scraped files
ls data/games/game_*_info.json | wc -l

# Check failed games
cat data/raw/failed_games.json

# Monitor scraping success rate
grep "Successfully fetched" outputs/logs/*.log | wc -l
```

## Data Output

### Scraped Files (JSON)

Each game produces three files in `data/games/`:

1. **`game_{id}_info.json`** - Game metadata
   ```json
   {
     "gameId": "6313129",
     "gameDate": "02/01/2025",
     "homeTeam": "Queens (NC) Royals",
     "homeTeamId": "594044",
     "homeScore": 9,
     "awayTeam": "Mount St. Mary's Mountaineers",
     "awayTeamId": "593988",
     "awayScore": 14,
     "location": "Queens Sports Complex (Charlotte, NC)",
     "attendance": 205
   }
   ```

2. **`game_{id}_player_stats.json`** - Player statistics
   ```json
   [
     {
       "playerId": 8762073,
       "name": "Player Name",
       "jersey": "1",
       "position": "M",
       "Goals": 2,
       "Assists": 1,
       "Points": 3,
       "Shots": 5,
       "SOG": 4,
       "GB": 3,
       "TO": 1,
       "CT": 0
     }
   ]
   ```

3. **`game_{id}_plays.json`** - Play-by-play events
   ```json
   [
     {
       "quarter": "1",
       "time": "15:00",
       "homeEvent": null,
       "awayEvent": "Faceoff won by AWAY",
       "score": "0-0"
     }
   ]
   ```

### Database Tables

All scraped data is normalized and stored in Supabase:

- **teams**: Team master table with NCAA IDs
- **players**: Player master table with biographic info
- **games**: Game records with foreign keys to teams
- **player_game_stats**: Individual player performance per game
- **game_plays**: Sequential play-by-play events

## Rate Limiting

The scraper respects NCAA website resources:

- **Base Delay**: 0.625s between requests
- **Jitter**: 0.125-0.375s random variation
- **Burst Protection**: Max 60 requests/minute
- **Daily Limit**: 4,000 requests/day
- **Exponential Backoff**: Progressive delays for 429/5xx errors
- **Business Hours**: Optional slowdown during EST business hours

## Important Notes

### NCAA ID Changes

The roster extraction URLs use category IDs specific to the 2024-2025 season:
- Category 15649: Field players
- Category 15650: Goalkeepers

**These IDs change annually** in the NCAA database. Update URLs in `scripts/utils/get_rosters.py` for future seasons.

### Data Quality

- The system automatically deduplicates player stats (1,561 duplicates removed from source data)
- Some players appear twice in game files (e.g., played field and goalie)
- The loader keeps the first occurrence of duplicate (game_id, player_id) pairs

### Loading New Data

To load new games, seasons, or divisions after initial setup:

1. Update date range in `config.json`
2. Run scraping workflow with appropriate `--season` and `--division` flags
3. Load data using multi-season loaders:
   ```bash
   python3 scripts/loading/load_games_multi_season.py --season 2025 --division 1
   python3 scripts/loading/load_player_stats_multi_season.py --season 2025 --division 1
   ```

The multi-season loaders automatically:
- Create new season and division records if needed
- Update player_seasons with current jersey numbers and positions
- Maintain team_seasons for each team per season and division
- Refresh aggregated statistics materialized view

## Row Level Security

RLS is enabled on all tables with public read access. When loading new data, use service role key:

1. Update `config.json` to use service role key (from `.env.local`)
2. Run data loading scripts (e.g., `load_games_multi_season.py`, `load_player_stats_multi_season.py`)
3. Restore anon key in `config.json`

**Note**: Service role key bypasses RLS and should only be used for data loading operations.

## Documentation

- **`TODO/tasks.md`** - Project tasks and obsolete file tracking
- **`TODO/MIGRATION_GUIDE.md`** - Multi-season migration instructions
- **`TODO/MULTI_SEASON_SUMMARY.md`** - Multi-season architecture overview
- **`archive/docs/`** - Historical documentation and archived guides

## Troubleshooting

### Scraping Issues

1. **429 Errors**: Increase `base_delay` in config
2. **Timeouts**: Increase `timeout_seconds` or reduce `max_workers`
3. **Failed Games**: Check `data/raw/failed_games.json` and re-run scraper
4. **Missing Data**: Verify date range and ensure NCAA site is accessible

### Database Issues

1. **Connection Errors**: Verify Supabase credentials in `config.json`
2. **Schema Errors**: Re-run `scripts/loading/reset_database.sql`
3. **Foreign Key Violations**: Load in correct order (teams → players → games → stats → plays)
4. **Duplicate Errors**: Already handled by deduplication in loaders

### Verification Failed

Execute verification queries from `scripts/loading/verify_data.sql` to diagnose:
- Missing data
- Broken relationships
- Incorrect record counts

## License

[Add your license here]

## Contributing

[Add contribution guidelines if open source]

## Contact

For questions or support, please refer to the project documentation or create an issue in the repository.
