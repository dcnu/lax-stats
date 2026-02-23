"""
Data integrity tests for the 2026 D1 lacrosse stats pipeline.

Tests are parametrized over all teams in team_seasons for the target season.
Run: pytest tests/test_data_integrity.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from utils.db import execute_query


SEASON = "2026"
DIVISION = 1


def get_active_teams() -> list[tuple[str, str]]:
	"""Return [(team_id, team_name)] for all teams in team_seasons for the season."""
	rows = execute_query(
		"SELECT team_id, team_name FROM team_seasons WHERE season_id = %s ORDER BY team_name",
		(SEASON,),
	)
	return [(r["team_id"], r["team_name"]) for r in rows] if rows else []


ACTIVE_TEAMS = get_active_teams()
TEAM_IDS = [t[0] for t in ACTIVE_TEAMS]
TEAM_NAMES = {t[0]: t[1] for t in ACTIVE_TEAMS}


def pytest_generate_tests(metafunc):
	"""Parametrize team-scoped tests with (team_id, team_name) tuples."""
	if "team_id" in metafunc.fixturenames:
		metafunc.parametrize(
			"team_id",
			TEAM_IDS,
			ids=[TEAM_NAMES[tid] for tid in TEAM_IDS],
		)


def _fail_summary(rows: list, header: str) -> str:
	"""Format a failure summary table for human readability."""
	lines = [header]
	for row in rows:
		lines.append("  " + "  |  ".join(f"{k}={v}" for k, v in dict(row).items()))
	return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Season-level tests (no team_id parametrization)
# ──────────────────────────────────────────────────────────────────────────────


def test_no_duplicate_games():
	"""Same matchup (home_team_id, away_team_id, game_date) must appear at most once."""
	rows = execute_query(
		"""
		SELECT home_team_id, away_team_id, game_date, COUNT(*) AS cnt
		FROM games
		WHERE season_id = %s
		GROUP BY home_team_id, away_team_id, game_date
		HAVING COUNT(*) > 1
		ORDER BY game_date, home_team_id
		""",
		(SEASON,),
	)
	assert not rows, _fail_summary(rows, f"Duplicate matchups in season {SEASON}:")


def test_active_teams_exist():
	"""team_seasons must be non-empty for the target season."""
	assert ACTIVE_TEAMS, f"No teams found in team_seasons for season {SEASON}"


# ──────────────────────────────────────────────────────────────────────────────
# Per-team tests
# ──────────────────────────────────────────────────────────────────────────────


def test_schedule_not_empty(team_id):
	"""Every active team must have at least 1 game scheduled or played."""
	rows = execute_query(
		"""
		SELECT COUNT(*) AS cnt FROM games
		WHERE season_id = %s
		AND (home_team_id = %s OR away_team_id = %s)
		""",
		(SEASON, team_id, team_id),
	)
	cnt = rows[0]["cnt"] if rows else 0
	assert cnt > 0, f"{TEAM_NAMES[team_id]}: no games found in season {SEASON}"


def test_team_season_stats_exists(team_id):
	"""Every active team must have a row in team_season_stats."""
	rows = execute_query(
		"SELECT 1 FROM team_season_stats WHERE team_id = %s AND season_id = %s",
		(team_id, SEASON),
	)
	assert rows, f"{TEAM_NAMES[team_id]}: missing row in team_season_stats"


def test_no_orphan_games(team_id):
	"""Every game's team_id must resolve to a team_seasons entry."""
	rows = execute_query(
		"""
		SELECT g.id, g.home_team_id, g.away_team_id
		FROM games g
		WHERE g.season_id = %s
		AND (g.home_team_id = %s OR g.away_team_id = %s)
		AND NOT EXISTS (
			SELECT 1 FROM team_seasons ts WHERE ts.team_id = g.home_team_id AND ts.season_id = g.season_id
		)
		""",
		(SEASON, team_id, team_id),
	)
	assert not rows, _fail_summary(rows, f"{TEAM_NAMES[team_id]}: games with orphan home_team_id:")


def _final_game_count(team_id: str) -> int:
	rows = execute_query(
		"""
		SELECT COUNT(*) AS cnt FROM games
		WHERE season_id = %s AND status = 'final'
		AND (home_team_id = %s OR away_team_id = %s)
		""",
		(SEASON, team_id, team_id),
	)
	return rows[0]["cnt"] if rows else 0


def _stat_row_count(team_id: str) -> int:
	rows = execute_query(
		"SELECT COUNT(*) AS cnt FROM player_game_stats WHERE team_id = %s AND season_id = %s",
		(team_id, SEASON),
	)
	return rows[0]["cnt"] if rows else 0


def test_final_games_have_stats(team_id):
	"""Every team with at least 1 final game must have player_game_stats rows."""
	final = _final_game_count(team_id)
	if final == 0:
		pytest.skip(f"{TEAM_NAMES[team_id]}: no final games yet")

	stat_rows = _stat_row_count(team_id)
	assert stat_rows > 0, (
		f"{TEAM_NAMES[team_id]}: {final} final game(s), 0 player_game_stats rows"
	)


def test_player_season_stats_populated(team_id):
	"""Teams with linked (non-NULL player_id) stats must have player_season_stats rows."""
	rows = execute_query(
		"""
		SELECT COUNT(*) AS cnt FROM player_game_stats
		WHERE team_id = %s AND season_id = %s AND player_id IS NOT NULL
		""",
		(team_id, SEASON),
	)
	linked = rows[0]["cnt"] if rows else 0
	if linked == 0:
		pytest.skip(f"{TEAM_NAMES[team_id]}: no linked player_game_stats rows (all NULL player_id)")

	pss_rows = execute_query(
		"SELECT COUNT(*) AS cnt FROM player_season_stats WHERE team_id = %s AND season_id = %s",
		(team_id, SEASON),
	)
	cnt = pss_rows[0]["cnt"] if pss_rows else 0
	assert cnt > 0, f"{TEAM_NAMES[team_id]}: has {linked} linked pgs rows but 0 player_season_stats rows"


def test_player_seasons_populated(team_id):
	"""Teams with player_game_stats (and known player_ids) must have player_seasons rows."""
	rows = execute_query(
		"""
		SELECT COUNT(*) AS cnt FROM player_game_stats
		WHERE team_id = %s AND season_id = %s AND player_id IS NOT NULL
		""",
		(team_id, SEASON),
	)
	linked = rows[0]["cnt"] if rows else 0
	if linked == 0:
		pytest.skip(f"{TEAM_NAMES[team_id]}: no linked player_game_stats rows")

	ps_rows = execute_query(
		"SELECT COUNT(*) AS cnt FROM player_seasons WHERE team_id = %s AND season_id = %s",
		(team_id, SEASON),
	)
	cnt = ps_rows[0]["cnt"] if ps_rows else 0
	assert cnt > 0, (
		f"{TEAM_NAMES[team_id]}: {linked} linked pgs rows but 0 player_seasons rows"
	)


def test_rankings_populated():
	"""team_season_rankings must have at least one entry for the current season."""
	rows = execute_query(
		"SELECT COUNT(*) AS cnt FROM team_season_rankings WHERE season_id = %s",
		(SEASON,),
	)
	cnt = rows[0]["cnt"] if rows else 0
	# Rankings may not exist early in the season; warn rather than hard-fail
	if cnt == 0:
		pytest.skip(f"No rankings entries for season {SEASON} (expected early in season)")
