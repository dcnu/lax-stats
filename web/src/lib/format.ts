export function formatTime(seconds: number | null | undefined): string {
	if (seconds === null || seconds === undefined) return "-";
	const mins = Math.floor(seconds / 60);
	const secs = seconds % 60;
	return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function formatPct(value: number | string | null | undefined): string {
	if (value === null || value === undefined) return "-";
	const num = typeof value === "string" ? parseFloat(value) : value;
	if (isNaN(num)) return "-";
	return num.toFixed(3);
}

export function formatRecord(wins: number, losses: number): string {
	return `${wins}-${losses}`;
}

export function formatGameDate(date: string | Date): string {
	const d = typeof date === "string" ? new Date(date + "T00:00:00") : date;
	return d.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
}

export function formatGameDateShort(date: string | Date): string {
	const d = typeof date === "string" ? new Date(date + "T00:00:00") : date;
	return d.toLocaleDateString("en-US", {
		month: "numeric",
		day: "numeric",
	});
}
