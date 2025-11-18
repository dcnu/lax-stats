-- Verification queries for data migration

-- 1. Check record counts
SELECT 'teams' as table_name, COUNT(*) as count FROM teams
UNION ALL SELECT 'players', COUNT(*) FROM players
UNION ALL SELECT 'games', COUNT(*) FROM games
UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats
UNION ALL SELECT 'game_plays', COUNT(*) FROM game_plays
ORDER BY table_name;

-- 2. Verify games.id is TEXT (not UUID)
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'games' AND column_name = 'id';

-- 3. Sample games data
SELECT id, game_date, home_score, away_score
FROM games
ORDER BY game_date
LIMIT 10;

-- 4. Test join between games and teams
SELECT
    g.id,
    g.game_date,
    t1.name as home_team,
    g.home_score,
    t2.name as away_team,
    g.away_score
FROM games g
JOIN teams t1 ON g.home_team_id = t1.id
JOIN teams t2 ON g.away_team_id = t2.id
ORDER BY g.game_date DESC
LIMIT 10;

-- 5. Top scorers
SELECT
    p.name,
    SUM(pgs.goals) as total_goals,
    SUM(pgs.assists) as total_assists,
    COUNT(DISTINCT pgs.game_id) as games_played
FROM players p
JOIN player_game_stats pgs ON p.id = pgs.player_id
GROUP BY p.id, p.name
HAVING SUM(pgs.goals) > 0
ORDER BY total_goals DESC
LIMIT 10;

-- 6. Team stats
SELECT
    t.name,
    COUNT(DISTINCT g.id) as games_played,
    SUM(CASE WHEN g.home_team_id = t.id THEN g.home_score ELSE g.away_score END) as total_goals_for,
    SUM(CASE WHEN g.home_team_id = t.id THEN g.away_score ELSE g.home_score END) as total_goals_against
FROM teams t
LEFT JOIN games g ON (t.id = g.home_team_id OR t.id = g.away_team_id)
GROUP BY t.id, t.name
ORDER BY games_played DESC
LIMIT 10;

-- 7. Play-by-play sample
SELECT
    game_id,
    quarter,
    time_remaining,
    COALESCE(home_event, away_event) as event,
    score
FROM game_plays
WHERE game_id = (SELECT id FROM games ORDER BY game_date DESC LIMIT 1)
ORDER BY play_sequence
LIMIT 20;
