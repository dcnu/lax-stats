"use client";

import { useMemo } from "react";
import type { Game, PlayerGameStats } from "@/lib/types";

interface StatRow {
	label: string;
	away: number;
	home: number;
}

function ComparisonBar({
	stat,
	awayName,
	homeName,
}: {
	stat: StatRow;
	awayName: string;
	homeName: string;
}) {
	const total = stat.away + stat.home;
	const awayPct = total > 0 ? (stat.away / total) * 100 : 50;
	const homePct = total > 0 ? (stat.home / total) * 100 : 50;

	return (
		<div className="space-y-1">
			<div className="flex items-center justify-between text-sm">
				<span className="font-medium tabular-nums w-10 text-right">{stat.away}</span>
				<span className="text-muted-foreground text-xs">{stat.label}</span>
				<span className="font-medium tabular-nums w-10">{stat.home}</span>
			</div>
			<div className="flex h-2 rounded-full overflow-hidden bg-muted">
				<div
					className="bg-blue-500 transition-all"
					style={{ width: `${awayPct}%` }}
					title={`${awayName}: ${stat.away}`}
				/>
				<div
					className="bg-emerald-500 transition-all"
					style={{ width: `${homePct}%` }}
					title={`${homeName}: ${stat.home}`}
				/>
			</div>
		</div>
	);
}

export function TeamComparison({
	game,
	players,
}: {
	game: Game;
	players: PlayerGameStats[];
}) {
	const stats = useMemo(() => {
		const away = players.filter((p) => p.team_id === game.away_team_id);
		const home = players.filter((p) => p.team_id === game.home_team_id);

		const sum = (arr: PlayerGameStats[], key: keyof PlayerGameStats) =>
			arr.reduce((acc, p) => acc + (Number(p[key]) || 0), 0);

		const rows: StatRow[] = [
			{ label: "Goals", away: game.away_score ?? 0, home: game.home_score ?? 0 },
			{ label: "Shots", away: sum(away, "shots"), home: sum(home, "shots") },
			{ label: "Shots on Goal", away: sum(away, "shots_on_goal"), home: sum(home, "shots_on_goal") },
			{ label: "Ground Balls", away: sum(away, "ground_balls"), home: sum(home, "ground_balls") },
			{ label: "Turnovers", away: sum(away, "turnovers"), home: sum(home, "turnovers") },
			{ label: "Caused Turnovers", away: sum(away, "caused_turnovers"), home: sum(home, "caused_turnovers") },
			{ label: "Faceoffs Won", away: sum(away, "faceoff_wins"), home: sum(home, "faceoff_wins") },
			{ label: "Saves", away: sum(away, "saves"), home: sum(home, "saves") },
		];

		return rows;
	}, [players, game]);

	return (
		<div className="pt-4 max-w-lg mx-auto space-y-4">
			<div className="flex items-center justify-between text-sm font-semibold">
				<span className="flex items-center gap-2">
					<span className="h-3 w-3 rounded-full bg-blue-500" />
					{game.away_team_name}
				</span>
				<span className="flex items-center gap-2">
					{game.home_team_name}
					<span className="h-3 w-3 rounded-full bg-emerald-500" />
				</span>
			</div>
			{stats.map((stat) => (
				<ComparisonBar
					key={stat.label}
					stat={stat}
					awayName={game.away_team_name}
					homeName={game.home_team_name}
				/>
			))}
		</div>
	);
}
