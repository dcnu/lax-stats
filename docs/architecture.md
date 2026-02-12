# Lacrosse Stats Architecture

NCAA men's lacrosse statistics system with Python data pipeline and Next.js web app, backed by Supabase (PostgreSQL).

## Directory Structure

```
lacrosse-stats/
├── config.json                      # Season IDs, rate limits, scraping config
├── main.py                          # Legacy batch processor (blocked by NCAA CDN)
├── data/
│   └── {season}/                    # e.g., "2025", "2026"
│       └── division{n}/
│           ├── raw/
│           │   ├── rosters.json     # Team rosters (source of truth for player→team)
│           │   └── game_ids.json    # Discovered game IDs
│           ├── rosters/             # Per-team roster files
│           └── games/
│               ├── game_{id}_info.json          # Game metadata
│               ├── game_{id}_player_stats.json  # Player stats per game
│               ├── game_{id}_plays.json         # Play-by-play
│               ├── failed_games.json            # Games with no data on NCAA site
│               └── flagged_games.json           # Games with NCAA stat errors
├── scripts/
│   ├── fetching/                    # Browser-based scrapers (agent-browser CDP)
│   │   ├── fetch_games_browser.py   # Fetches game info, stats, plays
│   │   └── fetch_rosters_browser.py # Fetches team rosters
│   ├── loading/                     # Database loaders (psycopg2 COPY)
│   │   ├── load_teams.py
│   │   ├── load_games.py
│   │   ├── load_players.py
│   │   ├── load_player_stats.py
│   │   ├── load_game_plays.py
│   │   └── enrich_tables.py         # Denormalization (idempotent)
│   ├── qc/
│   │   ├── assess_data_quality.py   # QC assessment
│   │   └── fill_missing_stats.py    # Fill gaps from play-by-play
│   ├── cron/
│   │   ├── setup_cron.sh            # Install/manage macOS launchd job
│   │   └── com.lacrosse-stats.daily-sync.plist
│   ├── sync_daily.py                # Daily sync orchestration
│   └── utils/
│       ├── db.py                    # psycopg2 connection helpers
│       ├── path_helpers.py          # Path resolution
│       ├── roster_lookup.py         # Player → Team lookup from rosters
│       ├── pbp_parser.py            # Play-by-play stat extraction
│       ├── browser_common.py        # Shared CDP/agent-browser helpers
│       ├── get_game_ids.py          # Legacy game ID discovery (requests)
│       ├── get_game_ids_browser.py  # Browser-based game ID discovery
│       ├── get_rosters.py           # Legacy roster fetching
│       ├── _extract_game_info.js    # JS extractor: game metadata
│       ├── _extract_player_stats.js # JS extractor: player stats
│       ├── _extract_plays.js        # JS extractor: play-by-play
│       ├── _extract_games.js        # JS extractor: game ID discovery
│       └── _extract_roster.js       # JS extractor: team rosters
├── web/                             # Next.js 16 app
│   └── src/
│       ├── app/
│       │   ├── (protected)/dashboard/page.tsx
│       │   └── api/
│       │       ├── seasons/route.ts
│       │       └── stats/
│       │           ├── top-scorers/route.ts
│       │           ├── recent-games/route.ts
│       │           └── team-standings/route.ts
│       ├── components/
│       │   ├── data-preview.tsx      # Dashboard tabs
│       │   ├── filterable-table.tsx   # Table with filters/sorting/pagination
│       │   ├── navigation.tsx
│       │   ├── season-dropdown.tsx
│       │   └── ui/                    # shadcn/ui components
│       └── lib/
│           ├── db.ts                  # Supabase + postgres.js clients
│           ├── utils.ts
│           ├── stores/                # Zustand (season selection)
│           └── types/                 # TypeScript types
└── supabase/
    └── migrations/
        ├── 20250210000000_enable_rls.sql
        └── 20260210000000_enrich_tables.sql
```

## Database Schema

Production database on Supabase (project ref: `mrcafhnnublwkgsiubmr`).

### Lookup Tables (cross-season reference)

```
lookup_divisions (id, name, abbreviation)
lookup_teams (id, name, short_name, division_id)
lookup_seasons (id, division_id, start_year, end_year, is_current)
lookup_positions (code, name, category)
lookup_play_types (code, name, category)
```

### Data Tables

```
players
├── id (bigint PK), name, jersey_number, primary_position
├── team_id, division_id, season_count, first_season, last_season
└── created_at, updated_at

games
├── id (text PK), game_date, season_id, division_id, status
├── home_team_id, away_team_id, home_score, away_score
├── home_team_name, away_team_name (denormalized)
├── winning_team_id, losing_team_id (denormalized)
├── home_team_wins, home_team_losses (denormalized, running record)
├── away_team_wins, away_team_losses (denormalized, running record)
├── location, attendance
└── created_at, updated_at

player_game_stats
├── id (uuid PK), game_id, player_id, team_id, season_id, division_id
├── player_name, team_name (denormalized)
├── jersey_number, position
├── goals, assists, points, shots, shots_on_goal
├── ground_balls, turnovers, caused_turnovers
├── faceoff_wins, faceoffs_taken
├── goalie_minutes, goals_allowed, saves, save_percentage
└── UNIQUE(game_id, player_id, position)

player_seasons
├── player_id, team_id, season_id
├── jersey_number, primary_position
└── UNIQUE(player_id, team_id, season_id)

team_seasons (team_id, season_id, team_name, conference)

game_plays
├── game_id, season_id, quarter, time_remaining
├── play_type, player_id, team_id, description
└── created_at
```

