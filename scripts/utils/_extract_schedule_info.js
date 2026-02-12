(() => {
	// Extract schedule info from the NCAA /contests/{id} main page.
	// This page is available even for unplayed (scheduled) games, unlike
	// /contests/{id}/individual_stats which requires box score data.
	//
	// The main contest page has a table with team links containing /teams/{id}
	// and game metadata (date, location).

	// Find all team links on the page
	const teamLinks = document.querySelectorAll('a[href*="/teams/"]');
	if (teamLinks.length < 2) {
		return JSON.stringify({error: 'Found ' + teamLinks.length + ' team links, expected >= 2'});
	}

	// Extract unique teams from links
	const teams = [];
	const seenIds = new Set();
	teamLinks.forEach(a => {
		const m = a.href.match(/\/teams\/(\d+)/);
		if (m && !seenIds.has(m[1])) {
			seenIds.add(m[1]);
			teams.push({id: m[1], name: a.textContent.trim()});
		}
	});

	if (teams.length < 2) {
		return JSON.stringify({error: 'Found ' + teams.length + ' unique teams, expected >= 2'});
	}

	// The first team is typically the away team, second is home
	// This matches NCAA convention on the main contest page
	const awayTeam = teams[0];
	const homeTeam = teams[1];

	// Extract game date — look for date patterns in the page text
	let gameDate = '';
	const datePattern = /(\d{2}\/\d{2}\/\d{4})/;

	// Check common locations: table cells, headers, detail sections
	const allText = document.body.innerText;
	const dateMatch = allText.match(datePattern);
	if (dateMatch) {
		gameDate = dateMatch[1];
	}

	// Extract location — look for text near "Location" or common venue patterns
	let location = '';
	const tds = document.querySelectorAll('td');
	for (let i = 0; i < tds.length; i++) {
		const text = tds[i].textContent.trim();
		// Location cell usually contains parenthetical city/state
		if (text.match(/\([A-Z]{2}\)/) || text.includes('Stadium') || text.includes('Field') || text.includes('Complex')) {
			location = text;
			break;
		}
	}

	// Try to get scores (will be null/NaN for scheduled games)
	let awayScore = null;
	let homeScore = null;
	const scorePattern = /\b(\d{1,3})\s*-\s*(\d{1,3})\b/;
	// Look in table cells near team names for scores
	const tables = document.querySelectorAll('table');
	for (const table of tables) {
		const rows = table.querySelectorAll('tr');
		for (const row of rows) {
			const cells = row.querySelectorAll('td');
			for (const cell of cells) {
				const val = parseInt(cell.textContent.trim(), 10);
				if (!isNaN(val) && val >= 0 && val < 100) {
					// Found a potential score cell
				}
			}
		}
	}

	return JSON.stringify({
		awayTeam: awayTeam.name,
		awayTeamId: awayTeam.id,
		homeTeam: homeTeam.name,
		homeTeamId: homeTeam.id,
		gameDate: gameDate,
		location: location
	});
})()
