#!/usr/bin/env python3
"""
Parse lookup_teams.name into short_name and mascot fields.

Strategy:
  1. Collect ncaa.com team names from game ID and info files (these are already short names).
  2. Fuzzy-match each ncaa.com name to a lookup_teams record.
  3. For matched records: short_name = ncaa.com name, mascot = name with short_name prefix removed.
  4. For unmatched records: programmatic parse — strip mascot words from end of name.
  5. UPDATE lookup_teams in database.

Usage:
    python3 scripts/loading/parse_team_names.py --season 2026 --dry-run
    python3 scripts/loading/parse_team_names.py --season 2026
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_connection
from utils.path_helpers import get_season_ncaa_dir, get_season_games_dir


def make_slug(short_name: str) -> str:
    """
    Generate a URL slug from a team's short_name (school name without mascot).

    Examples:
      "Richmond"      -> "richmond"
      "Johns Hopkins" -> "johns-hopkins"
      "St. John's (NY)" -> "st-johns-ny"
      "Queens (NC)"   -> "queens-nc"
      "Le Moyne"      -> "le-moyne"
    """
    s = short_name.strip()
    # Normalize unicode (e.g. accented chars → ASCII approximation)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    # Remove apostrophes, backticks, periods (St. → st, O'Brien → obrien)
    s = re.sub(r"[''`.]", "", s)
    # (XX) parenthetical suffix → -xx
    s = re.sub(r"\(([^)]+)\)", lambda m: "-" + m.group(1), s)
    # Remaining non-alphanumeric → hyphen
    s = re.sub(r"[^a-z0-9\-]", "-", s)
    # Collapse and trim hyphens
    s = re.sub(r"-+", "-", s).strip("-")
    return s


# Words that indicate part of school name, not mascot
SCHOOL_WORDS = {
    "university", "college", "institute", "school", "academy", "polytechnic",
    "state", "tech", "a&m", "and", "at", "of", "the",
}


def normalize(name: str) -> str:
    """Normalize a team name for comparison."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9 ]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def token_overlap(a: str, b: str) -> float:
    """Jaccard coefficient between word sets of two strings."""
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def name_matches(a: str, b: str) -> tuple[bool, str]:
    """
    Check if two team names refer to the same school.
    Returns (matched, confidence) where confidence is 'exact' or 'fuzzy'.
    """
    if not a or not b:
        return False, ''
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return True, 'exact'
    if na in nb or nb in na:
        return True, 'exact'
    if token_overlap(a, b) >= 0.5:
        return True, 'fuzzy'
    return False, ''


def collect_ncaa_names(season: str, division: int) -> set[str]:
    """Gather unique team names from ncaa.com game ID list and info files."""
    names: set[str] = set()

    ncaa_dir = get_season_ncaa_dir(season, division)

    # From game_ids_ncaa.json
    ids_file = ncaa_dir / "game_ids_ncaa.json"
    if ids_file.exists():
        with open(ids_file, "r") as f:
            for g in json.load(f):
                for key in ("homeTeam", "awayTeam"):
                    v = g.get(key, "").strip()
                    if v:
                        names.add(v)

    # From fetched info files
    for info_file in ncaa_dir.glob("game_*_info.json"):
        try:
            with open(info_file, "r") as f:
                data = json.load(f)
            for key in ("homeTeam", "awayTeam"):
                v = data.get(key, "").strip()
                if v:
                    names.add(v)
        except Exception:
            pass

    return names