### Denormalized Columns

Added by `enrich_tables.py`, populated from lookup tables:

| Table | Columns |
|-------|---------|
| `player_game_stats` | `player_name`, `team_name`, `opponent_id` |
| `games` | `home_team_name`, `away_team_name`, `winning_team_id`, `losing_team_id`, `home_team_wins`, `home_team_losses`, `away_team_wins`, `away_team_losses` |
| `players` | `team_id`, `season_count`, `first_season`, `last_season` |
| `game_plays` | `season_id` |

### Aggregated Tables

Rebuilt from scratch by `enrich_tables.py` on every run.

```
player_season_stats
├── player_id, team_id, season_id, division_id
├── player_name, team_name, primary_position
├── games_played, goals, assists, points
├── shots, shots_on_goal, ground_balls
├── turnovers, caused_turnovers
├── faceoff_wins, faceoffs_taken
├── minutes_played, goalie_minutes, goals_allowed, saves
└── points_per_game, goals_per_game, shooting_pct, faceoff_pct, save_pct

team_season_stats
├── team_id, season_id, division_id, team_name
├── wins, losses, ties, games_played
├── goals_for, goals_against, goal_diff
├── total_shots, total_shots_on_goal, total_ground_balls
├── total_turnovers, total_caused_turnovers
├── total_faceoff_wins, total_faceoffs_taken, total_saves
└── win_pct, opp_win_pct, opp_opp_win_pct, shooting_pct, faceoff_pct, save_pct
```

### Indexes

| Index | Table | Columns |
|-------|-------|---------|
| `idx_pgs_season_team` | `player_game_stats` | `(season_id, team_id)` |
| `idx_pgs_season_player` | `player_game_stats` | `(season_id, player_id)` |
| `idx_pgs_opponent` | `player_game_stats` | `(opponent_id)` |
| `idx_games_season_status` | `games` | `(season_id, status)` |
| `idx_player_seasons_player_desc` | `player_seasons` | `(player_id, season_id DESC)` |

## Data Pipeline

### Fetching (browser-based)

stats.ncaa.org uses Akamai CDN which blocks HTTP clients. Fetching uses `agent-browser` to control a real browser via CDP. See `docs/browser-fetching.md`.

```
1. Discover game IDs  → get_game_ids_browser.py → data/{season}/division{n}/raw/game_ids.json
2. Fetch game data    → fetch_games_browser.py  → game_{id}_info.json, _player_stats.json, _plays.json
3. Fetch rosters      → fetch_rosters_browser.py → data/{season}/division{n}/raw/rosters.json
```

### Loading (database)

All loaders use psycopg2 COPY and are season-safe (DELETE scoped by `season_id`).

```
1. load_teams.py         → Extract teams from game info files → lookup_teams
2. load_games.py         → Load game metadata → games
3. load_players.py       → Extract players from stat files → players, player_seasons
4. load_player_stats.py  → Load stats with roster-based team assignment → player_game_stats
5. load_game_plays.py    → Load play-by-play → game_plays
6. enrich_tables.py      → Denormalize all tables (idempotent)
```

### Team Assignment

Player stats JSON files contain no team identifier. Assignment uses roster lookup:

```python
roster_map = load_roster_mapping(season_id, division)  # {playerID: teamID}
team_id = get_player_team(player_id, roster_map, home_team_id, away_team_id)
```

### Daily Sync

```bash
python scripts/sync_daily.py --season 2026
```

Pipeline: discover game IDs → fetch via browser → load to database → run QC.

### Season Setup

Each season requires a `season_division_id` from NCAA, discovered via browser and stored in `config.json`.

## Web App

Next.js 16 with TypeScript and App Router. No Prisma — uses Supabase JS client and postgres.js directly.

### DB Access (`web/src/lib/db.ts`)

- `getSupabase()` — `@supabase/supabase-js` client (structured queries)
- `getSql()` — `postgres` (postgres.js) for raw SQL
- `getCurrentSeason()` — queries `lookup_seasons` for `is_current = true`

### API Routes

| Route | Data Source | Notes |
|-------|-------------|-------|
| `/api/seasons` | `lookup_seasons` | All seasons |
| `/api/stats/top-scorers` | `player_game_stats` | Uses denormalized `player_name`, `team_name` |
| `/api/stats/recent-games` | `games` | Uses denormalized `home_team_name`, `away_team_name` |
| `/api/stats/team-standings` | `team_season_stats` | Uses denormalized `team_name`, `win_pct` |

### Environment Variables (`web/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `DIRECT_URL` | Direct Postgres connection string (postgres.js) |

## Configuration (`config.json`)

| Setting | Description |
|---------|-------------|
| `season_division_ids` | NCAA IDs per division/season (e.g., 2026 D1 = 18723) |
| `date_ranges` | Default scraping date range |
| `rate_limiting.base_delay` | Seconds between requests |
| `scraping.timeout_seconds` | Per-request timeout |
