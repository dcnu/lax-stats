(() => {
	const result = {
		ncaaGameId: null,
		awayTeam: '',
		homeTeam: '',
		awayScore: null,
		homeScore: null,
		location: '',
		gameDate: '',
		activeTeam: '',
		players: [],
		goalies: [],
	};

	const m = window.location.pathname.match(/\/game\/(\d+)/);
	result.ncaaGameId = m ? m[1] : null;

	const teamNames = document.querySelectorAll('.team-name-long');
	if (teamNames.length >= 2) {
		result.awayTeam = teamNames[0].textContent.trim();
		result.homeTeam = teamNames[1].textContent.trim();
	}

	const awayScoreEl = document.querySelector('span.score.away, div.score.away');
	const homeScoreEl = document.querySelector('span.score.home, div.score.home');
	if (awayScoreEl) result.awayScore = parseInt(awayScoreEl.textContent.trim(), 10) || null;
	if (homeScoreEl) result.homeScore = parseInt(homeScoreEl.textContent.trim(), 10) || null;

	const venueEl = document.querySelector('.venue');
	if (venueEl) {
		const raw = venueEl.textContent.replace(/\n+/g, ' ').trim();
		const dashIdx = raw.indexOf(' - ');
		result.gameDate = dashIdx > 0 ? raw.substring(0, dashIdx).trim() : '';
		result.location = dashIdx > 0 ? raw.substring(dashIdx + 3).trim() : raw;
	}

	const activeTab = document.querySelector('.boxscore-team-selector-team.active');
	result.activeTeam = activeTab ? activeTab.textContent.trim() : '';

	const statsTable = Array.from(document.querySelectorAll('table')).find(t => {
		const h = Array.from(t.querySelectorAll('thead th')).map(th => th.textContent.trim());
		return h.includes('G') && h.includes('A');
	});
	if (statsTable) {
		const headers = Array.from(statsTable.querySelectorAll('thead th')).map(th => th.textContent.trim());
		result.players = Array.from(statsTable.querySelectorAll('tbody tr'))
			.filter(row => !row.classList.contains('total-row'))
			.map(row => {
				const cells = Array.from(row.querySelectorAll('td'));
				const player = {};
				headers.forEach((h, i) => { if (h && cells[i]) player[h] = cells[i].textContent.trim(); });
				return Object.keys(player).length > 1 ? player : null;
			})
			.filter(Boolean);
	}

	const goalieTable = Array.from(document.querySelectorAll('table')).find(t => {
		const h = Array.from(t.querySelectorAll('thead th')).map(th => th.textContent.trim());
		return h.includes('SAVES') || h.includes('Goalies');
	});
	if (goalieTable) {
		const headers = Array.from(goalieTable.querySelectorAll('thead th')).map(th => th.textContent.trim());
		result.goalies = Array.from(goalieTable.querySelectorAll('tbody tr'))
			.filter(row => !row.classList.contains('total-row'))
			.map(row => {
				const cells = Array.from(row.querySelectorAll('td'));
				const g = {};
				headers.forEach((h, i) => { if (h && cells[i]) g[h] = cells[i].textContent.trim(); });
				return Object.keys(g).length > 1 ? g : null;
			})
			.filter(Boolean);
	}

	if (!statsTable && !goalieTable) {
		return JSON.stringify({ error: 'No stat tables found. Inspect DOM to verify selectors.' });
	}

	return JSON.stringify(result);
})()