def load_lookup_teams(conn) -> list[dict]:
    """Load all teams from lookup_teams."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, short_name, mascot, slug FROM public.lookup_teams ORDER BY name")
        return [dict(row) for row in cur.fetchall()]


def infer_mascot_from_name(full_name: str) -> tuple[str, str]:
    """
    Programmatically split a full team name like "Cornell Big Red" into
    short_name="Cornell" and mascot="Big Red".

    Assumes mascot words are at the end and are not school-indicator words.
    """
    words = full_name.split()
    if len(words) <= 1:
        return full_name, ""

    # Walk backwards from end; collect mascot words until we hit a school word
    mascot_words: list[str] = []
    for i in range(len(words) - 1, -1, -1):
        word = words[i]
        if word.lower() in SCHOOL_WORDS:
            break
        mascot_words.insert(0, word)
        # Stop after collecting up to 4 words that look like a mascot
        if len(mascot_words) >= 4:
            break

    if not mascot_words:
        return full_name, ""

    short = " ".join(words[:len(words) - len(mascot_words)]).strip()
    mascot = " ".join(mascot_words).strip()

    # Sanity check: short_name must be at least 2 chars
    if len(short) < 2:
        return full_name, mascot

    return short, mascot


def build_updates(
    lookup_teams: list[dict],
    ncaa_names: set[str],
    verbose: bool,
) -> list[dict]:
    """
    Build list of {id, short_name, mascot} updates for each lookup_team record.
    """
    updates: list[dict] = []
    matched_ncaa: set[str] = set()

    for team in lookup_teams:
        tid = team["id"]
        full = team["name"]
        existing_short = team.get("short_name") or ""
        existing_mascot = team.get("mascot") or ""

        # Try to find a matching ncaa.com name
        best_ncaa: str | None = None
        best_conf = ''
        for ncaa_name in ncaa_names:
            matched, conf = name_matches(full, ncaa_name)
            if matched:
                # Prefer exact matches; also prefer shorter ncaa names (they're short names)
                if best_ncaa is None or (conf == 'exact' and best_conf != 'exact'):
                    best_ncaa = ncaa_name
                    best_conf = conf

        if best_ncaa:
            matched_ncaa.add(best_ncaa)
            short_name = best_ncaa
            # Mascot = everything in full name after the short name prefix
            norm_full = full
            if full.lower().startswith(short_name.lower()):
                mascot = full[len(short_name):].strip()
            else:
                # Try to infer mascot from full name using short_name as prefix
                _, mascot = infer_mascot_from_name(full)
            if verbose:
                print(f"  [{best_conf}] '{full}' -> short='{short_name}' mascot='{mascot}'")
        else:
            # Fallback: programmatic split
            short_name, mascot = infer_mascot_from_name(full)
            if verbose:
                print(f"  [inferred] '{full}' -> short='{short_name}' mascot='{mascot}'")

        slug = make_slug(short_name) if short_name else ""
        existing_slug = team.get("slug") or ""

        # Only include if there's a change
        if short_name != existing_short or mascot != existing_mascot or slug != existing_slug:
            updates.append({
                "id": tid,
                "name": full,
                "short_name": short_name,
                "mascot": mascot,
                "slug": slug,
            })

    unmatched_ncaa = ncaa_names - matched_ncaa
    if unmatched_ncaa and verbose:
        print(f"\n  {len(unmatched_ncaa)} ncaa.com names not matched to lookup_teams:")
        for n in sorted(unmatched_ncaa)[:20]:
            print(f"    '{n}'")

    return updates


def apply_updates(conn, updates: list[dict]) -> None:
    """Write short_name, mascot, and slug to lookup_teams."""
    with conn.cursor() as cur:
        for u in updates:
            cur.execute(
                "UPDATE public.lookup_teams SET short_name = %s, mascot = %s, slug = %s WHERE id = %s",
                (u["short_name"], u["mascot"], u["slug"], u["id"]),
            )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Parse team names into short_name and mascot")
    parser.add_argument("--season", default="2026", help="Season to source ncaa.com names from")
    parser.add_argument("--division", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print(f"Collecting ncaa.com team names from {args.season} D{args.division}...")
    ncaa_names = collect_ncaa_names(args.season, args.division)
    print(f"  {len(ncaa_names)} unique ncaa.com names")

    print("Loading lookup_teams from database...")
    conn = get_connection()
    lookup_teams = load_lookup_teams(conn)
    print(f"  {len(lookup_teams)} teams")

    print("Building updates...")
    updates = build_updates(lookup_teams, ncaa_names, args.verbose or args.dry_run)
    print(f"  {len(updates)} teams need changes")

    if not updates:
        print("Nothing to update.")
        conn.close()
        return

    if args.dry_run:
        print("\nDry run — proposed changes:")
        for u in updates:
            print(f"  {u['name']} -> short='{u['short_name']}' mascot='{u['mascot']}' slug='{u['slug']}'")
        conn.close()
        return

    print(f"Applying {len(updates)} updates...")
    apply_updates(conn, updates)
    print("Done.")
    conn.close()


if __name__ == "__main__":
    main()
