#!/usr/bin/env python3
"""
Execute the multi-division database migration.

This script runs the SQL migration in scripts/loading/add_division_support.sql
to add division tracking to the database schema.

Usage:
	python3 scripts/loading/run_division_migration.py
	python3 scripts/loading/run_division_migration.py --dry-run
"""

import json
import os
import sys
from pathlib import Path
from supabase import create_client, Client


def load_config():
	"""Load Supabase configuration."""
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


def load_env():
	"""Load service role key from .env.local."""
	env_path = Path(".env.local")
	if not env_path.exists():
		print("Error: .env.local not found", file=sys.stderr)
		print("This script requires the service role key from .env.local", file=sys.stderr)
		sys.exit(1)

	with open(env_path) as f:
		for line in f:
			line = line.strip()
			if line.startswith("SUPABASE_SERVICE_KEY="):
				return line.split("=", 1)[1]

	print("Error: SUPABASE_SERVICE_KEY not found in .env.local", file=sys.stderr)
	sys.exit(1)


def read_migration_sql():
	"""Read the migration SQL file."""
	sql_path = Path("scripts/loading/add_division_support.sql")
	if not sql_path.exists():
		print(f"Error: {sql_path} not found", file=sys.stderr)
		sys.exit(1)

	with open(sql_path) as f:
		return f.read()


def execute_migration(dry_run=False):
	"""Execute the database migration."""
	print("Multi-Division Database Migration")
	print("=" * 60)

	# Load configuration
	config = load_config()
	service_key = load_env()
	supabase: Client = create_client(config['supabase_url'], service_key)

	# Read migration SQL
	sql = read_migration_sql()

	if dry_run:
		print("\n[DRY RUN MODE - No changes will be made]")
		print("\nMigration SQL preview:")
		print("-" * 60)
		# Show first 20 lines
		lines = sql.split('\n')[:20]
		print('\n'.join(lines))
		print(f"\n... ({len(sql.split(chr(10)))} total lines)")
		print("-" * 60)
		print("\nRun without --dry-run to execute migration")
		return True

	print("\nWarning: This will modify your database schema!")
	print("Recommended: Back up your database before proceeding.")
	print("\nMigration will:")
	print("  1. Create 'divisions' reference table")
	print("  2. Add division_id columns to all tables")
	print("  3. Update indexes and constraints")
	print("  4. Recreate materialized view with division support")
	print("\nAll existing data will default to division_id = 1 (Division I)")

	response = input("\nProceed with migration? (yes/no): ")
	if response.lower() != 'yes':
		print("Migration cancelled")
		return False

	print("\nExecuting migration...")

	try:
		# Split SQL into individual statements (basic approach)
		# Note: This is a simplified parser - complex SQL may need better handling
		statements = []
		current = []
		in_block = False

		for line in sql.split('\n'):
			stripped = line.strip()

			# Skip comments and empty lines
			if not stripped or stripped.startswith('--'):
				continue

			# Track DO blocks
			if stripped.startswith('DO $$'):
				in_block = True

			current.append(line)

			# End of statement
			if (stripped.endswith(';') and not in_block) or \
			   (in_block and stripped == 'END $$;'):
				statements.append('\n'.join(current))
				current = []
				in_block = False

		print(f"\nFound {len(statements)} SQL statements to execute")

		# Execute each statement
		for i, stmt in enumerate(statements, 1):
			stmt_preview = stmt[:50].replace('\n', ' ') + '...'
			print(f"\n[{i}/{len(statements)}] Executing: {stmt_preview}")

			try:
				# Execute via RPC
				result = supabase.rpc('execute_sql', {'query': stmt}).execute()
				print(f"  ✓ Success")
			except Exception as e:
				# Try direct query method
				try:
					result = supabase.postgrest.rpc('execute_sql', {'query': stmt}).execute()
					print(f"  ✓ Success")
				except Exception as e2:
					print(f"  ✗ Failed: {e}")
					print(f"    Alternative method also failed: {e2}")
					print("\n  Statement:")
					print("  " + stmt[:200].replace('\n', '\n  '))
					print("\n  You may need to run this migration manually in Supabase SQL Editor")
					return False

		print("\n" + "=" * 60)
		print("Migration completed successfully!")
		print("\nNext steps:")
		print("  1. Verify migration with included queries in SQL file")
		print("  2. Update loading scripts to write division_id")
		print("  3. Test loading D2/D3 data when available")

		return True

	except Exception as e:
		print(f"\nError executing migration: {e}", file=sys.stderr)
		print("\nRecommendation: Run migration manually in Supabase SQL Editor")
		print("SQL file: scripts/loading/add_division_support.sql")
		return False


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(
		description='Execute multi-division database migration'
	)
	parser.add_argument('--dry-run', action='store_true',
		help='Preview migration without executing')
	args = parser.parse_args()

	success = execute_migration(dry_run=args.dry_run)
	sys.exit(0 if success else 1)
