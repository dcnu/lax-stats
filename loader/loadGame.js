/**
 * Individual game data loader for lacrosse statistics
 * Fetches game data from NCAA API (boxscore, play-by-play) for a specific game
 * Parses and structures the data, then saves to Supabase database
 * Handles teams, games, players, and player statistics data
 */

// loadGame.js
import fetch from 'node-fetch';
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';

// Load environment variables from .env.local in parent directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const envPath = join(__dirname, '..', '.env.local');

dotenv.config({ path: envPath });

// Load games data to get correct dates and game info
const gamesDataPath = join(__dirname, 'games_data.json');
let gamesData = null;
try {
	const gamesDataRaw = readFileSync(gamesDataPath, 'utf8');
	gamesData = JSON.parse(gamesDataRaw);
} catch (error) {
	console.warn('Warning: Could not load games_data.json for date lookup:', error.message);
}

// Environment variables loaded successfully

const API_BASE_URL = 'https://data.ncaa.com/casablanca';

// Initialize Supabase client only when needed
let supabase = null;

function getSupabaseClient() {
	if (!supabase) {
		const SUPABASE_URL = process.env.SUPABASE_URL;
		const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY;
		
		if (!SUPABASE_URL || !SUPABASE_KEY) {
			throw new Error('Supabase environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY) are required for saving data');
		}
		
		supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
	}
	return supabase;
}

// Function to normalize names to uppercase (addressing case sensitivity issue)
function normalizeName(name) {
	return name ? name.trim().toUpperCase() : '';
}

// Get correct game date from games_data.json
function getGameDate(gameId) {
	if (!gamesData || !gamesData.games) {
		console.warn(`Warning: No games data available for date lookup for game ${gameId}`);
		return new Date().toISOString().split('T')[0]; // Fallback to today
	}
	
	const gameInfo = gamesData.games.find(g => g.gameId === gameId);
	if (gameInfo && gameInfo.date) {
		console.log(`✅ Found correct date for game ${gameId}: ${gameInfo.date}`);
		return gameInfo.date;
	}
	
	console.warn(`Warning: No date found in games_data.json for game ${gameId}, using fallback`);
	return new Date().toISOString().split('T')[0];
}

// Upsert teams
async function upsertTeams(teams) {
	const client = getSupabaseClient();
	
	const { data, error } = await client
		.from('teams')
		.upsert(teams, { onConflict: 'id' })
		.select();
	
	if (error) {
		console.error('❌ FAILED to upsert teams:', error.message);
		return false;
	}
	console.log(`✅ Successfully upserted ${teams.length} teams`);
	return true;
}

// Upsert game
async function upsertGame(gameData) {
	const client = getSupabaseClient();
	
	const { data, error } = await client
		.from('games')
		.upsert(gameData, { onConflict: 'id' })
		.select()
		.single();
	
	if (error) {
		console.error('❌ FAILED to upsert game:', error.message);
		return null;
	}
	console.log(`✅ Successfully upserted game: ${gameData.home_team_id} vs ${gameData.away_team_id}`);
	return data;
}

// Upsert players
async function upsertPlayers(players) {
	const client = getSupabaseClient();
	
	// Use normalized names for unique constraint
	const { data, error } = await client
		.from('players')
		.upsert(players, { onConflict: 'normalized_name,team_id' })
		.select();
	
	if (error) {
		console.error('❌ FAILED to upsert players:', error.message);
		return [];
	}
	console.log(`✅ Successfully upserted ${players.length} players`);
	return data;
}

// Insert player game stats
async function insertPlayerGameStats(playerStats) {
	const client = getSupabaseClient();
	
	const { data, error } = await client
		.from('player_game_stats')
		.insert(playerStats)
		.select();
	
	if (error) {
		console.error('❌ FAILED to insert player game stats:', error.message);
		return false;
	}
	console.log(`✅ Successfully inserted ${playerStats.length} player game stats`);
	return true;
}

