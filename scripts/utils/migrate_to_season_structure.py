#!/usr/bin/env python3
"""
Migrate existing data from flat structure to season-based structure.

This script moves existing game data and raw files from:
- data/games/* -> data/{season}/games/*
- data/raw/* -> data/{season}/raw/*

The season is determined from the game date in each game info file.

Usage:
	python3 scripts/utils/migrate_to_season_structure.py
	python3 scripts/utils/migrate_to_season_structure.py --dry-run
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_from_date, get_season_games_dir, get_season_raw_dir


def migrate_game_files(dry_run=False):
	"""Migrate game files from data/games to season directories."""
	old_games_dir = Path("data/games")

	if not old_games_dir.exists():
		print("No data/games directory found. Nothing to migrate.")
		return 0

	# Group files by game ID
	game_files = defaultdict(list)
	for file_path in old_games_dir.glob("game_*_*.json"):
		parts = file_path.stem.split("_")
		if len(parts) >= 2:
			game_id = parts[1]
			game_files[game_id].append(file_path)

	if not game_files:
		print("No game files found in data/games. Nothing to migrate.")
		return 0

	print(f"Found {len(game_files)} games to migrate")

	# Process each game
	migrated = 0
	skipped = 0
	errors = 0

	for game_id, files in game_files.items():
		try:
			# Find the info file to determine season
			info_file = None
			for f in files:
				if f.stem.endswith("_info"):
					info_file = f
					break

			if not info_file:
				print(f"Warning: No info file found for game {game_id}, skipping")
				skipped += 1
				continue

			# Read game date
			with open(info_file) as f:
				game_data = json.load(f)
				game_date = game_data.get("gameDate")

			if not game_date:
				print(f"Warning: No gameDate in {info_file}, skipping")
				skipped += 1
				continue

			# Determine season
			season_id = get_season_from_date(game_date)

			# Get destination directory
			dest_dir = get_season_games_dir(season_id)

			# Move all files for this game
			for file_path in files:
				dest_path = dest_dir / file_path.name

				if dest_path.exists():
					print(f"  {file_path.name} already exists in {dest_dir}, skipping")
					skipped += 1
					continue

				if dry_run:
					print(f"  Would move: {file_path} -> {dest_path}")
				else:
					shutil.move(str(file_path), str(dest_path))
					print(f"  Moved: {file_path.name} -> {dest_dir}/")

			migrated += 1

		except Exception as e:
			print(f"Error processing game {game_id}: {e}")
			errors += 1

	print(f"\nMigration summary:")
	print(f"  Migrated: {migrated} games")
	print(f"  Skipped: {skipped} files")
	print(f"  Errors: {errors}")

	return migrated


def migrate_raw_files(season_id, dry_run=False):
	"""Migrate raw files from data/raw to season directory."""
	old_raw_dir = Path("data/raw")

	if not old_raw_dir.exists():
		print("No data/raw directory found. Nothing to migrate.")
		return 0

	# Get destination directory
	dest_dir = get_season_raw_dir(season_id)

	# Find raw files
	raw_files = list(old_raw_dir.glob("*.json"))

	if not raw_files:
		print("No raw files found in data/raw. Nothing to migrate.")
		return 0

	print(f"Found {len(raw_files)} raw files to migrate to season {season_id}")

	migrated = 0
	skipped = 0

	for file_path in raw_files:
		dest_path = dest_dir / file_path.name

		if dest_path.exists():
			print(f"  {file_path.name} already exists in {dest_dir}, skipping")
			skipped += 1
			continue

		if dry_run:
			print(f"  Would move: {file_path} -> {dest_path}")
		else:
			shutil.move(str(file_path), str(dest_path))
			print(f"  Moved: {file_path.name} -> {dest_dir}/")

		migrated += 1

	print(f"\nRaw files migration summary:")
	print(f"  Migrated: {migrated} files")
	print(f"  Skipped: {skipped} files")

	return migrated


def cleanup_old_directories(dry_run=False):
	"""Remove old empty directories after migration."""
	old_games_dir = Path("data/games")
	old_raw_dir = Path("data/raw")

	cleaned = []

	for directory in [old_games_dir, old_raw_dir]:
		if directory.exists():
			if not any(directory.iterdir()):
				if dry_run:
					print(f"Would remove empty directory: {directory}")
				else:
					directory.rmdir()
					print(f"Removed empty directory: {directory}")
					cleaned.append(directory)
			else:
				print(f"Directory not empty, keeping: {directory}")

	return cleaned


def main():
	parser = argparse.ArgumentParser(description="Migrate data to season-based structure")
	parser.add_argument("--season", help="Season ID for raw files (required if raw files exist)")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

	args = parser.parse_args()

	print("=" * 60)
	print("Data Migration to Season-Based Structure")
	print("=" * 60)

	if args.dry_run:
		print("DRY RUN MODE - no changes will be made\n")

	# Migrate game files (determines season from game dates)
	print("\n1. Migrating game files...")
	print("-" * 60)
	migrated_games = migrate_game_files(dry_run=args.dry_run)

	# Migrate raw files if season is provided
	print("\n2. Migrating raw files...")
	print("-" * 60)
	if args.season:
		migrated_raw = migrate_raw_files(args.season, dry_run=args.dry_run)
	else:
		old_raw_dir = Path("data/raw")
		if old_raw_dir.exists() and any(old_raw_dir.glob("*.json")):
			print("Warning: Raw files found but no --season specified")
			print("Re-run with --season YYYY to migrate raw files")
			migrated_raw = 0
		else:
			print("No raw files to migrate")
			migrated_raw = 0

	# Cleanup
	if not args.dry_run and (migrated_games > 0 or migrated_raw > 0):
		print("\n3. Cleaning up empty directories...")
		print("-" * 60)
		cleanup_old_directories(dry_run=args.dry_run)

	print("\n" + "=" * 60)
	print("Migration complete!")
	print("=" * 60)

	if args.dry_run:
		print("\nRe-run without --dry-run to apply changes")


if __name__ == "__main__":
	main()
