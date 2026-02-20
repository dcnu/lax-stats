(() => {
	const results = [];
	const tables = document.querySelectorAll('table.dataTable');

	tables.forEach((table, tableIndex) => {
		const thead = table.querySelector('thead');
		if (!thead) return;

		const ths = thead.querySelectorAll('th');
		const fields = [];
		for (let i = 3; i < ths.length; i++) {
			fields.push(
				ths[i].innerText.replace(/\n/g, ' ').trim()
					.replace('FO Won', 'FO_Won')
					.replace('FOs Taken', 'FOs_Taken')
			);
		}

		const tbody = table.querySelector('tbody');
		if (!tbody) return;

		const rows = tbody.querySelectorAll('tr[id^="game_player"]');
		rows.forEach(row => {
			const cells = row.querySelectorAll('td');
			if (cells.length < 3) return;

			const jersey = cells[0].textContent.trim();
			const link = cells[1].querySelector('a');
			if (!link || !link.getAttribute('href')) return;

			const href = link.getAttribute('href');
			const playerIdStr = href.split('/').pop();
			const playerId = parseInt(playerIdStr, 10);
			if (isNaN(playerId)) return;

			const name = link.textContent.trim();
			const position = cells[2].textContent.trim();

			const stats = {};
			for (let i = 0; i < fields.length; i++) {
				stats[fields[i]] = cells[3 + i] ? cells[3 + i].textContent.trim() : '0';
			}
			stats.jersey = jersey;
			stats.position = position;
			stats.playerId = playerId;
			stats.name = name;
			stats.tableIndex = tableIndex;

			results.push(stats);
		});
	});

	return JSON.stringify(results);
})()
