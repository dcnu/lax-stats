#!/usr/bin/env python3
"""
Database ping script to keep Supabase free tier active.

Retrieves a small number of rows from the database to prevent account pausing.

Usage:
	python3 scripts/utils/ping_database.py
	python3 scripts/utils/ping_database.py --verbose
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from supabase import create_client, Client


def load_config():
	"""Load Supabase configuration from config.json."""
	config_path = Path("config.json")
	if not config_path.exists():
		print("Error: config.json not found", file=sys.stderr)
		sys.exit(1)

	with open(config_path) as f:
		config = json.load(f)

	if 'supabase_url' not in config or 'supabase_key' not in config:
		print("Error: Supabase credentials not found in config.json", file=sys.stderr)
		sys.exit(1)

	return config


def ping_database(verbose=False):
	"""Ping database by retrieving a small number of rows."""
	try:
		config = load_config()
		supabase: Client = create_client(config['supabase_url'], config['supabase_key'])

		if verbose:
			print(f"[{datetime.now().isoformat()}] Pinging Supabase database...")

		# Try to retrieve data from games table (will work even if empty)
		response = supabase.table('games').select('id, game_date').limit(10).execute()

		# Connection successful regardless of data presence
		row_count = len(response.data) if response.data else 0
		if verbose:
			print(f"[{datetime.now().isoformat()}] Database connection successful")
			print(f"Retrieved {row_count} rows from games table")
			if row_count > 0:
				print(f"Sample game: {response.data[0]['id']}")
		else:
			print(f"Database ping successful: {row_count} rows retrieved")
		return True

	except Exception as e:
		print(f"Error pinging database: {e}", file=sys.stderr)
		return False


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description='Ping Supabase database to keep it active')
	parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
	args = parser.parse_args()

	success = ping_database(verbose=args.verbose)
	sys.exit(0 if success else 1)
