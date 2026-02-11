# Lacrosse Stats

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Node.js 20+](https://img.shields.io/badge/Node.js-20+-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

NCAA men's lacrosse statistics pipeline with Supabase PostgreSQL storage and Next.js web dashboard.

## Overview

Automated collection and analysis of NCAA lacrosse game data:

- **Data Pipeline**: Scrapes games, player stats, and play-by-play from NCAA
- **Database**: Supabase (PostgreSQL) with Prisma ORM
- **Quality Control**: Automated validation and gap-filling from play-by-play
- **Daily Sync**: Cron job for nightly updates during season
- **Web Dashboard**: Next.js app for stats exploration

## Features

- **Multi-division support**: D1, D2, D3 data collection
- **Multi-season historical data**: Tracks multiple seasons with season-specific configurations
- **Automated daily sync**: Cron-based nightly updates during active season
- **Play-by-play gap filling**: Recovers missing stats from play-by-play data
- **Natural language queries**: SQL generation from plain English (requires Anthropic API key)
- **Data quality monitoring**: Automated validation with detailed mismatch reports

## Tech Stack

| Layer | Technology |
|-------|------------|
| Scraping | Python (BeautifulSoup, requests) |
| Database | Supabase (PostgreSQL) + Prisma ORM |
| Backend | Next.js 16 API Routes |
| Frontend | React + TypeScript + TailwindCSS |
| UI Components | shadcn/ui |
| Charts | Recharts |
| DB Driver | psycopg2-binary |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ and pnpm

### Setup

```bash
# Clone and install Python dependencies
git clone <repository-url>
cd lacrosse-stats
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Set DATABASE_URL in .env.local for Supabase connection

# Initialize database schema
cd web && pnpm install && pnpm prisma db push

# Verify setup
cd .. && python scripts/qc/assess_data_quality.py
```

### Load Existing Data

```bash
# Load scraped data to database
python scripts/loading/load_teams.py --season 2025
python scripts/loading/load_games.py --season 2025
python scripts/loading/load_players.py --season 2025
python scripts/loading/load_player_stats.py --season 2025
```

### Start Web Dashboard

```bash
cd web && pnpm dev
# Open http://localhost:3000
```

## Data Pipeline

### Directory Structure

```
data/
└── {season}/                    # e.g., "2025", "2026"
    └── division{n}/             # division1, division2, division3
        ├── raw/
        │   ├── rosters.json     # Team rosters (source of truth)
        │   └── game_ids.json    # Discovered game IDs
        └── games/
            ├── game_{id}_info.json          # Game metadata
            ├── game_{id}_player_stats.json  # Player stats
            └── game_{id}_plays.json         # Play-by-play
```

### Data Hierarchy

1. **Rosters** - Source of truth for player→team mapping
2. **Games** - Game metadata, scores, team IDs
3. **Player Stats** - Per-game statistics, validated against rosters
4. **Plays** - Play-by-play, used for QC and derived stats

### Scraping Workflow

```bash
# 1. Discover game IDs for date range
python scripts/utils/get_game_ids.py --season 2026 --start-date 02/01/2026 --end-date 05/31/2026

# 2. Fetch game data and play-by-play
python main.py --season 2026

# 3. Load to database
python scripts/loading/load_teams.py --season 2026
python scripts/loading/load_games.py --season 2026
python scripts/loading/load_players.py --season 2026
python scripts/loading/load_player_stats.py --season 2026

# 4. Run quality control
python scripts/qc/assess_data_quality.py --season 2026
```

## Daily Sync (Cron)

Automated nightly updates during season:

```bash
# Install cron job (runs at midnight local time)
./scripts/cron/setup_cron.sh install

# Check status
./scripts/cron/setup_cron.sh status

# Manual run
./scripts/cron/setup_cron.sh run
```

The sync discovers yesterday's games, fetches data, loads to database, and runs QC.

## Quality Control

### Assessment

```bash
# Check data quality (terminal table output)
python scripts/qc/assess_data_quality.py

# Filter by season/division
python scripts/qc/assess_data_quality.py --season 2025 --division 1

# JSON output for automation
python scripts/qc/assess_data_quality.py --json
```

Sample output:
```
┌─────────┬─────────────────────────────┬────────────┬─────────┬──────────┬───────────────┐
│ Game ID │ Teams                       │ Expected   │ Actual  │ Delta    │ Cause         │
├─────────┼─────────────────────────────┼────────────┼─────────┼──────────┼───────────────┤
│ 6310370 │ Villanova vs Yale           │ 13-11 (24) │ 12-11   │ -1 home  │ GOAL_MISMATCH*│
└─────────┴─────────────────────────────┴────────────┴─────────┴──────────┴───────────────┘
* = Play-by-play available for recovery
```

### Fill Missing Data

```bash
# Fill specific game from play-by-play
python scripts/qc/fill_missing_stats.py --game 6380961

# Fill all games with missing files
python scripts/qc/fill_missing_stats.py --all-missing

# Dry run
python scripts/qc/fill_missing_stats.py --all-missing --dry-run
```

## Project Structure

```
lacrosse-stats/
├── main.py                      # Batch scraper orchestration
├── scripts/
│   ├── fetching/                # NCAA web scrapers
│   │   ├── fetch_game_data.py   # Game info + player stats
│   │   └── fetch_game_plays.py  # Play-by-play
│   ├── loading/                 # Database loaders
│   │   ├── load_teams.py
│   │   ├── load_games.py
│   │   ├── load_players.py
│   │   └── load_player_stats.py
│   ├── qc/                      # Quality control
│   │   ├── assess_data_quality.py
│   │   └── fill_missing_stats.py
│   ├── cron/                    # Scheduled tasks
│   │   └── setup_cron.sh
│   ├── sync_daily.py            # Daily sync orchestration
│   └── utils/
│       ├── db.py                # PostgreSQL helpers
│       ├── roster_lookup.py     # Player→team mapping
│       ├── pbp_parser.py        # Play-by-play parsing
│       └── get_game_ids.py      # Game discovery
├── data/                        # Scraped JSON files
└── web/                         # Next.js dashboard
    ├── prisma/schema.prisma     # Database schema
    └── src/app/                 # App Router pages
```

## Database Schema

Core tables:
- `teams` - NCAA teams (TEXT primary key = NCAA ID)
- `players` - Player records (BIGINT primary key = NCAA player ID)
- `games` - Games with scores and metadata
- `player_game_stats` - Individual player stats per game
- `player_seasons` - Season-specific player attributes

See `web/prisma/schema.prisma` for complete schema.

## Verification Queries

```sql
-- Row counts
SELECT 'teams' as tbl, COUNT(*) FROM teams
UNION ALL SELECT 'players', COUNT(*) FROM players
UNION ALL SELECT 'games', COUNT(*) FROM games
UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats;

-- Data integrity: all player teams match game teams
SELECT COUNT(*) FROM player_game_stats pgs
JOIN games g ON pgs.game_id = g.id
WHERE pgs.team_id NOT IN (g.home_team_id, g.away_team_id);
-- Expected: 0

-- Goals match scores
SELECT g.id, g.home_score, SUM(CASE WHEN pgs.team_id = g.home_team_id THEN pgs.goals ELSE 0 END) as calc_home
FROM games g
JOIN player_game_stats pgs ON pgs.game_id = g.id
GROUP BY g.id
HAVING g.home_score != SUM(CASE WHEN pgs.team_id = g.home_team_id THEN pgs.goals ELSE 0 END);
```

## Rate Limiting

The scraper respects NCAA website resources:
- Base delay: 0.625s between requests
- Random jitter: 0.125-0.375s
- Max 60 requests/minute
- Daily limit: 4,000 requests
- Exponential backoff for errors

## API Endpoints

Base URL: `http://localhost:3000/api`

### GET /seasons
Returns available seasons.
```json
[{ "id": "2026" }, { "id": "2025" }]
```

### GET /stats/recent-games
Returns recent completed games.

| Param | Default | Description |
|-------|---------|-------------|
| seasonId | 2025 | Season filter |
| limit | 30 | Max results |

```json
[{
  "id": "6380961",
  "date": "2025-05-26",
  "home_team": "Syracuse",
  "home_score": 13,
  "away_team": "Duke",
  "away_score": 11
}]
```

### GET /stats/top-scorers
Returns player scoring leaders with aggregated stats.

| Param | Default | Description |
|-------|---------|-------------|
| seasonId | 2025 | Season filter |
| limit | 50 | Max results |

```json
[{
  "player_name": "Brennan O'Neill",
  "team_name": "Duke",
  "games_played": 18,
  "total_goals": 65,
  "total_assists": 23,
  "total_points": 88,
  "points_per_game": 4.89
}]
```

### GET /stats/team-standings
Returns team win/loss records and goal differentials.

| Param | Default | Description |
|-------|---------|-------------|
| seasonId | 2025 | Season filter |

```json
[{
  "team_name": "Notre Dame",
  "wins": 17,
  "losses": 3,
  "win_pct": ".850",
  "goals_for": 289,
  "goals_against": 178,
  "goal_diff": 111
}]
```

### POST /query
Natural language or direct SQL queries (requires ANTHROPIC_API_KEY).

**Request:**
```json
{ "query": "Who led the ACC in goals?", "seasonId": "2025" }
```
or
```json
{ "sql": "SELECT name FROM players LIMIT 5" }
```

**Response:**
```json
{ "data": [...], "sql": "SELECT ...", "rowCount": 10 }
```

## Troubleshooting

### Scraping

- **403 Blocked**: Wait several hours, use VPN, or increase delays
- **429 Rate Limited**: Automatic backoff; increase `base_delay` if persistent
- **Missing Games**: Check `data/raw/failed_games.json`

### Database

- **Connection Error**: Verify `DATABASE_URL` in `.env.local` is correct
- **Schema Mismatch**: Run `pnpm prisma db push` in web/
- **Foreign Key Errors**: Load in order: teams → games → players → stats

### QC

- **GOAL_MISMATCH**: Can often be fixed with `fill_missing_stats.py`
- **MISSING_FILE**: Check if play-by-play exists for recovery

## License

MIT License. See [LICENSE](LICENSE) for details.
