(() => {
	const games = [];
	const trs = document.querySelectorAll('tr[id^="contest_"]');
	const seen = new Set();
	trs.forEach(tr => {
		const gameId = tr.id.replace('contest_', '');
		if (seen.has(gameId)) return;
		seen.add(gameId);
		const teamIds = [];
		tr.querySelectorAll('a[href*="/teams/"]').forEach(a => {
			const m = a.href.match(/\/teams\/(\d+)/);
			if (m && !teamIds.includes(m[1])) teamIds.push(m[1]);
		});
		games.push({ gameID: gameId, teamIDs: teamIds });
	});
	return JSON.stringify(games);
})()
