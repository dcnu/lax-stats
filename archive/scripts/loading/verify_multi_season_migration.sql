-- Verification: Multi-Season Migration
-- Date: 2025-01-31
-- Purpose: Verify data integrity after multi-season migration

\echo '=========================================='
\echo 'Multi-Season Migration Verification'
\echo '=========================================='
\echo ''

-- ============================================================================
-- CHECK 1: Seasons table populated
-- ============================================================================

\echo 'CHECK 1: Seasons Table'
\echo '---'
SELECT
	COUNT(*) as total_seasons,
	MIN(start_year) as earliest_season,
	MAX(end_year) as latest_season,
	SUM(CASE WHEN is_current THEN 1 ELSE 0 END) as current_seasons
FROM seasons;
\echo ''

-- ============================================================================
-- CHECK 2: All games have season_id
-- ============================================================================

\echo 'CHECK 2: Games with Season IDs'
\echo '---'
SELECT
	COUNT(*) as total_games,
	COUNT(season_id) as games_with_season,
	COUNT(*) - COUNT(season_id) as games_missing_season
FROM games;
\echo ''

-- Show games per season
\echo 'Games per season:'
SELECT
	season_id,
	COUNT(*) as game_count,
	MIN(game_date) as first_game,
	MAX(game_date) as last_game
FROM games
WHERE season_id IS NOT NULL
GROUP BY season_id
ORDER BY season_id DESC;
\echo ''

-- ============================================================================
-- CHECK 3: All player_game_stats have season_id and team_id
-- ============================================================================

\echo 'CHECK 3: Player Game Stats with Season/Team IDs'
\echo '---'
SELECT
	COUNT(*) as total_stats,
	COUNT(season_id) as stats_with_season,
	COUNT(team_id) as stats_with_team,
	COUNT(*) - COUNT(season_id) as stats_missing_season,
	COUNT(*) - COUNT(team_id) as stats_missing_team
FROM player_game_stats;
\echo ''

-- ============================================================================
-- CHECK 4: Team seasons populated
-- ============================================================================

\echo 'CHECK 4: Team Seasons'
\echo '---'
SELECT
	COUNT(DISTINCT team_id) as unique_teams,
	COUNT(DISTINCT season_id) as unique_seasons,
	COUNT(*) as total_team_seasons
FROM team_seasons;
\echo ''

-- Show team seasons breakdown
\echo 'Team seasons per season:'
SELECT
	season_id,
	COUNT(*) as team_count
FROM team_seasons
GROUP BY season_id
ORDER BY season_id DESC;
\echo ''

-- ============================================================================
-- CHECK 5: Player seasons populated
-- ============================================================================

\echo 'CHECK 5: Player Seasons'
\echo '---'
SELECT
	COUNT(DISTINCT player_id) as unique_players,
	COUNT(DISTINCT season_id) as unique_seasons,
	COUNT(*) as total_player_seasons,
	COUNT(jersey_number) as player_seasons_with_jersey,
	COUNT(primary_position) as player_seasons_with_position
FROM player_seasons;
\echo ''

-- Show player seasons breakdown
\echo 'Player seasons per season:'
SELECT
	season_id,
	COUNT(DISTINCT player_id) as player_count,
	COUNT(*) as player_season_records
FROM player_seasons
GROUP BY season_id
ORDER BY season_id DESC;
\echo ''

-- ============================================================================
-- CHECK 6: Uniqueness constraint working
-- ============================================================================

\echo 'CHECK 6: Player Game Stats Uniqueness'
\echo '---'
-- Should be 0 (no duplicates)
SELECT
	COUNT(*) as duplicate_count
FROM (
	SELECT game_id, player_id, position, COUNT(*) as cnt
	FROM player_game_stats
	GROUP BY game_id, player_id, position
	HAVING COUNT(*) > 1
) duplicates;
\echo ''

-- ============================================================================
-- CHECK 7: Players with multiple positions same game (expected edge cases)
-- ============================================================================

\echo 'CHECK 7: Players with Multiple Positions Same Game'
\echo '---'
SELECT
	COUNT(DISTINCT player_id) as players_multi_position,
	COUNT(*) as total_occurrences
FROM (
	SELECT game_id, player_id, COUNT(DISTINCT position) as position_count
	FROM player_game_stats
	GROUP BY game_id, player_id
	HAVING COUNT(DISTINCT position) > 1
) multi_pos;
\echo ''

-- Show examples
\echo 'Examples (first 5):'
SELECT
	pgs.game_id,
	pgs.player_id,
	p.name,
	STRING_AGG(DISTINCT pgs.position, ', ') as positions,
	g.game_date
FROM player_game_stats pgs
JOIN players p ON pgs.player_id = p.id
JOIN games g ON pgs.game_id = g.id
GROUP BY pgs.game_id, pgs.player_id, p.name, g.game_date
HAVING COUNT(DISTINCT pgs.position) > 1
ORDER BY g.game_date DESC
LIMIT 5;
\echo ''

-- ============================================================================
-- CHECK 8: Players with jersey number changes across seasons
-- ============================================================================

\echo 'CHECK 8: Players with Jersey Number Changes'
\echo '---'
SELECT
	COUNT(*) as players_with_jersey_changes
