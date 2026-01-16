"""
Database connection module for local PostgreSQL.

Provides connection management using psycopg2.
"""

import json
import sys
from pathlib import Path
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def load_config():
	"""Load database configuration from config.json."""
	config_path = Path("config.json")
	if not config_path.exists():
		print("Error: config.json not found.", file=sys.stderr)
		sys.exit(1)

	with open(config_path) as f:
		config = json.load(f)

	if "database" not in config:
		print("Error: 'database' section not found in config.json", file=sys.stderr)
		sys.exit(1)

	return config["database"]


def get_connection():
	"""Create a new database connection."""
	db_config = load_config()
	return psycopg2.connect(
		host=db_config.get("host", "localhost"),
		port=db_config.get("port", 5432),
		database=db_config["database"],
		user=db_config.get("user", ""),
		password=db_config.get("password", ""),
		cursor_factory=RealDictCursor,
	)


@contextmanager
def get_cursor():
	"""Context manager for database cursor with automatic commit/rollback."""
	conn = get_connection()
	try:
		cursor = conn.cursor()
		yield cursor
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		cursor.close()
		conn.close()


def execute_query(query: str, params: tuple = None):
	"""Execute a query and return results."""
	with get_cursor() as cursor:
		cursor.execute(query, params)
		if cursor.description:
			return cursor.fetchall()
		return None


def execute_many(query: str, params_list: list):
	"""Execute a query with multiple parameter sets."""
	with get_cursor() as cursor:
		cursor.executemany(query, params_list)
		return cursor.rowcount


def upsert_team(team_id: str, name: str, short_name: str = None, division_id: int = 1):
	"""Insert or update a team."""
	query = """
		INSERT INTO teams (id, name, short_name, division_id)
		VALUES (%s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			short_name = EXCLUDED.short_name,
			updated_at = NOW()
		RETURNING id, name
	"""
	with get_cursor() as cursor:
		cursor.execute(query, (team_id, name, short_name, division_id))
		return cursor.fetchone()


def upsert_player(player_id: int, name: str, division_id: int = 1):
	"""Insert or update a player."""
	query = """
		INSERT INTO players (id, name, division_id)
		VALUES (%s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			updated_at = NOW()
		RETURNING id, name
	"""
	with get_cursor() as cursor:
		cursor.execute(query, (player_id, name, division_id))
		return cursor.fetchone()


def upsert_season(
	season_id: str,
	division_id: int,
	start_year: int,
	end_year: int,
	start_date=None,
	end_date=None,
	is_current: bool = False,
):
	"""Insert or update a season."""
	query = """
		INSERT INTO seasons (id, division_id, start_year, end_year, start_date, end_date, is_current)
		VALUES (%s, %s, %s, %s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			division_id = EXCLUDED.division_id,
			start_year = EXCLUDED.start_year,
			end_year = EXCLUDED.end_year,
			start_date = EXCLUDED.start_date,
			end_date = EXCLUDED.end_date,
			is_current = EXCLUDED.is_current,
			updated_at = NOW()
		RETURNING id
	"""
	with get_cursor() as cursor:
		cursor.execute(
			query,
			(season_id, division_id, start_year, end_year, start_date, end_date, is_current),
		)
		return cursor.fetchone()


def upsert_game(
	game_id: str,
	season_id: str,
	division_id: int,
	game_date,
	home_team_id: str,
	away_team_id: str,
	home_score: int = None,
	away_score: int = None,
	location: str = None,
	attendance: int = None,
	status: str = "final",
):
	"""Insert or update a game."""
	query = """
		INSERT INTO games (
			id, season_id, division_id, game_date, home_team_id, away_team_id,
			home_score, away_score, location, attendance, status
		)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			home_score = EXCLUDED.home_score,
			away_score = EXCLUDED.away_score,
			location = EXCLUDED.location,
			attendance = EXCLUDED.attendance,
			status = EXCLUDED.status,
			updated_at = NOW()
		RETURNING id
	"""
	with get_cursor() as cursor:
		cursor.execute(
			query,
			(
				game_id,
				season_id,
				division_id,
				game_date,
				home_team_id,
				away_team_id,
				home_score,
				away_score,
				location,
				attendance,
				status,
			),
		)
		return cursor.fetchone()


def parse_time_to_seconds(time_str: str) -> int:
	"""Convert MM:SS time format to total seconds."""
	if not time_str or time_str == "0":
		return 0
	try:
		parts = time_str.split(":")
		if len(parts) == 2:
			return int(parts[0]) * 60 + int(parts[1])
		return int(time_str)
	except (ValueError, AttributeError):
		return 0


def format_seconds_to_time(seconds: int) -> str:
	"""Convert seconds to MM:SS format."""
	if seconds is None:
		return "0:00"
	minutes = seconds // 60
	secs = seconds % 60
	return f"{minutes}:{secs:02d}"
