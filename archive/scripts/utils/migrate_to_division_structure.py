#!/usr/bin/env python3
"""
Migrate existing data from season-only structure to season+division structure.

Transforms:
    data/{season}/games/        → data/{season}/division1/games/
    data/{season}/raw/          → data/{season}/division1/raw/

This script:
1. Identifies seasons with old structure (direct games/ and raw/ subdirs)
2. Creates new division1/ subdirectories
3. Moves existing data into division1/ folders
4. Validates file counts before and after
5. Supports --dry-run for safe testing

Usage:
    python3 scripts/utils/migrate_to_division_structure.py --dry-run
    python3 scripts/utils/migrate_to_division_structure.py
    python3 scripts/utils/migrate_to_division_structure.py --season 2025
"""

import argparse
import sys
from pathlib import Path
import shutil


def check_old_structure(season_path):
	"""
	Check if a season directory uses the old structure.

	Args:
		season_path: Path to season directory

	Returns:
		True if old structure (has direct games/ or raw/ subdirs)
	"""
	games_dir = season_path / "games"
	raw_dir = season_path / "raw"
	return games_dir.exists() or raw_dir.exists()


def check_new_structure(season_path):
	"""
	Check if a season directory uses the new structure.

	Args:
		season_path: Path to season directory

	Returns:
		True if new structure (has division* subdirs)
	"""
	for item in season_path.iterdir():
		if item.is_dir() and item.name.startswith("division"):
			return True
	return False


def count_files_in_dir(directory):
	"""Count all files recursively in a directory."""
	if not directory.exists():
		return 0
	return sum(1 for _ in directory.rglob("*") if _.is_file())


def migrate_season(season_id, season_path, dry_run=False):
	"""
	Migrate a single season from old to new structure.

	Args:
		season_id: Season ID (year as string)
		season_path: Path to season directory
		dry_run: If True, only show what would be done

	Returns:
		True if migration successful or not needed
	"""
	print(f"\n{'[DRY RUN] ' if dry_run else ''}Checking season {season_id}...")

	# Check if already migrated
	if check_new_structure(season_path):
		print(f"  ✓ Season {season_id} already uses new structure (has division subdirs)")
		return True

	# Check if uses old structure
	if not check_old_structure(season_path):
		print(f"  ℹ Season {season_id} has no data to migrate")
		return True

	# Count files before migration
	games_dir = season_path / "games"
	raw_dir = season_path / "raw"
	games_count = count_files_in_dir(games_dir)
	raw_count = count_files_in_dir(raw_dir)
	total_before = games_count + raw_count

	print(f"  Found old structure:")
	print(f"    games/: {games_count} files")
	print(f"    raw/:   {raw_count} files")
	print(f"    Total:  {total_before} files")

	# Define new paths
	division1_dir = season_path / "division1"
	new_games_dir = division1_dir / "games"
	new_raw_dir = division1_dir / "raw"

	if dry_run:
		print(f"  Would create: {division1_dir}")
		if games_dir.exists():
			print(f"  Would move: {games_dir} → {new_games_dir}")
		if raw_dir.exists():
			print(f"  Would move: {raw_dir} → {new_raw_dir}")
		return True

	# Create division1 directory
	try:
		division1_dir.mkdir(exist_ok=True)
		print(f"  Created: {division1_dir}")

		# Move games directory
		if games_dir.exists():
			shutil.move(str(games_dir), str(new_games_dir))
			print(f"  Moved: games/ → division1/games/")

		# Move raw directory
		if raw_dir.exists():
			shutil.move(str(raw_dir), str(new_raw_dir))
			print(f"  Moved: raw/ → division1/raw/")

		# Verify file counts
		total_after = count_files_in_dir(division1_dir)
		if total_after != total_before:
			print(f"  ⚠ WARNING: File count mismatch!")
			print(f"    Before: {total_before} files")
			print(f"    After:  {total_after} files")
			return False

		print(f"  ✓ Migration successful: {total_after} files preserved")
		return True

	except Exception as e:
		print(f"  ✗ Error during migration: {e}")
		return False


def main():
	parser = argparse.ArgumentParser(
		description="Migrate data from season-only to season+division structure"
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Show what would be done without making changes"
	)
	parser.add_argument(
		"--season",
		type=str,
		help="Migrate only a specific season (e.g., 2025)"
	)
	parser.add_argument(
		"--base-dir",
		type=str,
		default="data",
		help="Base data directory (default: data)"
	)

	args = parser.parse_args()

	base_path = Path(args.base_dir)
	if not base_path.exists():
		print(f"Error: Base directory '{args.base_dir}' does not exist")
		return 1

	print(f"{'='*60}")
	print(f"Data Structure Migration to Multi-Division Support")
	print(f"{'='*60}")
	print(f"Base directory: {base_path.absolute()}")
	if args.dry_run:
		print("Mode: DRY RUN (no changes will be made)")
	if args.season:
		print(f"Target: Season {args.season} only")
	print()

	# Get seasons to migrate
	if args.season:
		season_path = base_path / args.season
		if not season_path.exists():
			print(f"Error: Season directory '{args.season}' does not exist")
			return 1
		seasons = [(args.season, season_path)]
	else:
		seasons = []
		for item in base_path.iterdir():
			if item.is_dir() and item.name.isdigit():
				seasons.append((item.name, item))
		seasons.sort(key=lambda x: x[0])

	if not seasons:
		print("No season directories found")
		return 0

	# Migrate each season
	success_count = 0
	fail_count = 0

	for season_id, season_path in seasons:
		result = migrate_season(season_id, season_path, dry_run=args.dry_run)
		if result:
			success_count += 1
		else:
			fail_count += 1

	# Summary
	print(f"\n{'='*60}")
	print("Migration Summary")
	print(f"{'='*60}")
	print(f"Seasons processed: {len(seasons)}")
	print(f"Successful:        {success_count}")
	print(f"Failed:            {fail_count}")

	if args.dry_run:
		print("\nThis was a dry run. To perform migration, run without --dry-run flag.")
		return 0

	if fail_count > 0:
		print("\n⚠ Some migrations failed. Review errors above.")
		return 1

	print("\n✓ All migrations completed successfully")
	return 0


if __name__ == "__main__":
	sys.exit(main())