FROM (
	SELECT player_id, COUNT(DISTINCT jersey_number) as jersey_count
	FROM player_seasons
	GROUP BY player_id
	HAVING COUNT(DISTINCT jersey_number) > 1
) jersey_changes;
\echo ''

-- Show examples
\echo 'Examples (first 10):'
SELECT
	p.id,
	p.name,
	STRING_AGG(
		CONCAT(ps.season_id, ': #', ps.jersey_number, ' (', t.short_name, ')'),
		', '
		ORDER BY ps.season_id
	) as jersey_history
FROM players p
JOIN player_seasons ps ON p.id = ps.player_id
JOIN teams t ON ps.team_id = t.id
GROUP BY p.id, p.name
HAVING COUNT(DISTINCT ps.jersey_number) > 1
ORDER BY p.name
LIMIT 10;
\echo ''

-- ============================================================================
-- CHECK 9: Players with position changes across seasons
-- ============================================================================

\echo 'CHECK 9: Players with Position Changes'
\echo '---'
SELECT
	COUNT(*) as players_with_position_changes
FROM (
	SELECT player_id, COUNT(DISTINCT primary_position) as position_count
	FROM player_seasons
	WHERE primary_position IS NOT NULL
	GROUP BY player_id
	HAVING COUNT(DISTINCT primary_position) > 1
) position_changes;
\echo ''

-- Show examples
\echo 'Examples (first 10):'
SELECT
	p.id,
	p.name,
	STRING_AGG(
		CONCAT(ps.season_id, ': ', ps.primary_position),
		', '
		ORDER BY ps.season_id
	) as position_history
FROM players p
JOIN player_seasons ps ON p.id = ps.player_id
WHERE ps.primary_position IS NOT NULL
GROUP BY p.id, p.name
HAVING COUNT(DISTINCT ps.primary_position) > 1
ORDER BY p.name
LIMIT 10;
\echo ''

-- ============================================================================
-- CHECK 10: Players who played for multiple teams in same season
-- ============================================================================

\echo 'CHECK 10: Players with Multiple Teams Same Season (Transfers)'
\echo '---'
SELECT
	season_id,
	COUNT(*) as transfer_count
FROM (
	SELECT player_id, season_id, COUNT(DISTINCT team_id) as team_count
	FROM player_seasons
	GROUP BY player_id, season_id
	HAVING COUNT(DISTINCT team_id) > 1
) transfers
GROUP BY season_id
ORDER BY season_id DESC;
\echo ''

-- Show examples
\echo 'Examples (first 10):'
SELECT
	p.id,
	p.name,
	ps.season_id,
	STRING_AGG(t.short_name, ' -> ' ORDER BY t.short_name) as teams
FROM players p
JOIN player_seasons ps ON p.id = ps.player_id
JOIN teams t ON ps.team_id = t.id
GROUP BY p.id, p.name, ps.season_id
HAVING COUNT(DISTINCT ps.team_id) > 1
ORDER BY ps.season_id DESC, p.name
LIMIT 10;
\echo ''

-- ============================================================================
-- CHECK 11: Materialized view populated
-- ============================================================================

\echo 'CHECK 11: Materialized View - Player Season Stats'
\echo '---'
SELECT
	COUNT(*) as total_records,
	COUNT(DISTINCT player_id) as unique_players,
	COUNT(DISTINCT season_id) as unique_seasons
FROM player_season_stats;
\echo ''

-- Show sample data
\echo 'Sample (top 5 scorers in most recent season):'
SELECT
	season_id,
	player_name,
	jersey_number,
	primary_position,
	games_played,
	total_goals,
	total_assists,
	total_points
FROM player_season_stats
WHERE season_id = (SELECT id FROM seasons ORDER BY start_year DESC LIMIT 1)
ORDER BY total_points DESC NULLS LAST
LIMIT 5;
\echo ''

-- ============================================================================
-- CHECK 12: Data consistency between tables
-- ============================================================================

\echo 'CHECK 12: Data Consistency'
\echo '---'

-- Orphaned player_game_stats (should be 0)
\echo 'Orphaned player_game_stats records (should be 0):'
SELECT COUNT(*) as orphaned_stats
FROM player_game_stats pgs
WHERE NOT EXISTS (
	SELECT 1 FROM player_seasons ps
	WHERE ps.player_id = pgs.player_id
		AND ps.team_id = pgs.team_id
		AND ps.season_id = pgs.season_id
);
\echo ''

-- Orphaned player_seasons (should be 0)
\echo 'Orphaned player_seasons records (should be 0):'
SELECT COUNT(*) as orphaned_player_seasons
FROM player_seasons ps
WHERE NOT EXISTS (
	SELECT 1 FROM player_game_stats pgs
	WHERE pgs.player_id = ps.player_id
		AND pgs.team_id = ps.team_id
		AND pgs.season_id = ps.season_id
);
\echo ''

-- ============================================================================
-- VERIFICATION COMPLETE
-- ============================================================================

\echo '=========================================='
\echo 'Verification Complete'
\echo '=========================================='
\echo ''
\echo 'Review the output above for any anomalies.'
\echo 'Expected results:'
\echo '  - All games have season_id'
\echo '  - All player_game_stats have season_id and team_id'
\echo '  - No duplicate records in player_game_stats'
\echo '  - Player seasons and team seasons are populated'
\echo '  - Materialized view has data'
\echo '  - No orphaned records'
