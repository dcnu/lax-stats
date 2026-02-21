import { formatRecord } from "@/lib/format";

export function TeamHeader({
	teamName,
	wins,
	losses,
}: {
	teamName: string;
	wins: number;
	losses: number;
}) {
	return (
		<div className="mb-6">
			<h1 className="text-2xl font-bold">{teamName}</h1>
			<p className="text-muted-foreground">{formatRecord(wins, losses)}</p>
		</div>
	);
}
