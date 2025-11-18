#!/usr/bin/env python3
"""
Execute the multi-division database migration via direct PostgreSQL connection.

This script uses psycopg2 to execute the SQL migration directly.

Usage:
	python3 scripts/loading/execute_division_migration.py
	python3 scripts/loading/execute_division_migration.py --dry-run
"""

import json
import os
import sys
from pathlib import Path


def load_config():
	"""Load Supabase configuration."""
	config_path = Path("config.json")
	if not config_path.exists():
		print("Error: config.json not found", file=sys.stderr)
		sys.exit(1)

	with open(config_path) as f:
		config = json.load(f)

	return config


def load_env():
	"""Load service role key from .env.local."""
	env_path = Path(".env.local")
	if not env_path.exists():
		print("Error: .env.local not found", file=sys.stderr)
		sys.exit(1)

	env_vars = {}
	with open(env_path) as f:
		for line in f:
			line = line.strip()
			if '=' in line and not line.startswith('#'):
				key, value = line.split('=', 1)
				env_vars[key] = value

	return env_vars


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
	env_vars = load_env()

	# Parse database URL from Supabase URL
	supabase_url = config['supabase_url']

	# Extract project reference from URL
	# Format: https://xxxxx.supabase.co
	if 'supabase.co' not in supabase_url:
		print("Error: Invalid Supabase URL format", file=sys.stderr)
		sys.exit(1)

	project_ref = supabase_url.replace('https://', '').replace('.supabase.co', '')

	# Construct connection info
	db_host = f"db.{project_ref}.supabase.co"
	db_name = "postgres"
	db_user = "postgres"
	db_port = 5432

	# Read migration SQL
	sql = read_migration_sql()

	if dry_run:
		print("\n[DRY RUN MODE - No changes will be made]")
		print("\nMigration SQL preview:")
		print("-" * 60)
		lines = sql.split('\n')[:30]
		print('\n'.join(lines))
		print(f"\n... ({len(sql.split(chr(10)))} total lines)")
		print("-" * 60)
		print("\nDatabase connection would be:")
		print(f"  Host: {db_host}")
		print(f"  Database: {db_name}")
		print(f"  User: {db_user}")
		print(f"  Port: {db_port}")
		print("\nRun without --dry-run to execute migration")
		return True

	# Try to get password from environment
	db_password = env_vars.get('SUPABASE_DB_PASSWORD') or env_vars.get('DB_PASSWORD')

	if not db_password:
		print("\nError: Database password not found in .env.local")
		print("Please add one of the following to .env.local:")
		print("  SUPABASE_DB_PASSWORD=your-db-password")
		print("  DB_PASSWORD=your-db-password")
		print("\nYou can find your database password in Supabase:")
		print("  Settings > Database > Connection string > Password")
		sys.exit(1)

	print("\nWarning: This will modify your database schema!")
	print("\nMigration will:")
	print("  1. Create 'divisions' reference table")
	print("  2. Add division_id columns to all tables")
	print("  3. Update indexes and constraints")
	print("  4. Recreate materialized view with division support")
	print("\nAll existing data will default to division_id = 1 (Division I)")
	print(f"\nConnecting to: {db_host}")

	response = input("\nProceed with migration? (yes/no): ")
	if response.lower() != 'yes':
		print("Migration cancelled")
		return False

	# Try to import psycopg2
	try:
		import psycopg2
	except ImportError:
		print("\nError: psycopg2 not installed")
		print("Install with: pip install psycopg2-binary")
		print("\nAlternatively, run the migration manually:")
		print("  1. Open Supabase SQL Editor")
		print("  2. Copy contents of scripts/loading/add_division_support.sql")
		print("  3. Paste and execute")
		sys.exit(1)

	print("\nExecuting migration...")

	try:
		# Connect to database
		conn = psycopg2.connect(
			host=db_host,
			database=db_name,
			user=db_user,
			password=db_password,
			port=db_port,
			sslmode='require'
		)
		conn.autocommit = False
		cursor = conn.cursor()

		print("Connected to database")

		# Execute migration SQL
		print("Executing SQL migration...")
		cursor.execute(sql)

		# Commit transaction
		conn.commit()
		print("Migration committed successfully")

		# Run verification queries
		print("\nRunning verification queries...")

		# Check divisions table
		cursor.execute("SELECT * FROM divisions ORDER BY id")
		divisions = cursor.fetchall()
		print(f"\nDivisions table: {len(divisions)} divisions")
		for div in divisions:
			print(f"  {div[0]}: {div[1]} ({div[2]})")

		# Check division_id columns
		cursor.execute("""
			SELECT 'seasons' AS table_name, division_id, COUNT(*) AS count
			FROM seasons GROUP BY division_id
			UNION ALL
			SELECT 'teams', division_id, COUNT(*) FROM teams GROUP BY division_id
			UNION ALL
			SELECT 'players', division_id, COUNT(*) FROM players GROUP BY division_id
			UNION ALL
			SELECT 'games', division_id, COUNT(*) FROM games GROUP BY division_id
			ORDER BY table_name, division_id
		""")
		counts = cursor.fetchall()
		print("\nRecords by division:")
		for row in counts:
			print(f"  {row[0]}: division {row[1]} = {row[2]} records")

		cursor.close()
		conn.close()

		print("\n" + "=" * 60)
		print("Migration completed successfully!")
		print("\nNext steps:")
		print("  1. Update loading scripts to write division_id")
		print("  2. Test loading D2/D3 data when available")

		return True

	except Exception as e:
		print(f"\nError executing migration: {e}", file=sys.stderr)
		if 'conn' in locals():
			conn.rollback()
			conn.close()
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
