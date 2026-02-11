"""
Shared browser automation utilities for agent-browser scripts.

Provides common functions for navigating pages, evaluating JS, and
parsing results via the agent-browser CLI.
"""

import json
import re
import subprocess
import time
from pathlib import Path


def run_ab(*args) -> str:
	"""Run an agent-browser command and return stdout."""
	result = subprocess.run(
		["agent-browser"] + list(args),
		capture_output=True, text=True, timeout=30
	)
	return result.stdout.strip()


def eval_js_inline(js: str) -> str:
	"""Evaluate an inline JS expression and return stdout."""
	result = subprocess.run(
		f'agent-browser eval {json.dumps(js)}',
		capture_output=True, text=True, timeout=30, shell=True
	)
	return result.stdout.strip().strip('"').replace('\\"', '"')


def wait_for_selector(selector: str, timeout: float = 10.0, interval: float = 1.0) -> bool:
	"""Poll until a CSS selector is found on the page or timeout."""
	check = (
		f"document.querySelector('{selector}') ? 'found' "
		f": document.body.innerText.includes('Box score not available') ? 'nodata' "
		f": document.body.innerText.includes('Access Denied') ? 'blocked' "
		f": 'missing'"
	)
	elapsed = 0.0
	while elapsed < timeout:
		time.sleep(interval)
		elapsed += interval
		result = eval_js_inline(check)
		if result == 'found':
			return True
		if result == 'nodata':
			raise ValueError("Box score not available")
		if result == 'blocked':
			raise ValueError("Access Denied by CDN")
	return False


def eval_js(js_file: Path) -> str:
	"""Evaluate a JS file in the browser and return the raw output string."""
	js = js_file.read_text().replace("\n", " ").replace("\t", " ")
	result = subprocess.run(
		f'agent-browser eval {json.dumps(js)}',
		capture_output=True, text=True, timeout=30, shell=True
	)
	raw = result.stdout.strip().strip('"').replace('\\"', '"')
	return raw


def parse_eval_json(raw: str) -> dict | list:
	"""Parse JSON from eval output, searching for the JSON structure."""
	# Try direct parse first
	try:
		return json.loads(raw)
	except json.JSONDecodeError:
		pass

	# Search for JSON object or array
	for pattern in [r'\{.*\}', r'\[.*\]']:
		match = re.search(pattern, raw, re.DOTALL)
		if match:
			try:
				return json.loads(match.group())
			except json.JSONDecodeError:
				continue

	raise ValueError(f"Could not parse JSON from eval output: {raw[:200]}")
