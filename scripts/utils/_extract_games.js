(() => {
	const games = [];
	const tables = document.querySelectorAll('table');
	const seen = new Set();

	tables.forEach(table => {
		const contestRows = table.querySelectorAll('tr[id^="contest_"]');
		if (contestRows.length < 2) return;

		const gameId = contestRows[0].id.replace('contest_', '');
		if (seen.has(gameId)) return;
		seen.add(gameId);

		const teamLinks = table.querySelectorAll('a[href*="/teams/"]');
		const teams = [];
		const seenIds = new Set();
		teamLinks.forEach(a => {
			const m = a.href.match(/\/teams\/(\d+)/);
			if (m && !seenIds.has(m[1])) {
				seenIds.add(m[1]);
				const raw = a.textContent.trim();
				const paren = raw.lastIndexOf('(');
				const name = paren > 0 ? raw.substring(0, paren).trim() : raw;
				teams.push({id: m[1], name: name});
			}
		});

		if (teams.length < 2) return;

		const game = {
			gameID: gameId,
			teamIDs: teams.map(t => t.id),
			homeTeamId: teams[0].id,
			homeTeam: teams[0].name,
			awayTeamId: teams[1].id,
			awayTeam: teams[1].name
		};

		const scoreDivs = table.querySelectorAll('div[id^="score_"]');
		if (scoreDivs.length >= 2) {
			const s1 = scoreDivs[0].textContent.trim();
			const s2 = scoreDivs[1].textContent.trim();
			if (s1 && s2) {
				game.homeScore = parseInt(s1, 10);
				game.awayScore = parseInt(s2, 10);
			}
		}

		games.push(game);
	});

	return JSON.stringify(games);
})()
