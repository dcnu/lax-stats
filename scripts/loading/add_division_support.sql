-- Database Schema Migration: Add Multi-Division Support (v4 - With Deduplication)
-- Handles existing duplicate records before adding constraints
-- Back up your database before running!

-- ============================================================================
-- Step 1: Create divisions reference table
-- ============================================================================

CREATE TABLE IF NOT EXISTS divisions (
    id INTEGER PRIMARY KEY CHECK (id IN (1, 2, 3)),
    name TEXT NOT NULL UNIQUE,
    abbreviation TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO divisions (id, name, abbreviation) VALUES
    (1, 'Division I', 'D1'),
    (2, 'Division II', 'D2'),
    (3, 'Division III', 'D3')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Step 2: Add division_id to seasons table
-- ============================================================================

ALTER TABLE seasons ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'seasons_division_id_fkey'
    ) THEN
        ALTER TABLE seasons ADD CONSTRAINT seasons_division_id_fkey
            FOREIGN KEY (division_id) REFERENCES divisions(id);
    END IF;
END $$;

DROP INDEX IF EXISTS seasons_id_division_key;
CREATE UNIQUE INDEX IF NOT EXISTS seasons_id_division_key ON seasons(id, division_id);
CREATE INDEX IF NOT EXISTS idx_seasons_division ON seasons(division_id);

-- ============================================================================
-- Step 3: Add division_id to teams table
-- ============================================================================

ALTER TABLE teams ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'teams_division_id_fkey'
    ) THEN
        ALTER TABLE teams ADD CONSTRAINT teams_division_id_fkey
            FOREIGN KEY (division_id) REFERENCES divisions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_teams_division ON teams(division_id);

-- ============================================================================
-- Step 4: Add division_id to players table
-- ============================================================================

ALTER TABLE players ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'players_division_id_fkey'
    ) THEN
        ALTER TABLE players ADD CONSTRAINT players_division_id_fkey
            FOREIGN KEY (division_id) REFERENCES divisions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_players_division ON players(division_id);

-- ============================================================================
-- Step 5: Add division_id and season_id to games table
-- ============================================================================

ALTER TABLE games ADD COLUMN IF NOT EXISTS season_id TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'games_division_id_fkey'
    ) THEN
        ALTER TABLE games ADD CONSTRAINT games_division_id_fkey
            FOREIGN KEY (division_id) REFERENCES divisions(id);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'games' AND column_name = 'season_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'games_season_id_fkey'
    ) THEN
        ALTER TABLE games ADD CONSTRAINT games_season_id_fkey
            FOREIGN KEY (season_id) REFERENCES seasons(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_games_division ON games(division_id);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season_id);
CREATE INDEX IF NOT EXISTS idx_games_season_division ON games(season_id, division_id);

-- ============================================================================
-- Step 6: Add division_id to player_game_stats table
-- ============================================================================

ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS season_id TEXT;
ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS team_id TEXT;
ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'player_game_stats_division_id_fkey'
    ) THEN
        ALTER TABLE player_game_stats ADD CONSTRAINT player_game_stats_division_id_fkey
            FOREIGN KEY (division_id) REFERENCES divisions(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'player_game_stats_team_id_fkey'
    ) THEN
        ALTER TABLE player_game_stats ADD CONSTRAINT player_game_stats_team_id_fkey
            FOREIGN KEY (team_id) REFERENCES teams(id);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'player_game_stats' AND column_name = 'season_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'player_game_stats_season_id_fkey'
    ) THEN
        ALTER TABLE player_game_stats ADD CONSTRAINT player_game_stats_season_id_fkey
            FOREIGN KEY (season_id) REFERENCES seasons(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_player_game_stats_division ON player_game_stats(division_id);
CREATE INDEX IF NOT EXISTS idx_player_game_stats_season ON player_game_stats(season_id);

-- ============================================================================
-- Step 7: Add division_id to game_plays table (if it exists)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'game_plays'
    ) THEN
        ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS division_id INTEGER NOT NULL DEFAULT 1;

        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'game_plays_division_id_fkey'
        ) THEN
            ALTER TABLE game_plays ADD CONSTRAINT game_plays_division_id_fkey
                FOREIGN KEY (division_id) REFERENCES divisions(id);
        END IF;

        CREATE INDEX IF NOT EXISTS idx_game_plays_division ON game_plays(division_id);
    END IF;
