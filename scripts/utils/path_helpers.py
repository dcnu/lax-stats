#!/usr/bin/env python3
"""
Path helper utilities for season-based directory structure.

Provides consistent path resolution for data organized by season and division:
data/{season_id}/division{division}/games/ - game data files
data/{season_id}/division{division}/raw/ - raw scraping outputs

For backward compatibility, division defaults to 1 (Division I).
"""

from pathlib import Path
from datetime import datetime


def get_season_from_date(date_str, date_format="%m/%d/%Y"):
	"""
	Extract season ID from date string.

	Args:
		date_str: Date string to parse
		date_format: Format of date string (default: MM/DD/YYYY)

	Returns:
		Season ID as string (year)
	"""
	try:
		date_obj = datetime.strptime(date_str, date_format)
		return str(date_obj.year)
	except Exception as e:
		raise ValueError(f"Could not extract season from date '{date_str}': {e}")


def get_season_games_dir(season_id, division=1, base_dir="data"):
	"""
	Get path to games directory for a season and division.

	Args:
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3), defaults to 1
		base_dir: Base data directory

	Returns:
		Path object for season's games directory
	"""
	if division not in [1, 2, 3]:
		raise ValueError(f"Division must be 1, 2, or 3. Got: {division}")
	path = Path(base_dir) / season_id / f"division{division}" / "games"
	path.mkdir(parents=True, exist_ok=True)
	return path


def get_season_raw_dir(season_id, division=1, base_dir="data"):
	"""
	Get path to raw directory for a season and division.

	Args:
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3), defaults to 1
		base_dir: Base data directory

	Returns:
		Path object for season's raw directory
	"""
	if division not in [1, 2, 3]:
		raise ValueError(f"Division must be 1, 2, or 3. Got: {division}")
	path = Path(base_dir) / season_id / f"division{division}" / "raw"
	path.mkdir(parents=True, exist_ok=True)
	return path


def get_season_ncaa_dir(season_id, division=1, base_dir="data"):
	"""
	Get path to ncaa.com pipeline directory for a season and division.

	Args:
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3), defaults to 1
		base_dir: Base data directory

	Returns:
		Path object for season's ncaa directory
	"""
	if division not in [1, 2, 3]:
		raise ValueError(f"Division must be 1, 2, or 3. Got: {division}")
	path = Path(base_dir) / season_id / f"division{division}" / "ncaa"
	path.mkdir(parents=True, exist_ok=True)
	return path


def get_game_file_path(game_id, file_type, season_id, division=1, base_dir="data"):
	"""
	Get path to a game data file.

	Args:
		game_id: Game ID
		file_type: One of 'info', 'player_stats', 'plays'
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3), defaults to 1
		base_dir: Base data directory

	Returns:
		Path object for game file
	"""
	games_dir = get_season_games_dir(season_id, division, base_dir)
	return games_dir / f"game_{game_id}_{file_type}.json"


def get_raw_file_path(filename, season_id, division=1, base_dir="data"):
	"""
	Get path to a raw data file.

	Args:
		filename: Raw file name (e.g., 'game_ids.json')
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3), defaults to 1
		base_dir: Base data directory

	Returns:
		Path object for raw file
	"""
	raw_dir = get_season_raw_dir(season_id, division, base_dir)
	return raw_dir / filename


def get_all_season_dirs(base_dir="data"):
	"""
	Get all season directories.

	Args:
		base_dir: Base data directory

	Returns:
		List of (season_id, path) tuples
	"""
	base_path = Path(base_dir)
	if not base_path.exists():
		return []

	seasons = []
	for item in base_path.iterdir():
		if item.is_dir() and item.name.isdigit():
			seasons.append((item.name, item))

	return sorted(seasons, key=lambda x: x[0])


def get_all_divisions_for_season(season_id, base_dir="data"):
	"""
	Get all division directories for a given season.

	Args:
		season_id: Season ID (year as string)
		base_dir: Base data directory

	Returns:
		List of division numbers (1, 2, 3) that exist for this season
	"""
	season_path = Path(base_dir) / season_id
	if not season_path.exists():
		return []

	divisions = []
	for item in season_path.iterdir():
		if item.is_dir() and item.name.startswith("division"):
			try:
				div_num = int(item.name.replace("division", ""))
				if div_num in [1, 2, 3]:
					divisions.append(div_num)
			except ValueError:
				continue

	return sorted(divisions)


def get_all_game_files(season_id=None, division=None, base_dir="data"):
	"""
	Get all game info files, optionally filtered by season and/or division.

	Args:
		season_id: Optional season ID to filter by
		division: Optional division (1, 2, or 3) to filter by
		base_dir: Base data directory

	Returns:
		List of (season_id, division, game_id, file_path) tuples
	"""
	files = []

	if season_id:
		seasons = [(season_id, Path(base_dir) / season_id)]
	else:
		seasons = get_all_season_dirs(base_dir)

	for sid, season_path in seasons:
		# Determine which divisions to check
		if division is not None:
			divisions_to_check = [division]
		else:
			divisions_to_check = get_all_divisions_for_season(sid, base_dir)
			# Fallback to check old structure (no division subdirs)
			if not divisions_to_check:
				divisions_to_check = [None]

		for div in divisions_to_check:
			if div is None:
				# Old structure: data/{season}/games/
				games_dir = season_path / "games"
			else:
				# New structure: data/{season}/division{n}/games/
				games_dir = season_path / f"division{div}" / "games"

			if not games_dir.exists():
				continue

			for file_path in games_dir.glob("game_*_info.json"):
				# Extract game ID from filename
				parts = file_path.stem.split("_")
				if len(parts) >= 2:
					game_id = parts[1]
					files.append((sid, div, game_id, file_path))

	return files
