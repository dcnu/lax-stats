(() => {
	const games = [];
	const pods = document.querySelectorAll('div.gamePod');

	if (pods.length === 0) {
		return JSON.stringify({ error: 'No div.gamePod elements found' });
	}

	pods.forEach(pod => {
		const linkEl = pod.querySelector('a.gamePod-link');
		if (!linkEl) return;
		const href = linkEl.getAttribute('href') || '';
		const m = href.match(/\/game\/(\d+)/);
		if (!m) return;
		const ncaaGameId = m[1];

		const teamEls = pod.querySelectorAll('ul.gamePod-game-teams li');
		if (teamEls.length < 2) return;

		const awayLi = teamEls[0];
		const homeLi = teamEls[teamEls.length - 1];

		const awayNameEl = awayLi.querySelector('span.gamePod-game-team-name:not(.short)');
		const homeNameEl = homeLi.querySelector('span.gamePod-game-team-name:not(.short)');
		const awayScoreEl = awayLi.querySelector('span.gamePod-game-team-score');
		const homeScoreEl = homeLi.querySelector('span.gamePod-game-team-score');

		const awayTeam = awayNameEl ? awayNameEl.textContent.trim() : '';
		const homeTeam = homeNameEl ? homeNameEl.textContent.trim() : '';
		const awayScore = awayScoreEl ? parseInt(awayScoreEl.textContent.trim(), 10) : null;
		const homeScore = homeScoreEl ? parseInt(homeScoreEl.textContent.trim(), 10) : null;

		const statusEl = pod.querySelector('div.gamePod-status');
		const statusText = (statusEl ? statusEl.textContent.trim() : '').toLowerCase();
		let status = 'scheduled';
		if (/\bfinal\b/.test(statusText)) status = 'final';
		else if (/\blive\b/.test(statusText) || /\bhalftime\b/.test(statusText)) status = 'live';
		else if (/\bpostponed\b/.test(statusText)) status = 'postponed';
		else if (/\bcanceled\b|\bcancelled\b/.test(statusText)) status = 'canceled';

		games.push({ ncaaGameId, gameUrl: href, homeTeam, awayTeam, homeScore, awayScore, status });
	});

	return JSON.stringify(games);
})()
