# Browser-Based Game Data Fetching

## Why Browser Fetching?

stats.ncaa.org uses Akamai CDN which blocks Python `requests` (and similar HTTP clients). The site requires a real browser with JavaScript execution to pass bot detection. We use `agent-browser` to control a local browser instance via Chrome DevTools Protocol (CDP).

## How agent-browser Works

1. Launch a browser with remote debugging enabled:
   ```bash
   /Applications/Brave\ Browser.app/Contents/MacOS/Brave\ Browser --remote-debugging-port=9222
   ```

2. Connect agent-browser to the running browser:
   ```bash
   agent-browser connect 9222
   ```

3. Control the browser programmatically:
   ```bash
   agent-browser open "https://stats.ncaa.org/contests/6309665/individual_stats"
   agent-browser eval "document.title"
   ```

## JS Extractor Pattern

Instead of fetching raw HTML and parsing it server-side (which produces mangled whitespace), we run JavaScript directly in the browser's DOM context. Each extractor is an IIFE that:

1. Queries the rendered DOM using standard selectors
2. Extracts structured data from elements
3. Returns a `JSON.stringify()`'d result

**Important:** JS string literals in extractors must use single quotes only. `agent-browser eval` wraps the expression in double quotes via `json.dumps()`, so inner double quotes break the shell quoting even when escaped.

### Extractors

| File | Page | Output |
|------|------|--------|
| `_extract_game_info.js` | `/contests/{id}/individual_stats` | Game metadata (teams, scores, date, venue) |
| `_extract_player_stats.js` | `/contests/{id}/individual_stats` | Player stats array |
| `_extract_plays.js` | `/contests/{id}/play_by_play` | Play-by-play events array |
| `_extract_games.js` | `/season_divisions/{id}/livestream_scoreboards` | Game ID discovery |
| `_extract_schedule_info.js` | `/contests/{id}` | Schedule data for future games (teams, date, location) |

### Header Cell Gotcha

Some `<th>` cells use `<br>` tags (e.g. `<th>FO<br>Won</th>`). `textContent` collapses these to `FOWon`; use `innerText` which preserves linebreaks, then replace `\n` with spaces to get `FO Won`.

### Python Integration

```python
def eval_js(js_file: Path) -> str:
    js = js_file.read_text().replace("\n", " ").replace("\t", " ")
    result = subprocess.run(
        f'agent-browser eval {json.dumps(js)}',
        capture_output=True, text=True, timeout=30, shell=True
    )
    raw = result.stdout.strip().strip('"').replace('\\"', '"')
    return raw
```

The `shell=True` + `json.dumps()` pattern preserves JS quoting through the shell. The output is wrapped in quotes with escaped inner quotes by agent-browser, so we strip and unescape.

### Page Readiness

Don't use fixed `time.sleep()` after navigation. Instead, poll for a DOM selector that indicates the page content has rendered:

```python
def wait_for_selector(selector, timeout=10.0, interval=1.0):
    # Returns True when found, raises on "Box score not available" or "Access Denied"
```

This handles three cases:
- **Content loaded** — selector found, proceed with extraction
- **No data** — "Box score not available" detected, fail fast
- **CDN block** — "Access Denied" detected, fail fast

## Running

### Dry run (check what needs fetching)
```bash
python3 scripts/fetching/fetch_games_browser.py --season 2026 --dry-run
python3 scripts/fetching/fetch_schedules_browser.py --season 2026 --dry-run
```

### Fetch all missing games
```bash
python3 scripts/fetching/fetch_games_browser.py --season 2026
```

### Fetch schedules for future games
```bash
python3 scripts/fetching/fetch_schedules_browser.py --season 2026
```

Uses the main `/contests/{id}` page (not `/individual_stats`) which is available for unplayed games. Saves `game_{id}_schedule.json` with `status: "scheduled"` and no scores. Skips games already in the database or with existing info/schedule files.

### Full daily sync
```bash
python3 scripts/sync_daily.py --season 2026
```

## Adding New Extractors

1. Create `scripts/utils/_extract_<name>.js` as an IIFE returning `JSON.stringify(data)`
2. Test in browser DevTools console first
3. Add to `fetch_games_browser.py`: define the path, call `eval_js()`, parse with `parse_eval_json()`
4. Handle errors by checking for `{error: "..."}` in the returned JSON

## Error Detection

The fetcher detects two types of problems:

### Box Score Not Available

Some game IDs have no published stats (future games or missing submissions). These fail fast during the `wait_for_selector` poll and are recorded in `failed_games.json`. Re-running the fetcher retries them since no output files are written.

### NCAA Stat Error Flags

Some games display a banner: "This box score has errors and the data will not be reflected in season to date stats or national rankings until the following errors are fixed." These are typically team/player stat total mismatches (assists, turnovers, etc.).

The data is still extracted and saved normally. Flagged games are additionally recorded in `flagged_games.json` with the error text, team names, and date.

## Rate Limiting

- Poll-based wait after navigation (typically 2-5s until DOM ready, 10s timeout)
- 2s between page navigations within a game
- 2s between games

## Output Structure

```
data/{season}/division{n}/
├── raw/
│   └── game_ids.json               # discovered game IDs
└── games/
    ├── game_{id}_info.json          # game metadata (final games)
    ├── game_{id}_player_stats.json  # player statistics
    ├── game_{id}_plays.json         # play-by-play events
    ├── game_{id}_schedule.json      # schedule data (future games, no scores)
    ├── failed_games.json            # games with no box score on NCAA site
    ├── failed_schedules.json        # games where schedule fetch failed
    └── flagged_games.json           # games with NCAA stat errors
```
