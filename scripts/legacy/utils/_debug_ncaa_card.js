(() => {
	const xhr = new XMLHttpRequest();
	xhr.open('POST', 'https://sdataprod.ncaa.com/', false);
	xhr.setRequestHeader('Content-Type', 'application/json');
	xhr.setRequestHeader('Origin', 'https://www.ncaa.com');
	xhr.send(JSON.stringify({
		extensions: {
			persistedQuery: {
				version: 1,
				sha256Hash: '7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c'
			}
		},
		variables: {
			sportCode: 'MLA',
			division: 'd1',
			startDate: '2026-02-07',
			endDate: '2026-02-07'
		}
	}));
	return JSON.stringify({status: xhr.status, body: xhr.responseText.slice(0, 1000)});
})()
