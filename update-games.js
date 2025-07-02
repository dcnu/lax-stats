#!/usr/bin/env node

/**
 * Convenience script to update/fetch lacrosse game data from the project root
 * Fetches all games between configured dates from NCAA API and saves to games_data.json
 * Delegates to loader/findGamesByDate.js for the actual data fetching
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log('Updating lacrosse game data...');
console.log('This will fetch all games between the configured dates and save to loader/games_data.json');

const child = spawn('node', [join(__dirname, 'loader', 'findGamesByDate.js')], {
	stdio: 'inherit',
	cwd: __dirname
});

child.on('close', (code) => {
	if (code === 0) {
		console.log('\n✅ Game data update completed successfully');
	} else {
		console.log(`\n❌ Game data update failed with code ${code}`);
	}
}); 