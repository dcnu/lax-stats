(() => {
	const results = [];
	const cards = document.querySelectorAll('.card.table-responsive');

	cards.forEach(card => {
		const header = card.querySelector('.card-header');
		let quarterRaw = header ? header.textContent.trim() : 'Unknown';
		let quarter = quarterRaw.toLowerCase();
		if (quarter.includes('1st')) quarter = '1';
		else if (quarter.includes('2nd')) quarter = '2';
		else if (quarter.includes('3rd')) quarter = '3';
		else if (quarter.includes('4th')) quarter = '4';
		else quarter = quarterRaw;

		const rows = card.querySelectorAll('table tbody tr');
		rows.forEach(row => {
			const cells = row.querySelectorAll('td');
			if (cells.length !== 4) return;

			results.push({
				quarter: quarter,
				time: cells[0].textContent.trim(),
				home_event: cells[1].textContent.trim(),
				score: cells[2].textContent.trim(),
				away_event: cells[3].textContent.trim()
			});
		});
	});

	return JSON.stringify(results);
})()