END $$;

-- ============================================================================
-- Step 8: Handle team_seasons table with deduplication
-- ============================================================================

CREATE TABLE IF NOT EXISTS team_seasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id TEXT NOT NULL REFERENCES teams(id),
    season_id TEXT NOT NULL REFERENCES seasons(id),
    division_id INTEGER NOT NULL DEFAULT 1 REFERENCES divisions(id),
    team_name TEXT,
    conference TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add division_id if it doesn't exist
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'team_seasons'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_seasons' AND column_name = 'division_id'
    ) THEN
        ALTER TABLE team_seasons ADD COLUMN division_id INTEGER NOT NULL DEFAULT 1 REFERENCES divisions(id);
    END IF;
END $$;

-- Remove duplicates from team_seasons before adding constraint
-- Keep the most recently updated record for each (team_id, season_id, division_id)
DELETE FROM team_seasons
WHERE id NOT IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY team_id, season_id, division_id
                   ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
               ) as rn
        FROM team_seasons
    ) t
    WHERE t.rn = 1
);

-- Now add unique constraint
ALTER TABLE team_seasons DROP CONSTRAINT IF EXISTS team_seasons_team_season_key;
ALTER TABLE team_seasons DROP CONSTRAINT IF EXISTS team_seasons_team_season_division_key;
DROP INDEX IF EXISTS team_seasons_team_season_division_key;
CREATE UNIQUE INDEX IF NOT EXISTS team_seasons_team_season_division_key
    ON team_seasons(team_id, season_id, division_id);

CREATE INDEX IF NOT EXISTS idx_team_seasons_division ON team_seasons(division_id);

-- ============================================================================
-- Step 9: Handle player_seasons table with deduplication
-- ============================================================================

CREATE TABLE IF NOT EXISTS player_seasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id BIGINT NOT NULL REFERENCES players(id),
    team_id TEXT NOT NULL REFERENCES teams(id),
    season_id TEXT NOT NULL REFERENCES seasons(id),
    division_id INTEGER NOT NULL DEFAULT 1 REFERENCES divisions(id),
    jersey_number TEXT,
    primary_position TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add division_id if it doesn't exist
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'player_seasons'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'player_seasons' AND column_name = 'division_id'
    ) THEN
        ALTER TABLE player_seasons ADD COLUMN division_id INTEGER NOT NULL DEFAULT 1 REFERENCES divisions(id);
    END IF;
END $$;

-- Remove duplicates from player_seasons before adding constraint
-- Keep the most recently updated record for each (player_id, season_id, division_id)
DELETE FROM player_seasons
WHERE id NOT IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY player_id, season_id, division_id
                   ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
               ) as rn
        FROM player_seasons
    ) t
    WHERE t.rn = 1
);

-- Now add unique constraint
ALTER TABLE player_seasons DROP CONSTRAINT IF EXISTS player_seasons_player_season_key;
ALTER TABLE player_seasons DROP CONSTRAINT IF EXISTS player_seasons_player_season_division_key;
DROP INDEX IF EXISTS player_seasons_player_season_division_key;
CREATE UNIQUE INDEX IF NOT EXISTS player_seasons_player_season_division_key
    ON player_seasons(player_id, season_id, division_id);

CREATE INDEX IF NOT EXISTS idx_player_seasons_division ON player_seasons(division_id);

-- ============================================================================
-- Step 10: Recreate materialized view with division support
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS player_season_stats_view;

