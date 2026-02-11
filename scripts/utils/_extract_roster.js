(() => {
	const table = document.querySelector('table#rosters_form_players_16980_data_table');
	if (!table) return JSON.stringify({error: 'Roster table not found'});

	const tbody = table.querySelector('tbody');
	if (!tbody) return JSON.stringify({error: 'No tbody in roster table'});

	const rows = tbody.querySelectorAll('tr');
	const players = [];

	rows.forEach(row => {
		const cells = row.querySelectorAll('td');
		if (cells.length < 8) return;

		const nameCell = cells[3];
		const link = nameCell.querySelector('a');
		if (!link || !link.getAttribute('href')) return;

		const href = link.getAttribute('href');
		const playerIdStr = href.split('/').pop();
		const playerId = parseInt(playerIdStr, 10);
		if (isNaN(playerId)) return;

		players.push({
			playerId: playerId,
			name: link.textContent.trim(),
			jersey: cells[2].textContent.trim(),
			classYear: cells[4].textContent.trim(),
			position: cells[5].textContent.trim(),
			hometown: cells[6].textContent.trim(),
			highSchool: cells[7].textContent.trim(),
			gamesPlayed: parseInt(cells[0].textContent.trim(), 10) || 0,
			gamesStarted: parseInt(cells[1].textContent.trim(), 10) || 0
		});
	});

	return JSON.stringify(players);
})()
