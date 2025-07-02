#!/usr/bin/env node

/**
 * Convenience script to load lacrosse game statistics from the project root
 * Provides a simple interface with dry-run and save modes for processing game data
 * Delegates to loader/loadAllGames.js for the actual processing
 */

// Convenience script to load game data from the project root
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const args = process.argv.slice(2);

console.log('🏑 Loading lacrosse game stats...');

if (args.includes('--test')) {
	console.log('🧪 TEST MODE: Processing first 3 games only');
} else if (args.includes('--save')) {
	console.log('💾 SAVE MODE: Data will be saved to database');
} else {
	console.log('🧪 DRY RUN MODE: No data will be saved (add --save to save to database)');
}

const child = spawn('node', [join(__dirname, 'loader', 'loadAllGames.js'), ...args], {
	stdio: 'inherit',
	cwd: __dirname
});

child.on('close', (code) => {
	if (code === 0) {
		console.log('\n✅ Game loading completed successfully');
	} else {
		console.log(`\n❌ Game loading failed with code ${code}`);
	}
}); 