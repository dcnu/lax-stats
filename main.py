"""
Main script to batch process NCAA lacrosse games.
Reads game IDs from data/{season}/raw/game_ids.json and fetches game data and play-by-play.

Usage:
    python3 main.py --season 2025
    python3 main.py --season 2025 --config config.json
"""

import json
import sys
import argparse
import time
import subprocess
import random
import pytz
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from utils.path_helpers import get_season_raw_dir, get_season_games_dir, get_game_file_path

# Set up logging with outputs/logs directory
log_dir = Path("outputs/logs")
log_dir.mkdir(parents=True, exist_ok=True)

# Create timestamped log file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"lacrosse_scraper_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global rate limiting state
class RateLimiter:
    def __init__(self, config):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0
        self.daily_count = 0
        self.lock = threading.Lock()
        self.minute_requests = []
        
    def wait_if_needed(self):
        """Apply rate limiting with jitter and business hours consideration."""
        with self.lock:
            now = time.time()
            
            # Check daily limit
            if self.daily_count >= self.config["rate_limiting"]["daily_limit"]:
                logger.warning("Daily request limit reached. Stopping.")
                return False
            
            # Check requests per minute
            self.minute_requests = [t for t in self.minute_requests if now - t < 60]
            if len(self.minute_requests) >= self.config["rate_limiting"]["requests_per_minute"]:
                wait_time = 61 - (now - self.minute_requests[0])
                logger.info(f"Rate limit: waiting {wait_time:.1f}s (requests per minute)")
                time.sleep(wait_time)
            
            # Calculate base delay with jitter
            base_delay = self.config["rate_limiting"]["base_delay"]
            jitter_range = self.config["rate_limiting"]["random_jitter"]
            jitter = random.uniform(jitter_range[0], jitter_range[1])
            delay = base_delay + jitter
            
            # Business hours slowdown
            if self.config["rate_limiting"]["business_hours_slowdown"]:
                if self.is_business_hours():
                    multiplier = self.config["rate_limiting"]["business_hours"]["slowdown_multiplier"]
                    delay *= multiplier
                    logger.debug(f"Business hours slowdown applied: {delay:.1f}s")
            
            # Ensure minimum time between requests
            time_since_last = now - self.last_request_time
            if time_since_last < delay:
                wait_time = delay - time_since_last
                logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
                time.sleep(wait_time)
            
            self.last_request_time = time.time()
            self.minute_requests.append(self.last_request_time)
            self.daily_count += 1
            
            return True
    
    def is_business_hours(self):
        """Check if current time is during NCAA business hours (Eastern time)."""
        try:
            tz = pytz.timezone(self.config["rate_limiting"]["business_hours"]["timezone"])
            now = datetime.now(tz)
            start_hour = self.config["rate_limiting"]["business_hours"]["start"]
            end_hour = self.config["rate_limiting"]["business_hours"]["end"]
            
            return start_hour <= now.hour < end_hour
        except:
            return False


def load_config(config_file="config.json"):
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {config_file} not found. Using defaults.")
        return {
            "max_workers": 2,
            "rate_limiting": {
                "base_delay": 1.25,
                "random_jitter": [0.25, 0.75],
                "business_hours_slowdown": False,
                "daily_limit": 2000,
                "requests_per_minute": 30
            },
            "retry_strategy": {
                "max_attempts": 3,
                "base_delay": 5.0,
                "429_backoff_start": 30,
                "max_backoff": 300
            }
        }


def load_game_ids(season_id, division=1):
    """Load game IDs from raw data file for a specific season and division."""
    # Get season and division-specific raw directory
    raw_dir = get_season_raw_dir(season_id, division)

    # Check for first day test file first
    first_day_file = raw_dir / "first_day_games.json"
    game_ids_file = raw_dir / "game_ids.json"

    if first_day_file.exists():
        target_file = first_day_file
        logger.info(f"Using first day games for testing (season {season_id})")
    elif game_ids_file.exists():
        target_file = game_ids_file
    else:
        logger.error(f"Game IDs file not found: {game_ids_file}")
        logger.error(f"Please run get_game_ids.py --season {season_id} first to generate game IDs")
        sys.exit(1)

    try:
        with open(target_file, 'r') as f:
            games = json.load(f)

        game_ids = [game["gameID"] for game in games]
        logger.info(f"Loaded {len(game_ids)} game IDs from {target_file}")
        return game_ids

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error reading game IDs file: {e}")
        sys.exit(1)


