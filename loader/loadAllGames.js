#!/usr/bin/env node

/**
 * Batch game processor for lacrosse statistics
 * Loads games from games_data.json and processes them with rate limiting
 * Supports dry-run mode, test mode, and retry logic for failed games
 * Saves successful/failed results and provides progress tracking
 */

import fs from 'fs/promises';
import { loadGame } from './loadGame.js';

// Rate limiting configuration
const RATE_LIMIT_DELAY = 1000; // 1 second between requests
const BATCH_SIZE = 10; // Process 10 games at a time
const MAX_RETRIES = 3;

// Utility function to sleep
function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}

// Load games data
async function loadGamesData() {
	try {
		// Handle being run from either project root or loader directory
		const gamesDataPath = process.cwd().endsWith('loader') ? 'games_data.json' : 'loader/games_data.json';
		const data = await fs.readFile(gamesDataPath, 'utf8');
		return JSON.parse(data);
	} catch (error) {
		console.error('Error reading games_data.json:', error);
		process.exit(1);
	}
}

// Process a single game with retry logic
async function processGameWithRetry(game, dryRun = true, retryCount = 0) {
	try {
		console.log(`Processing game ${game.gameId}: ${game.awayTeam} @ ${game.homeTeam} (${game.date})`);
		const success = await loadGame(game.gameId, dryRun);
		
		if (!success && retryCount < MAX_RETRIES) {
			console.log(`Retrying game ${game.gameId} (attempt ${retryCount + 1}/${MAX_RETRIES})`);
			await sleep(RATE_LIMIT_DELAY * 2); // Longer delay for retries
			return await processGameWithRetry(game, dryRun, retryCount + 1);
		}
		
		return success;
	} catch (error) {
		console.error(`Error processing game ${game.gameId}:`, error);
		
		if (retryCount < MAX_RETRIES) {
			console.log(`Retrying game ${game.gameId} after error (attempt ${retryCount + 1}/${MAX_RETRIES})`);
			await sleep(RATE_LIMIT_DELAY * 2);
			return await processGameWithRetry(game, dryRun, retryCount + 1);
		}
		
		return false;
	}
}

// Process games in batches
async function processGamesBatch(games, startIndex, batchSize, dryRun = true) {
	const endIndex = Math.min(startIndex + batchSize, games.length);
	const batch = games.slice(startIndex, endIndex);
	
	console.log(`\nProcessing batch ${Math.floor(startIndex / batchSize) + 1}: games ${startIndex + 1}-${endIndex} of ${games.length}`);
	
	const results = {
		successful: 0,
		failed: 0,
		failedGames: []
	};
	
	for (const game of batch) {
		const success = await processGameWithRetry(game, dryRun);
		
		if (success) {
			results.successful++;
		} else {
			results.failed++;
			results.failedGames.push({
				gameId: game.gameId,
				matchup: `${game.awayTeam} @ ${game.homeTeam}`,
				date: game.date
			});
		}
		
		// Rate limiting - wait between each game
		if (batch.indexOf(game) < batch.length - 1) {
			await sleep(RATE_LIMIT_DELAY);
		}
	}
	
	return results;
}

// Main function
async function main() {
	const args = process.argv.slice(2);
	const dryRun = !args.includes('--save');
	const testMode = args.includes('--test');
	const limitGames = args.find(arg => arg.startsWith('--limit='));
	
	console.log('🏑 Lacrosse Game Stats Loader');
	console.log('=====================================');
	
	if (dryRun) {
		console.log('🧪 DRY RUN MODE - No data will be saved to database');
	} else {
		console.log('💾 SAVE MODE - Data will be saved to database');
	}
	
	// Load games data
	const games = await loadGamesData();
	console.log(`📋 Found ${games.length} games to process`);
	
	// Determine how many games to process
	let gamesToProcess = games;
	if (testMode) {
		gamesToProcess = games.slice(0, 3);
		console.log('🧪 TEST MODE - Processing first 3 games only');
	} else if (limitGames) {
		const limit = parseInt(limitGames.split('=')[1]);
		gamesToProcess = games.slice(0, limit);
		console.log(`🎯 LIMITED MODE - Processing first ${limit} games only`);
	}
	
	console.log(`\n🚀 Starting to process ${gamesToProcess.length} games...`);
	console.log(`⏱️  Rate limit: ${RATE_LIMIT_DELAY}ms between requests`);
	console.log(`📦 Batch size: ${BATCH_SIZE} games per batch`);
	
	const startTime = Date.now();
	const totalResults = {
		successful: 0,
		failed: 0,
		failedGames: []
	};
	
	// Process games in batches
	for (let i = 0; i < gamesToProcess.length; i += BATCH_SIZE) {
		const batchResults = await processGamesBatch(gamesToProcess, i, BATCH_SIZE, dryRun);
		
		totalResults.successful += batchResults.successful;
		totalResults.failed += batchResults.failed;
		totalResults.failedGames.push(...batchResults.failedGames);
		
		console.log(`Batch completed: ${batchResults.successful} successful, ${batchResults.failed} failed`);
		
		// Wait between batches
		if (i + BATCH_SIZE < gamesToProcess.length) {
			console.log(`Waiting ${RATE_LIMIT_DELAY}ms before next batch...`);
			await sleep(RATE_LIMIT_DELAY);
		}
	}
	
	// Final results
	const endTime = Date.now();
	const duration = Math.round((endTime - startTime) / 1000);
	
	console.log('\n🏁 Processing Complete!');
	console.log('========================');
	console.log(`✅ Successful: ${totalResults.successful}`);
	console.log(`❌ Failed: ${totalResults.failed}`);
	console.log(`⏰ Duration: ${duration} seconds`);
	
	if (totalResults.failedGames.length > 0) {
		console.log('\n❌ Failed Games:');
		totalResults.failedGames.forEach(game => {
			console.log(`  - ${game.gameId}: ${game.matchup} (${game.date})`);
		});
		
		// Save failed games to file for retry
		const failedGamesFile = process.cwd().endsWith('loader') ? 'failed_games.json' : 'loader/failed_games.json';
		await fs.writeFile(failedGamesFile, JSON.stringify(totalResults.failedGames, null, 2));
		console.log(`\n💾 Failed games saved to ${failedGamesFile} for retry`);
	}
	
	console.log('\n📊 Summary:');
	console.log(`• Total games processed: ${gamesToProcess.length}`);
	console.log(`• Success rate: ${Math.round((totalResults.successful / gamesToProcess.length) * 100)}%`);
	
	if (dryRun) {
		console.log('\n💡 To save data to database, run with --save flag');
	}
	
	if (testMode) {
		console.log('\n💡 To process all games, remove --test flag');
	}
}

// Handle errors and exit gracefully
process.on('unhandledRejection', (error) => {
	console.error('Unhandled promise rejection:', error);
	process.exit(1);
});

process.on('SIGINT', () => {
	console.log('\n\n🛑 Process interrupted by user');
	process.exit(0);
});

main().catch(console.error); 