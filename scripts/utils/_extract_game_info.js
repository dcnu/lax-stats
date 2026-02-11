(() => {
	const table = document.querySelector('div.table-responsive table');
	if (!table) return JSON.stringify({error: 'No table-responsive table found'});

	const rows = table.querySelectorAll('tr');
	if (rows.length === 0) return JSON.stringify({error: 'No rows found'});

	const cells = rows[0].querySelectorAll('td');
	if (cells.length < 30) return JSON.stringify({error: 'Expected >=30 cells, found ' + cells.length});

	const isOvertime = cells.length > 30;
	const otShift = isOvertime ? cells.length - 30 : 0;

	const awayLink = cells[1].querySelector('a');
	if (!awayLink) return JSON.stringify({error: 'Away team link not found'});
	const awayTeam = awayLink.textContent.trim();
	const awayHref = awayLink.getAttribute('href') || '';
	const awayTeamId = awayHref.split('/').pop();

	const awayScore = parseInt(cells[3].textContent.trim(), 10);

	const homePos = 27 + otShift;
	const homeLink = cells[homePos].querySelector('a');
	if (!homeLink) return JSON.stringify({error: 'Home team link not found'});
	const homeTeam = homeLink.textContent.trim();
	const homeHref = homeLink.getAttribute('href') || '';
	const homeTeamId = homeHref.split('/').pop();

	const homeScore = parseInt(cells[29 + otShift].textContent.trim(), 10);

	const gameDate = cells[23 + otShift].textContent.trim();
	const location = cells[24 + otShift].textContent.trim();
	const attendanceRaw = cells[25 + otShift].textContent.trim()
		.replace('Attendance: ', '').replace(/,/g, '').trim();
	const attendance = /^\d+$/.test(attendanceRaw) ? parseInt(attendanceRaw, 10) : 0;

	return JSON.stringify({
		awayTeam: awayTeam,
		awayTeamId: awayTeamId,
		awayScore: awayScore,
		homeTeam: homeTeam,
		homeTeamId: homeTeamId,
		homeScore: homeScore,
		location: location,
		attendance: attendance,
		gameDate: gameDate,
		isOvertime: isOvertime,
		overtimePeriods: otShift
	});
})()
