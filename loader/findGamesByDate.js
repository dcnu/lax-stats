/**
 * NCAA API game finder - fetches lacrosse games within a specified date range
 * Queries the NCAA scoreboard API for each day and extracts game information
 * Saves found games to games_data.json for processing by other scripts
 */

import fetch from 'node-fetch';
import fs from 'fs/promises'; // Added for file system operations
import { config } from '../config.js'; // Import configuration

const API_BASE_URL = 'https://data.ncaa.com/casablanca'; // Changed from localhost:3000

async function fetchScoreboard(year, month, day) { // Added day parameter
  const url = `${API_BASE_URL}/scoreboard/lacrosse-men/d1/${year}/${month}/${day}/scoreboard.json`; // Changed URL structure
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error(`Error fetching scoreboard for ${year}-${month}-${day}: ${response.status} ${response.statusText}`);
      // const errorBody = await response.text(); // Body might not always be text or useful
      // console.error('Error body:', errorBody);
      return null;
    }
    // Check for empty response body before parsing JSON
    const text = await response.text();
    if (!text) {
      // console.log(`Empty response body for ${year}-${month}-${day}. Assuming no games.`);
      return { games: [] }; // Return a structure that indicates no games
    }
    return JSON.parse(text);
  } catch (error) {
    console.error(`Network or parsing error fetching scoreboard for ${year}-${month}-${day}:`, error);
    return null;
  }
}

function extractGameId(gameUrl) {
  if (!gameUrl) return null;
  const match = gameUrl.match(/\/game\/(\d+)/); // Corrected regex
  return match ? match[1] : null;
}

async function findGamesInDateRange(startDateStr, endDateStr) {
  const startDateObj = new Date(startDateStr + 'T00:00:00Z'); // Use UTC for date operations
  const endDateObj = new Date(endDateStr + 'T00:00:00Z');
  const gamesInRange = [];

  console.log(`Fetching games between ${startDateStr} and ${endDateStr}`);

  let currentDate = new Date(startDateObj);

  while (currentDate <= endDateObj) {
    const year = currentDate.getUTCFullYear();
    const monthPadded = String(currentDate.getUTCMonth() + 1).padStart(2, '0');
    const dayPadded = String(currentDate.getUTCDate()).padStart(2, '0');

    console.log(`Fetching scoreboard for ${year}-${monthPadded}-${dayPadded}...`);
    const scoreboardData = await fetchScoreboard(year, monthPadded, dayPadded);

    if (scoreboardData) {
      let gamesArray = [];
      // Try to find the games array in a few common structures from NCAA raw data
      if (Array.isArray(scoreboardData)) { // Direct array of games
        gamesArray = scoreboardData;
      } else if (scoreboardData.games && Array.isArray(scoreboardData.games)) { // e.g., { games: [...] }
        gamesArray = scoreboardData.games;
      } else if (scoreboardData.scoreboard && Array.isArray(scoreboardData.scoreboard) && scoreboardData.scoreboard.length > 0 && scoreboardData.scoreboard[0].games && Array.isArray(scoreboardData.scoreboard[0].games)) {
        // e.g., { scoreboard: [ { date: "...", games: [...] } ] }
        gamesArray = scoreboardData.scoreboard[0].games;
      }

      if (gamesArray.length > 0) {
        for (const item of gamesArray) { // Changed variable from game to item
          if (item && item.game) { // Ensure item and its nested .game property exist
            const gameDetails = item.game; // This is the actual game data object
            const gameId = extractGameId(gameDetails.url);
            if (gameId) {
              gamesInRange.push({
                date: `${year}-${monthPadded}-${dayPadded}`,
                gameId: gameId,
                // Prioritize .names.seo for team names based on observed data
                homeTeam: gameDetails.home?.names?.seo || gameDetails.home?.nameRaw || gameDetails.home?.nameDisplay || gameDetails.home?.name || gameDetails.home?.school || "Unknown Home",
                awayTeam: gameDetails.away?.names?.seo || gameDetails.away?.nameRaw || gameDetails.away?.nameDisplay || gameDetails.away?.name || gameDetails.away?.school || "Unknown Away",
                url: gameDetails.url
              });
            }
          } else {
            console.warn(`Item in gamesArray missing 'game' property for ${year}-${monthPadded}-${dayPadded}:`, item);
          }
        }
      } else {
        // If gamesArray is empty, it means none of the expected structures were found, or the API returned an empty list for the day.
        console.log(`No games array found or games list empty in scoreboardData for ${year}-${monthPadded}-${dayPadded}.`);
      }
    }
    // else: fetchScoreboard returned null, error already logged

    currentDate.setUTCDate(currentDate.getUTCDate() + 1); // Move to the next day
  }

  return gamesInRange;
}

async function main() {
  const startDate = process.env.GAME_START_DATE || config.gameStartDate;
  const endDate = process.env.GAME_END_DATE || config.gameEndDate;
  // const startDate = '2024-02-01'; // Example for testing a past season
  // const endDate = '2024-02-03';   // Example for testing a past season

  const games = await findGamesInDateRange(startDate, endDate);

  if (games.length > 0) {
    console.log(`\\nFound ${games.length} games between ${startDate} and ${endDate}:`);
    games.forEach(game => {
      console.log(`Date: ${game.date}, Game ID: ${game.gameId}, Home: ${game.homeTeam}, Away: ${game.awayTeam}, URL: ${game.url}`);
    });

    // Save the games data to a JSON file
    // Handle being run from either project root or loader directory
    const outputFilePath = process.cwd().endsWith('loader') ? 'games_data.json' : 'loader/games_data.json';
    try {
      const jsonContent = JSON.stringify(games, null, 2); // Pretty print JSON
      await fs.writeFile(outputFilePath, jsonContent);
      console.log(`\\nSuccessfully saved ${games.length} games to ${outputFilePath}`);
    } catch (error) {
      console.error(`\\nError saving games data to ${outputFilePath}:`, error);
    }

    // Example: Test loading the first game found (if any)
    // if (games.length > 0 && typeof loadGame === 'function') { // Check if loadGame is available (e.g. if this script is run with it)
    //   console.log(\`\\\\nTesting loadGame with the first game: ${games[0].gameId}\`);
    //   await loadGame(games[0].gameId, true);
    // }\n
  } else {
    console.log(`No games found in the specified date range: ${startDate} to ${endDate}.`);
  }
}

// To make this script runnable with node-fetch using ES modules,
// ensure your package.json in the 'loader' directory has "type": "module"
// or use a .mjs extension for this file if "type": "module" is not set globally for the project.

main().catch(console.error); 