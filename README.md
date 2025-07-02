# Lacrosse Stats

A system for fetching, processing, and storing NCAA lacrosse game statistics from the NCAA API into a PostgreSQL database.

## Overview

This project automates the collection and processing of NCAA Division I men's lacrosse game data. It fetches game information from the NCAA API, processes individual game statistics, and stores the data in a normalized database structure with quality controls.

## Features

- **Automated Game Discovery**: Fetches all lacrosse games within a configurable date range from the NCAA API
- **Batch Processing**: Processes games in batches with configurable rate limiting to respect API limits
- **Data Quality Controls**:
  - Normalizes team and player names to prevent duplicates
  - Uses official NCAA game IDs as primary keys
  - Maintains accurate game dates from source data
- **Robust Error Handling**: Includes retry logic, failed game tracking, and graceful error recovery
- **Multiple Operating Modes**:
  - Dry-run mode for testing without database writes
  - Test mode for processing a limited number of games
  - Full production mode with database persistence
- **Progress Tracking**: Real-time progress reporting with success/failure statistics
- **Database Integration**: Stores data in Supabase with proper schema design and indexes

## Installation

### Prerequisites

- Node.js (v18 or higher)
- Supabase account and project
- Git

### Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd lacrosse-stats
   ```

2. **Install dependencies**

   ```bash
   npm install
   cd loader
   npm install
   cd ..
   ```

3. **Configure Supabase**

   - Create a new Supabase project
   - Set up your database connection (see Configuration section)
   - Run the database migrations (located in `supabase/migrations/`)

4. **Configure date range**
   - Edit `config.js` to set your desired game date range
   - Default range is February 1 - May 31, 2025 (current lacrosse season)

## Configuration

### Date Range Configuration

Edit `config.js` to set the lacrosse season dates:

```javascript
export const config = {
  gameStartDate: "2025-02-01", // Start of season
  gameEndDate: "2025-05-31", // End of season
};
```

### Environment Variables

Create a `.env` file in the `loader/` directory with your Supabase credentials:

```
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Usage

### 1. Update Game List

First, fetch the list of games for your configured date range:

```bash
npm run update-games
```

This will:

- Query the NCAA API for each day in your date range
- Find all lacrosse games and extract game IDs
- Save the results to `loader/games_data.json`

### 2. Load Game Statistics

Process the games and load statistics into your database:

```bash
# Dry run (no database writes) - recommended first
node load-games.js

# Test mode (process first 3 games only)
node load-games.js --test

# Production mode (save to database)
node load-games.js --save

# Limited processing (first N games)
node load-games.js --limit=10 --save
```

### Advanced Usage

**Process games from the loader directory:**

```bash
cd loader
node loadAllGames.js --save
```

**Retry failed games:**
Failed games are automatically saved to `loader/failed_games.json` and can be retried by running the loader again.

## System Architecture

### Core Components

- **`config.js`**: Central configuration for date ranges and settings
- **`update-games.js`**: Convenience script for updating the game list
- **`load-games.js`**: Main entry point for processing games
- **`loader/`**: Core processing module containing:
  - `findGamesByDate.js`: NCAA API integration for game discovery
  - `loadAllGames.js`: Batch processor with rate limiting and error handling
  - `loadGame.js`: Individual game processor
  - `games_data.json`: Cached game list from NCAA API

### Processing Flow

1. **Game Discovery**: Query NCAA API for games in date range
2. **Data Extraction**: Parse game details and extract statistics
3. **Data Processing**: Normalize names, validate data quality
4. **Database Storage**: Upsert games, teams, players, and statistics
5. **Error Handling**: Track failures and provide retry capabilities

### Rate Limiting

The system includes built-in rate limiting to respect NCAA API limits:

- 1-second delay between individual game requests
- Configurable batch sizes (default: 10 games per batch)
- Extended delays for retry attempts
- Graceful handling of API failures

## Database Schema

The system uses a normalized database structure:

- **games**: Game metadata with NCAA IDs as primary keys
- **teams**: Team information with normalized names
- **players**: Player roster with normalized names
- **player_stats**: Individual game statistics
- **Additional tables**: For comprehensive game data tracking

All tables include proper indexes and triggers for data quality enforcement.

## Development

### Project Structure

```
lacrosse-stats/
├── config.js              # Configuration settings
├── load-games.js          # Main loading script
├── update-games.js        # Game list update script
├── loader/                # Core processing module
│   ├── findGamesByDate.js # NCAA API integration
│   ├── loadAllGames.js    # Batch processor
│   ├── loadGame.js        # Individual game processor
│   └── games_data.json    # Cached game data
├── supabase/              # Database configuration
```

### Running Tests

Test mode processes only the first 3 games for development:

```bash
node load-games.js --test
```

### Debugging

Use dry-run mode to test processing without database writes:

```bash
node load-games.js  # Defaults to dry-run mode
```

## API Reference

### NCAA API Integration

The system integrates with the NCAA scoreboard API:

- **Base URL**: `https://data.ncaa.com/casablanca`
- **Endpoint**: `/scoreboard/lacrosse-men/d1/{year}/{month}/{day}/scoreboard.json`
- **Rate Limits**: Self-imposed 1-second delays between requests

### Command Line Options

**load-games.js options:**

- `--save`: Enable database writes (default: dry-run)
- `--test`: Process first 3 games only
- `--limit=N`: Process first N games only

## Troubleshooting

### Common Issues

1. **Schema Cache Issues**: If encountering schema cache problems, restart your Supabase instance
2. **API Rate Limits**: The system includes built-in rate limiting, but extend delays if needed
3. **Failed Games**: Check `loader/failed_games.json` for games that failed processing
4. **Date Format**: Ensure dates in `config.js` use YYYY-MM-DD format

### Getting Help

- Review failed game logs in `loader/failed_games.json`

## License

...

## Contact

For questions or support, please refer to the project documentation or create an issue in the repository.
