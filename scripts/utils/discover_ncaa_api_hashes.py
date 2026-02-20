#!/usr/bin/env python3
"""
One-time utility to discover ncaa.com GraphQL hashes by intercepting browser network traffic.

Uses Playwright headless to navigate to a game page and capture all POST requests
to sdataprod.ncaa.com, printing each operation's name and sha256Hash.

Usage:
	python3 scripts/utils/discover_ncaa_api_hashes.py --game-id 6538788
	python3 scripts/utils/discover_ncaa_api_hashes.py --game-id 6538788 --wait 30
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
	from playwright.sync_api import sync_playwright
except ImportError:
	print("Error: playwright not installed. Run: pip install playwright && playwright install chromium")
	sys.exit(1)


def discover_hashes(game_id: str, wait_seconds: int = 20) -> dict[str, str]:
	"""
	Navigate to a game page with Playwright and intercept GraphQL requests.

	Returns a dict mapping operation_name -> sha256Hash.
	"""
	found: dict[str, str] = {}

	def on_request(request):
		"""Capture outgoing POST requests to sdataprod.ncaa.com."""
		if "sdataprod.ncaa.com" not in request.url:
			return
		try:
			body = request.post_data
			if not body:
				return
			data = json.loads(body)
			op = data.get("operationName", "")
			ext = data.get("extensions", {})
			pq = ext.get("persistedQuery", {})
			h = pq.get("sha256Hash", "")
			if h and op:
				found[op] = h
				print(f"  Found: {op} → {h}")
		except Exception:
			pass

	with sync_playwright() as p:
		browser = p.chromium.launch(headless=True)
		context = browser.new_context(
			user_agent=(
				"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
				"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
			)
		)
		page = context.new_page()
		page.on("request", on_request)

		print(f"Navigating to game {game_id}...")
		page.goto(f"https://www.ncaa.com/game/{game_id}", wait_until="domcontentloaded")
		print(f"Page loaded. Waiting {wait_seconds}s for React to fire API calls...")
		time.sleep(wait_seconds)

		print("\nNavigating to play-by-play tab...")
		page.goto(f"https://www.ncaa.com/game/{game_id}/play-by-play", wait_until="domcontentloaded")
		time.sleep(wait_seconds)

		browser.close()

	return found


def main():
	parser = argparse.ArgumentParser(description="Discover ncaa.com GraphQL hashes via Playwright")
	parser.add_argument("--game-id", default="6538788", help="Known ncaa.com game ID")
	parser.add_argument("--wait", type=int, default=20, help="Seconds to wait after page load")
	args = parser.parse_args()

	print(f"Known: scoreboard → 7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c")
	print()
	hashes = discover_hashes(args.game_id, args.wait)

	if hashes:
		print(f"\nAll discovered hashes ({len(hashes)}):")
		for op, h in sorted(hashes.items()):
			print(f"  {op}: {h}")
		print("\nPaste relevant hashes into fetch_games_ncaa.py")
	else:
		print("\nNo GraphQL hashes captured.")
		print("The game detail data may be in server-rendered HTML, not GraphQL.")
		print("Use --wait with a larger value if React hasn't loaded yet.")


if __name__ == "__main__":
	main()