def get_exponential_backoff(attempt, base_delay, max_backoff):
    """Calculate exponential backoff delay."""
    delay = base_delay * (2 ** attempt)
    return min(delay, max_backoff)


def handle_http_error(status_code, config, attempt):
    """Handle specific HTTP error codes with appropriate delays."""
    if status_code == 429:  # Too Many Requests
        backoff = config["retry_strategy"]["429_backoff_start"] * (config["retry_strategy"]["429_backoff_multiplier"] ** attempt)
        delay = min(backoff, config["retry_strategy"]["max_backoff"])
        logger.warning(f"Rate limited (429). Backing off for {delay}s")
        return delay
    elif 500 <= status_code < 600:  # Server errors
        delay = get_exponential_backoff(attempt, config["retry_strategy"]["5xx_backoff_start"], config["retry_strategy"]["max_backoff"])
        logger.warning(f"Server error ({status_code}). Backing off for {delay}s")
        return delay
    else:
        return config["retry_strategy"]["base_delay"]


def fetch_game_data(game_id, config, rate_limiter):
    """Fetch game info and player stats for a single game."""
    url = f"https://stats.ncaa.org/contests/{game_id}/individual_stats"
    max_attempts = config["retry_strategy"]["max_attempts"]
    
    for attempt in range(max_attempts):
        # Apply rate limiting
        if not rate_limiter.wait_if_needed():
            return False
        
        try:
            logger.info(f"Fetching game data for game {game_id} (attempt {attempt + 1})")
            
            # Get random user agent
            user_agent = random.choice(config["scraping"]["user_agents"])
            
            result = subprocess.run([
                sys.executable, "scripts/fetch_game_data.py", url
            ], capture_output=True, text=True, timeout=config["scraping"]["timeout_seconds"])
            
            if result.returncode == 0:
                logger.info(f"Successfully fetched game data for game {game_id}")
                return True
            else:
                error_msg = result.stderr.strip()
                logger.warning(f"Failed to fetch game data for game {game_id}: {error_msg}")
                
                # Check for specific HTTP errors in the error message
                if "429" in error_msg:
                    delay = handle_http_error(429, config, attempt)
                    time.sleep(delay)
                elif any(code in error_msg for code in ["500", "501", "502", "503", "504"]):
                    delay = handle_http_error(500, config, attempt)
                    time.sleep(delay)
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout fetching game data for game {game_id}")
        except Exception as e:
            logger.error(f"Error fetching game data for game {game_id}: {e}")
            time.sleep(config["retry_strategy"]["connection_error_delay"])
        
        if attempt < max_attempts - 1:
            delay = get_exponential_backoff(attempt, config["retry_strategy"]["base_delay"], config["retry_strategy"]["max_backoff"])
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    logger.error(f"Failed to fetch game data for game {game_id} after {max_attempts} attempts")
    return False


def fetch_game_plays(game_id, config, rate_limiter):
    """Fetch play-by-play data for a single game."""
    max_attempts = config["retry_strategy"]["max_attempts"]
    
    for attempt in range(max_attempts):
        # Apply rate limiting
        if not rate_limiter.wait_if_needed():
            return False
        
        try:
            logger.info(f"Fetching play-by-play for game {game_id} (attempt {attempt + 1})")
            
            result = subprocess.run([
                sys.executable, "scripts/fetch_game_plays.py", "--test", game_id
            ], capture_output=True, text=True, timeout=config["scraping"]["timeout_seconds"])
            
            if result.returncode == 0:
                logger.info(f"Successfully fetched play-by-play for game {game_id}")
                return True
            else:
                error_msg = result.stderr.strip()
                logger.warning(f"Failed to fetch play-by-play for game {game_id}: {error_msg}")
                
                # Check for specific HTTP errors
                if "429" in error_msg:
                    delay = handle_http_error(429, config, attempt)
                    time.sleep(delay)
                elif any(code in error_msg for code in ["500", "501", "502", "503", "504"]):
                    delay = handle_http_error(500, config, attempt)
                    time.sleep(delay)
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout fetching play-by-play for game {game_id}")
        except Exception as e:
            logger.error(f"Error fetching play-by-play for game {game_id}: {e}")
            time.sleep(config["retry_strategy"]["connection_error_delay"])
        
        if attempt < max_attempts - 1:
            delay = get_exponential_backoff(attempt, config["retry_strategy"]["base_delay"], config["retry_strategy"]["max_backoff"])
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    logger.error(f"Failed to fetch play-by-play for game {game_id} after {max_attempts} attempts")
    return False