CREATE MATERIALIZED VIEW player_season_stats_view AS
SELECT
    ps.player_id,
    ps.season_id,
    ps.division_id,
    ps.season_id AS season_year,
    d.abbreviation AS division,
    d.name AS division_name,
    ps.team_id,
    ps.jersey_number,
    ps.primary_position AS position,
    p.name AS player_name,
    COUNT(DISTINCT pgs.game_id) AS games_played,
    COALESCE(SUM(pgs.goals), 0) AS total_goals,
    COALESCE(SUM(pgs.assists), 0) AS total_assists,
    COALESCE(SUM(pgs.points), 0) AS total_points,
    COALESCE(SUM(pgs.shots), 0) AS total_shots,
    COALESCE(SUM(pgs.shots_on_goal), 0) AS total_sog,
    COALESCE(SUM(pgs.ground_balls), 0) AS total_gb,
    COALESCE(SUM(pgs.turnovers), 0) AS total_turnovers,
    COALESCE(SUM(pgs.caused_turnovers), 0) AS total_ct,
    COALESCE(SUM(pgs.faceoff_wins), 0) AS total_fow,
    COALESCE(SUM(pgs.faceoffs_taken), 0) - COALESCE(SUM(pgs.faceoff_wins), 0) AS total_fol,
    0 AS total_pen,
    0 AS total_pen_min,
    COALESCE(SUM(pgs.saves), 0) AS total_saves,
    COALESCE(SUM(pgs.goals_allowed), 0) AS total_goals_allowed,
    0 AS total_minutes_played,
    CASE WHEN COUNT(DISTINCT pgs.game_id) > 0
        THEN ROUND(COALESCE(SUM(pgs.goals), 0)::NUMERIC / COUNT(DISTINCT pgs.game_id), 2)
        ELSE 0
    END AS avg_goals_per_game,
    CASE WHEN COUNT(DISTINCT pgs.game_id) > 0
        THEN ROUND(COALESCE(SUM(pgs.assists), 0)::NUMERIC / COUNT(DISTINCT pgs.game_id), 2)
        ELSE 0
    END AS avg_assists_per_game,
    CASE WHEN COUNT(DISTINCT pgs.game_id) > 0
        THEN ROUND(COALESCE(SUM(pgs.points), 0)::NUMERIC / COUNT(DISTINCT pgs.game_id), 2)
        ELSE 0
    END AS avg_points_per_game,
    CASE WHEN COALESCE(SUM(pgs.shots), 0) > 0
        THEN ROUND((COALESCE(SUM(pgs.goals), 0)::NUMERIC / SUM(pgs.shots)) * 100, 2)
        ELSE 0
    END AS shot_percentage,
    CASE WHEN COALESCE(SUM(pgs.faceoffs_taken), 0) > 0
        THEN ROUND((COALESCE(SUM(pgs.faceoff_wins), 0)::NUMERIC / SUM(pgs.faceoffs_taken)) * 100, 2)
        ELSE 0
    END AS faceoff_percentage,
    CASE WHEN (COALESCE(SUM(pgs.saves), 0) + COALESCE(SUM(pgs.goals_allowed), 0)) > 0
        THEN ROUND((COALESCE(SUM(pgs.saves), 0)::NUMERIC / (SUM(pgs.saves) + SUM(pgs.goals_allowed))) * 100, 2)
        ELSE 0
    END AS save_percentage
FROM player_seasons ps
JOIN divisions d ON ps.division_id = d.id
JOIN players p ON ps.player_id = p.id
LEFT JOIN player_game_stats pgs ON ps.player_id = pgs.player_id
    AND ps.season_id = pgs.season_id
    AND ps.division_id = pgs.division_id
GROUP BY
    ps.player_id, ps.season_id, ps.division_id, d.abbreviation,
    d.name, ps.team_id, ps.jersey_number, ps.primary_position, p.name;

CREATE INDEX IF NOT EXISTS idx_player_season_stats_player ON player_season_stats_view(player_id);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_season ON player_season_stats_view(season_id);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_division ON player_season_stats_view(division_id);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_team ON player_season_stats_view(team_id);

-- ============================================================================
-- Verification
-- ============================================================================

SELECT 'Migration complete!' AS status;
SELECT '' AS spacer;
SELECT 'Divisions created:' AS info;
SELECT id, name, abbreviation FROM divisions ORDER BY id;

SELECT '' AS spacer;
SELECT 'Records by division:' AS info;
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
UNION ALL
SELECT 'player_game_stats', division_id, COUNT(*) FROM player_game_stats GROUP BY division_id
UNION ALL
SELECT 'team_seasons', division_id, COUNT(*) FROM team_seasons GROUP BY division_id
UNION ALL
SELECT 'player_seasons', division_id, COUNT(*) FROM player_seasons GROUP BY division_id
ORDER BY table_name, division_id;

SELECT '' AS spacer;
SELECT 'All existing data has been assigned to Division I (division_id = 1)' AS note;