// Fetch game data from NCAA API
async function fetchGameData(gameId, endpoint) {
	const url = `${API_BASE_URL}/game/${gameId}/${endpoint}.json`;
	try {
		const response = await fetch(url);
		if (!response.ok) {
			console.error(`Error fetching ${endpoint} for game ${gameId}: ${response.status} ${response.statusText}`);
			return null;
		}
		const text = await response.text();
		if (!text) {
			console.log(`Empty response for game ${gameId} ${endpoint}`);
			return null;
		}
		return JSON.parse(text);
	} catch (error) {
		console.error(`Network or parsing error fetching ${endpoint} for game ${gameId}:`, error);
		return null;
	}
}

// Load a game by ID
export async function loadGame(gameId, dryRun = true) {
	console.log(`Loading game ${gameId}...`);
	
	// Fetch only boxscore for now (team-stats endpoint has access issues)
	const boxscore = await fetchGameData(gameId, 'boxscore');

	if (!boxscore) {
		console.error(`Failed to fetch boxscore data for game ${gameId}`);
		return false;
	}

	// Extract teams data from meta.teams (not main teams array)
	const teams = [];
	const teamsData = {};
	
	if (boxscore.meta?.teams && Array.isArray(boxscore.meta.teams)) {
		for (const team of boxscore.meta.teams) {
			const teamName = team.shortName || team.nickName || `Team ${team.id}`;
			const teamRecord = {
				id: team.id.toString().toUpperCase(), // Normalize team ID to uppercase
				name: teamName,
				normalized_name: normalizeName(teamName), // Add normalized name
				conference: null, // Not available in boxscore
				logo_url: null // Not available in boxscore
			};
			teams.push(teamRecord);
			teamsData[team.id] = teamRecord;
		}
	}

	// Extract game data - use NCAA game ID and correct date
	const gameData = {
		id: gameId, // Use NCAA game ID as primary key
		date: getGameDate(gameId), // Use correct date from games_data.json
		season: boxscore.meta?.season || '2025',
		home_team_id: boxscore.meta?.teams?.find(t => t.homeTeam === "true")?.id?.toString().toUpperCase(),
		away_team_id: boxscore.meta?.teams?.find(t => t.homeTeam === "false")?.id?.toString().toUpperCase(),
		home_score: boxscore.teams?.find(t => t.teamId.toString() === boxscore.meta?.teams?.find(mt => mt.homeTeam === "true")?.id?.toString())?.score || 0,
		away_score: boxscore.teams?.find(t => t.teamId.toString() === boxscore.meta?.teams?.find(mt => mt.homeTeam === "false")?.id?.toString())?.score || 0,
		venue: boxscore.meta?.venue || null,
		neutral_site: false
	};

	// Extract players data
	const players = [];
	const playersMap = {};
	
	if (boxscore.teams && Array.isArray(boxscore.teams)) {
		for (const team of boxscore.teams) {
			if (team.playerStats && Array.isArray(team.playerStats)) {
				for (const player of team.playerStats) {
					const playerName = `${player.firstName || ''} ${player.lastName || ''}`.trim();
					const playerRecord = {
						team_id: team.teamId.toString().toUpperCase(), // Normalize team ID
						name: playerName,
						normalized_name: normalizeName(playerName), // Add normalized name
						position: player.position === 'NULL' ? null : player.position,
						class_year: null, // Not available in boxscore
						photo_url: null
					};
					players.push(playerRecord);
					// Create a key to map player stats later - use normalized name
					playersMap[`${playerRecord.normalized_name}-${team.teamId}`] = playerRecord;
				}
			}
		}
	}

	if (dryRun) {
		console.log(`✅ DRY RUN — Parsed data for game ${gameId}:`);
		console.log(`  - ${teams.length} teams`);
		console.log(`  - 1 game`);
		console.log(`  - ${players.length} players`);
		console.log("Sample team data:", teams.slice(0, 2));
		console.log("Game data:", gameData);
		console.log("Sample player data:", players.slice(0, 2));
		return true;
	} else {
		try {
			// Step 1: Upsert teams
			if (teams.length > 0) {
				const teamsSuccess = await upsertTeams(teams);
				if (!teamsSuccess) return false;
			}

			// Step 2: Upsert game
			const savedGame = await upsertGame(gameData);
			if (!savedGame) return false;

			// Step 3: Upsert players  
			let savedPlayers = [];
			if (players.length > 0) {
				savedPlayers = await upsertPlayers(players);
				if (!savedPlayers || savedPlayers.length === 0) return false;
			}

			// Step 4: Create player game stats with proper matching
			const playerGameStats = [];
			
			if (boxscore.teams && Array.isArray(boxscore.teams)) {
				for (let teamIndex = 0; teamIndex < boxscore.teams.length; teamIndex++) {
					const team = boxscore.teams[teamIndex];
					
					if (team.playerStats && Array.isArray(team.playerStats)) {
						for (const playerStat of team.playerStats) {
							const playerName = `${playerStat.firstName || ''} ${playerStat.lastName || ''}`.trim();
							const normalizedPlayerName = normalizeName(playerName);
							
							// Find the corresponding saved player using normalized name
							const savedPlayer = savedPlayers.find(p => 
								p.normalized_name === normalizedPlayerName && p.team_id === team.teamId.toString().toUpperCase()
							);
							
							if (savedPlayer) {
								playerGameStats.push({
									player_id: savedPlayer.id,
									game_id: savedGame.id, // Now using NCAA game ID
									team_id: team.teamId.toString().toUpperCase(),
									opponent_team_id: boxscore.teams[teamIndex === 0 ? 1 : 0]?.teamId?.toString().toUpperCase(),
									game_played: parseInt(playerStat.goals || 0) > 0 || parseInt(playerStat.assists || 0) > 0 || parseInt(playerStat.shots || 0) > 0,
									game_started: false, // Not available in this data structure
									position_played: playerStat.position === 'NULL' ? null : playerStat.position,
									minutes_played: 0, // Not available in boxscore
									goals: parseInt(playerStat.goals || 0),
									assists: parseInt(playerStat.assists || 0),
									shot_attempts: parseInt(playerStat.shots || 0),
									shots_on_goal: parseInt(playerStat.shotsOnGoal || 0),
									ground_balls: parseInt(playerStat.groundBalls || 0),
									caused_turnovers: 0, // Not in basic boxscore
									turnovers: 0, // Not in basic boxscore
									saves: 0, // Not in basic boxscore
									goals_against: 0, // Not in basic boxscore
									faceoff_wins: 0, // Not in basic boxscore
									faceoff_attempts: 0, // Not in basic boxscore
									penalty_minutes: 0, // Not in basic boxscore
									unassisted_goals: 0, // Not in basic boxscore
									man_up_goals: 0, // Not in basic boxscore
									man_down_goals: 0, // Not in basic boxscore
									overtime_goals: 0 // Not in basic boxscore
								});
							} else {
								console.warn(`⚠️ Could not find saved player for: ${normalizedPlayerName} on team ${team.teamId}`);
							}
						}
					}
				}
			}

			// Step 5: Insert player game stats
			let statsSuccess = true;
			if (playerGameStats.length > 0) {
				statsSuccess = await insertPlayerGameStats(playerGameStats);
			}

			if (statsSuccess) {
				console.log(`✔️ Successfully loaded game ${gameId}:`);
				console.log(`   - ${teams.length} teams`);
				console.log(`   - 1 game`);
				console.log(`   - ${savedPlayers.length} players`);
				console.log(`   - ${playerGameStats.length} player game stats`);
			} else {
				console.log(`⚠️ Partially loaded game ${gameId} - player stats save failed`);
			}
			
			return statsSuccess;
			
		} catch (error) {
			console.error(`❌ Error loading game ${gameId}:`, error);
			return false;
		}
	}
}