def process_game(game_id, config, rate_limiter, season_id, division=1):
    """Process a single game: fetch both game data and play-by-play."""
    logger.info(f"Processing game {game_id}")

    # Note: Files will be saved in season and division-based directories by the fetching scripts
    # The season is determined from the game date, which should match season_id
    # We still check for existing files using season_id and division for efficiency

    games_dir = get_season_games_dir(season_id, division)
    info_file = games_dir / f"game_{game_id}_info.json"
    stats_file = games_dir / f"game_{game_id}_player_stats.json"
    plays_file = games_dir / f"game_{game_id}_plays.json"

    data_success = True
    plays_success = True

    # Fetch game data if not exists
    if not (info_file.exists() and stats_file.exists()):
        data_success = fetch_game_data(game_id, config, rate_limiter)
    else:
        logger.info(f"Game data already exists for game {game_id}, skipping")

    # Fetch play-by-play if not exists
    if not plays_file.exists():
        plays_success = fetch_game_plays(game_id, config, rate_limiter)
    else:
        logger.info(f"Play-by-play already exists for game {game_id}, skipping")

    return {
        "game_id": game_id,
        "data_success": data_success,
        "plays_success": plays_success
    }


def main():
    parser = argparse.ArgumentParser(description="Batch process NCAA lacrosse games")
    parser.add_argument("--season", required=True, help="Season ID (year, e.g., 2025)")
    parser.add_argument("--division", type=int, default=None,
                        choices=[1, 2, 3],
                        help="NCAA division (1, 2, or 3). Default from config.json or 1.")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--max-workers", type=int, help="Override max workers from config")
    parser.add_argument("--sequential", action="store_true", help="Process games sequentially instead of in parallel")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    if args.max_workers:
        config["max_workers"] = args.max_workers

    # Get division from args or config
    division = args.division if args.division is not None else config.get('division', 1)

    # Load game IDs for season and division
    game_ids = load_game_ids(args.season, division)

    if not game_ids:
        logger.error("No game IDs found to process")
        sys.exit(1)

    # Create output directories for season and division
    get_season_games_dir(args.season, division)
    get_season_raw_dir(args.season, division)

    # Initialize rate limiter
    rate_limiter = RateLimiter(config)

    logger.info(f"Starting to process {len(game_ids)} games (Season {args.season}, Division {division})")
    logger.info(f"Rate limiting: {config['rate_limiting']['base_delay']}s base delay, max {config['rate_limiting']['requests_per_minute']} req/min")
    if config["rate_limiting"]["business_hours_slowdown"]:
        logger.info("Business hours slowdown enabled")
    
    results = []
    failed_games = []
    
    if args.sequential:
        # Sequential processing
        for game_id in game_ids:
            result = process_game(game_id, config, rate_limiter, args.season, division)
            results.append(result)

            if not (result["data_success"] and result["plays_success"]):
                failed_games.append(game_id)
    else:
        # Parallel processing with shared rate limiter
        with ThreadPoolExecutor(max_workers=config["max_workers"]) as executor:
            future_to_game = {
                executor.submit(process_game, game_id, config, rate_limiter, args.season, division): game_id
                for game_id in game_ids
            }

            for future in as_completed(future_to_game):
                result = future.result()
                results.append(result)

                if not (result["data_success"] and result["plays_success"]):
                    failed_games.append(result["game_id"])
    
    # Summary
    successful_games = [r for r in results if r["data_success"] and r["plays_success"]]
    
    logger.info(f"Processing complete!")
    logger.info(f"Total games: {len(game_ids)}")
    logger.info(f"Successful: {len(successful_games)}")
    logger.info(f"Failed: {len(failed_games)}")
    logger.info(f"Total requests made: {rate_limiter.daily_count}")
    
    if failed_games:
        logger.warning(f"Failed games: {failed_games}")

        # Save failed games for retry
        raw_dir = get_season_raw_dir(args.season, division)
        failed_file = raw_dir / "failed_games.json"
        with open(failed_file, 'w') as f:
            json.dump(failed_games, f, indent=2)
        logger.info(f"Failed games saved to {failed_file}")
    
    # Check if we hit the daily limit
    if rate_limiter.daily_count >= config["rate_limiting"]["daily_limit"]:
        logger.warning("Daily request limit reached. Consider running again tomorrow.")
    
    return len(failed_games) == 0  # Return True if all successful


if __name__ == "__main__":
    main()