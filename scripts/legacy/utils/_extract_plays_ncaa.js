(() => {
	const plays = [];
	let currentPeriod = '1';

	const tables = Array.from(document.querySelectorAll('table'));

	tables.forEach(table => {
		let el = table.previousElementSibling;
		let depth = 0;
		while (el && depth < 5) {
			const text = (el.innerText || el.textContent || '').trim().toLowerCase();
			if (/\b1st\b/.test(text)) { currentPeriod = '1'; break; }
			if (/\b2nd\b/.test(text)) { currentPeriod = '2'; break; }
			if (/\b3rd\b/.test(text)) { currentPeriod = '3'; break; }
			if (/\b4th\b/.test(text)) { currentPeriod = '4'; break; }
			if (/overtime|\bot\b/.test(text)) { currentPeriod = 'OT'; break; }
			el = el.previousElementSibling;
			depth++;
		}

		if (depth >= 5 || !el) {
			const parent = table.parentElement;
			if (parent) {
				const heading = parent.querySelector('h1, h2, h3, h4, h5, [class*="header"], [class*="title"]');
				if (heading) {
					const text = (heading.innerText || heading.textContent || '').trim().toLowerCase();
					if (/\b1st\b/.test(text)) currentPeriod = '1';
					else if (/\b2nd\b/.test(text)) currentPeriod = '2';
					else if (/\b3rd\b/.test(text)) currentPeriod = '3';
					else if (/\b4th\b/.test(text)) currentPeriod = '4';
					else if (/overtime|\bot\b/.test(text)) currentPeriod = 'OT';
				}
			}
		}

		const rows = Array.from(table.querySelectorAll('tbody tr'));
		rows.forEach(row => {
			const cells = Array.from(row.querySelectorAll('td'));
			if (cells.length < 2) return;

			const play = { quarter: currentPeriod, time: '', home_event: '', score: '', away_event: '' };

			if (cells.length >= 4) {
				play.time = cells[0].textContent.trim();
				play.away_event = cells[1].textContent.trim();
				play.score = cells[2].textContent.trim();
				play.home_event = cells[3].textContent.trim();
			} else if (cells.length === 3) {
				play.time = cells[0].textContent.trim();
				play.home_event = cells[1].textContent.trim();
				play.score = cells[2].textContent.trim();
			} else if (cells.length === 2) {
				play.time = cells[0].textContent.trim();
				play.home_event = cells[1].textContent.trim();
			}

			plays.push(play);
		});
	});

	if (plays.length === 0) {
		const playItems = document.querySelectorAll(
			'[class*="play-item"], [class*="playItem"], [class*="play_item"], [data-testid*="play"]'
		);
		playItems.forEach(item => {
			plays.push({ quarter: currentPeriod, time: '', home_event: (item.innerText || item.textContent || '').trim(), score: '', away_event: '' });
		});
	}

	if (plays.length === 0) {
		return JSON.stringify({ error: 'No play-by-play data found. Selectors may need adjustment.' });
	}

	return JSON.stringify(plays);
})()
