#!/usr/bin/env python3
"""
Compare ncaa.com and stats.ncaa.org data quality for matched games.

Reads game_id_map.json and corresponding game files from both sources,
then prints a comparison report without loading anything to the database.

Usage:
    python3 scripts/utils/compare_sources.py --season 2026
    python3 scripts/utils/compare_sources.py --season 2026 --csv report.csv
    python3 scripts/utils/compare_sources.py --season 2026 --verbose
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_ncaa_dir, get_season_games_dir


def load_json(path: Path) -> dict | list | None:
    """Load a JSON file, returning None on failure."""
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def count_players(player_stats: dict | list | None) -> int:
    """Count total players (non-goalie) across both teams."""
    if not player_stats:
        return 0
    if isinstance(player_stats, dict):
        # ncaa.com format: {away: {players: [...], goalies: [...]}, home: {...}}
        total = 0
        for side in ("away", "home"):
            side_data = player_stats.get(side, {})
            total += len(side_data.get("players", []))
        return total
    if isinstance(player_stats, list):
        # stats.ncaa.org format: flat list
        return len(player_stats)
    return 0


def count_goalies(player_stats: dict | list | None) -> int:
    """Count goalies across both teams (ncaa.com only)."""
    if not isinstance(player_stats, dict):
        return 0
    total = 0
    for side in ("away", "home"):
        side_data = player_stats.get(side, {})
        total += len(side_data.get("goalies", []))
    return total


def get_stat_fields(player_stats: dict | list | None, source: str) -> set[str]:
    """Extract stat field names from the first non-empty player record."""
    if not player_stats:
        return set()
    if source == "ncaa" and isinstance(player_stats, dict):
        for side in ("away", "home"):
            players = player_stats.get(side, {}).get("players", [])
            if players:
                return set(players[0].keys()) - {"name", "playerId", "jersey", "position", "tableIndex"}
    if source == "stats" and isinstance(player_stats, list):
        if player_stats:
            return set(player_stats[0].keys()) - {"name", "playerId", "jersey", "position"}
    return set()


def scores_match(ncaa_info: dict, stats_info: dict) -> bool:
    """Compare scores between the two sources."""
    try:
        return (
            int(ncaa_info.get("homeScore", -1)) == int(stats_info.get("homeScore", -2))
            and int(ncaa_info.get("awayScore", -1)) == int(stats_info.get("awayScore", -2))
        )
    except (TypeError, ValueError):
        return False


def analyze_game(
    ncaa_game_id: str,
    stats_game_id: str,
    ncaa_dir: Path,
    stats_dir: Path,
) -> dict:
    """Analyze one matched game pair and return a metrics dict."""
    ncaa_info = load_json(ncaa_dir / f"game_{ncaa_game_id}_info.json")
    ncaa_stats = load_json(ncaa_dir / f"game_{ncaa_game_id}_player_stats.json")
    ncaa_plays = load_json(ncaa_dir / f"game_{ncaa_game_id}_plays.json")

    stats_info = load_json(stats_dir / f"game_{stats_game_id}_info.json")
    stats_stats = load_json(stats_dir / f"game_{stats_game_id}_player_stats.json")
    stats_plays = load_json(stats_dir / f"game_{stats_game_id}_plays.json")

    ncaa_has_info = ncaa_info is not None
    stats_has_info = stats_info is not None
    score_agree = scores_match(ncaa_info or {}, stats_info or {}) if ncaa_has_info and stats_has_info else None

    return {
        "ncaaGameId": ncaa_game_id,
        "statsGameId": stats_game_id,
        "ncaa_has_info": ncaa_has_info,
        "ncaa_has_stats": ncaa_stats is not None,
        "ncaa_has_plays": isinstance(ncaa_plays, list) and len(ncaa_plays) > 0,
        "ncaa_play_count": len(ncaa_plays) if isinstance(ncaa_plays, list) else 0,
        "ncaa_player_count": count_players(ncaa_stats),
        "ncaa_goalie_count": count_goalies(ncaa_stats),
        "ncaa_stat_fields": get_stat_fields(ncaa_stats, "ncaa"),
        "stats_has_info": stats_has_info,
        "stats_has_stats": stats_stats is not None,
        "stats_has_plays": isinstance(stats_plays, list) and len(stats_plays) > 0,
        "stats_play_count": len(stats_plays) if isinstance(stats_plays, list) else 0,
        "stats_player_count": count_players(stats_stats),
        "stats_stat_fields": get_stat_fields(stats_stats, "stats"),
        "score_agree": score_agree,
        "score_discrepancy": (
            not score_agree
            and ncaa_has_info
            and stats_has_info
            and score_agree is False
        ),
        "date": "",
        "homeTeam": ncaa_info.get("homeTeam", "") if ncaa_info else "",
        "awayTeam": ncaa_info.get("awayTeam", "") if ncaa_info else "",
    }


def print_report(
    matched: list[dict],
    unmatched_ncaa: list[dict],
    game_metrics: list[dict],
    verbose: bool,
) -> None:
    """Print a human-readable comparison report."""
    total_ncaa = len(matched) + len(unmatched_ncaa)

    print("=" * 60)
    print("SOURCE COMPARISON REPORT")
    print("=" * 60)

    print(f"\nCoverage")
    print(f"  ncaa.com games total:      {total_ncaa}")
    print(f"  Matched to stats.ncaa.org: {len(matched)} ({100*len(matched)/total_ncaa:.1f}%)" if total_ncaa else "  No games")
    print(f"  Unmatched (ncaa.com only): {len(unmatched_ncaa)}")

    if not game_metrics:
        return

    fetched = [g for g in game_metrics if g["ncaa_has_info"] or g["stats_has_info"]]
    ncaa_fetched = [g for g in game_metrics if g["ncaa_has_info"]]
    stats_fetched = [g for g in game_metrics if g["stats_has_info"]]

    print(f"\nData Availability (of {len(matched)} matched games)")
    print(f"  ncaa.com files fetched:      {len(ncaa_fetched)}")
    print(f"  stats.ncaa.org files fetched:{len(stats_fetched)}")

    if ncaa_fetched:
        ncaa_with_plays = sum(1 for g in ncaa_fetched if g["ncaa_has_plays"])
        print(f"\nPlay-by-Play")
        print(f"  ncaa.com with plays:        {ncaa_with_plays}/{len(ncaa_fetched)} ({100*ncaa_with_plays/len(ncaa_fetched):.1f}%)")
        avg_ncaa_plays = sum(g["ncaa_play_count"] for g in ncaa_fetched if g["ncaa_has_plays"]) / max(ncaa_with_plays, 1)
        print(f"  avg plays/game (ncaa.com):  {avg_ncaa_plays:.1f}")

    if stats_fetched:
        stats_with_plays = sum(1 for g in stats_fetched if g["stats_has_plays"])
        print(f"  stats.ncaa.org with plays:  {stats_with_plays}/{len(stats_fetched)} ({100*stats_with_plays/len(stats_fetched):.1f}%)")

    comparable = [g for g in game_metrics if g["ncaa_has_info"] and g["stats_has_info"]]
    if comparable:
        score_agree = sum(1 for g in comparable if g["score_agree"])
        print(f"\nScore Agreement ({len(comparable)} games with both sources)")
        print(f"  Agree:    {score_agree}/{len(comparable)} ({100*score_agree/len(comparable):.1f}%)")
        print(f"  Disagree: {len(comparable) - score_agree}")

        avg_ncaa_players = sum(g["ncaa_player_count"] for g in comparable) / len(comparable)
        avg_stats_players = sum(g["stats_player_count"] for g in comparable) / len(comparable)
        print(f"\nPlayer Counts (avg per game)")
        print(f"  ncaa.com:        {avg_ncaa_players:.1f}")
        print(f"  stats.ncaa.org:  {avg_stats_players:.1f}")

        # Stat field comparison
        ncaa_fields: set[str] = set()
        stats_fields: set[str] = set()
        for g in comparable:
            ncaa_fields |= g["ncaa_stat_fields"]
            stats_fields |= g["stats_stat_fields"]
        ncaa_only = ncaa_fields - stats_fields
        stats_only = stats_fields - ncaa_fields
        shared = ncaa_fields & stats_fields
        print(f"\nStat Fields")
        print(f"  Shared ({len(shared)}):          {', '.join(sorted(shared))}")
        if ncaa_only:
            print(f"  ncaa.com only ({len(ncaa_only)}): {', '.join(sorted(ncaa_only))}")
        if stats_only:
            print(f"  stats only ({len(stats_only)}):   {', '.join(sorted(stats_only))}")

    discrepancies = [g for g in game_metrics if g["score_discrepancy"]]
    if discrepancies:
        print(f"\nScore Discrepancies ({len(discrepancies)} games):")
        for g in discrepancies:
            print(f"  ncaa {g['ncaaGameId']} / stats {g['statsGameId']}: {g['awayTeam']} @ {g['homeTeam']} ({g['date']})")

    if verbose and unmatched_ncaa:
        print(f"\nUnmatched ncaa.com games:")
        for g in unmatched_ncaa:
            print(f"  ncaa {g['ncaaGameId']}: {g.get('awayTeam','')} @ {g.get('homeTeam','')} ({g.get('date','')})")

    print()


def write_csv(path: str, game_metrics: list[dict]) -> None:
    """Write per-game metrics to a CSV file."""
    if not game_metrics:
        return
    fields = [
        "ncaaGameId", "statsGameId", "date", "awayTeam", "homeTeam",
        "ncaa_has_info", "ncaa_has_stats", "ncaa_has_plays", "ncaa_play_count",
        "ncaa_player_count", "ncaa_goalie_count",
        "stats_has_info", "stats_has_stats", "stats_has_plays", "stats_play_count",
        "stats_player_count", "score_agree",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(game_metrics)
    print(f"CSV written to {path}")


def main():
    parser = argparse.ArgumentParser(description="Compare ncaa.com vs stats.ncaa.org data quality")
    parser.add_argument("--season", default="2026", help="Season year")
    parser.add_argument("--division", type=int, default=1)
    parser.add_argument("--csv", metavar="FILE", help="Write per-game metrics to this CSV file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show unmatched game details")
    args = parser.parse_args()

    ncaa_dir = get_season_ncaa_dir(args.season, args.division)
    stats_dir = get_season_games_dir(args.season, args.division)

    map_file = ncaa_dir / "game_id_map.json"
    if not map_file.exists():
        print(f"Error: {map_file} not found. Run map_game_ids.py first.", file=sys.stderr)
        sys.exit(1)

    with open(map_file, "r") as f:
        game_map: list[dict] = json.load(f)

    matched = [g for g in game_map if g.get("statsGameId")]
    unmatched_ncaa = [g for g in game_map if not g.get("statsGameId")]

    print(f"Analyzing {len(matched)} matched game pairs...")
    game_metrics: list[dict] = []
    for entry in matched:
        ncaa_id = str(entry["ncaaGameId"])
        stats_id = str(entry["statsGameId"])
        metrics = analyze_game(ncaa_id, stats_id, ncaa_dir, stats_dir)
        metrics["date"] = entry.get("date", "")
        if not metrics["homeTeam"]:
            metrics["homeTeam"] = entry.get("homeTeam", "")
        if not metrics["awayTeam"]:
            metrics["awayTeam"] = entry.get("awayTeam", "")
        game_metrics.append(metrics)

    print_report(matched, unmatched_ncaa, game_metrics, args.verbose)

    if args.csv:
        write_csv(args.csv, game_metrics)


if __name__ == "__main__":
    main()
