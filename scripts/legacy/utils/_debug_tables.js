(() => {
	var tables = document.querySelectorAll('table.dataTable');
	var r = [];
	for (var i = 0; i < tables.length; i++) {
		var t = tables[i];
		var heading = '';
		var p = t.parentElement;
		while (p && !heading) {
			var prev = p.previousElementSibling;
			if (prev) {
				var text = prev.innerText || '';
				if (text.length > 2) heading = text.substring(0, 80);
			}
			p = p.parentElement;
		}
		var rows = t.querySelectorAll('tbody tr[id^="game_player"]').length;
		r.push({index: i, heading: heading, rows: rows});
	}
	return JSON.stringify(r);
})()
