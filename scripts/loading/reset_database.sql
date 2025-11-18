-- Step 1: Drop all existing tables
DROP TABLE IF EXISTS game_plays CASCADE;
DROP TABLE IF EXISTS player_game_stats CASCADE;
DROP TABLE IF EXISTS team_game_stats CASCADE;
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS teams CASCADE;

-- Drop deprecated tables if they exist
DROP TABLE IF EXISTS dep_game_plays CASCADE;
DROP TABLE IF EXISTS dep_player_game_stats CASCADE;
DROP TABLE IF EXISTS dep_team_game_stats CASCADE;
DROP TABLE IF EXISTS dep_games CASCADE;
DROP TABLE IF EXISTS dep_players CASCADE;
DROP TABLE IF EXISTS dep_teams CASCADE;

-- Step 2: Create fresh schema with games.id as TEXT PRIMARY KEY

-- Teams master table (using external team IDs)
CREATE TABLE teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Players master table (using external player IDs)
CREATE TABLE players (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    jersey_number TEXT,
    primary_position TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Games master table (using external game IDs as TEXT)
CREATE TABLE games (
    id TEXT PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team_id TEXT NOT NULL REFERENCES teams(id),
    away_team_id TEXT NOT NULL REFERENCES teams(id),
    home_score INTEGER,
    away_score INTEGER,
    location TEXT,
    attendance INTEGER,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Player game statistics
CREATE TABLE player_game_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id TEXT NOT NULL REFERENCES games(id),
    player_id BIGINT NOT NULL REFERENCES players(id),
    jersey_number TEXT,
    position TEXT,
    minutes_played TEXT,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    shots_on_goal INTEGER DEFAULT 0,
    ground_balls INTEGER DEFAULT 0,
    turnovers INTEGER DEFAULT 0,
    caused_turnovers INTEGER DEFAULT 0,
    faceoff_wins INTEGER DEFAULT 0,
    faceoffs_taken INTEGER DEFAULT 0,
    goalie_minutes TEXT,
    goals_allowed INTEGER DEFAULT 0,
    gaa DECIMAL(5,3),
    saves INTEGER DEFAULT 0,
    save_percentage DECIMAL(5,3),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(game_id, player_id)
);

-- Game plays (play-by-play data)
CREATE TABLE game_plays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id TEXT NOT NULL REFERENCES games(id),
    quarter TEXT NOT NULL,
    time_remaining TEXT NOT NULL,
    home_event TEXT,
    away_event TEXT,
    score TEXT,
    play_sequence INTEGER,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(game_id, play_sequence)
);

-- Step 3: Create indexes
CREATE INDEX idx_teams_name ON teams(name);
CREATE INDEX idx_players_name ON players(name);
CREATE INDEX idx_players_position ON players(primary_position);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);
CREATE INDEX idx_games_teams ON games(home_team_id, away_team_id);
CREATE INDEX idx_player_game_stats_game ON player_game_stats(game_id);
CREATE INDEX idx_player_game_stats_player ON player_game_stats(player_id);
CREATE INDEX idx_player_game_stats_position ON player_game_stats(position);
CREATE INDEX idx_game_plays_game ON game_plays(game_id);
CREATE INDEX idx_game_plays_quarter ON game_plays(quarter);
CREATE INDEX idx_game_plays_sequence ON game_plays(game_id, play_sequence);

-- Step 4: Create or replace update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Step 5: Create triggers
CREATE TRIGGER teams_updated_at_trigger
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER players_updated_at_trigger
    BEFORE UPDATE ON players
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER games_updated_at_trigger
    BEFORE UPDATE ON games
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER player_game_stats_updated_at_trigger
    BEFORE UPDATE ON player_game_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Step 6: Disable RLS for data loading
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE players DISABLE ROW LEVEL SECURITY;
ALTER TABLE games DISABLE ROW LEVEL SECURITY;
ALTER TABLE player_game_stats DISABLE ROW LEVEL SECURITY;
ALTER TABLE game_plays DISABLE ROW LEVEL SECURITY;
