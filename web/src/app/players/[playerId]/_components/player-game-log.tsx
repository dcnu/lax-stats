"use client";

import type { PlayerGameStats } from "@/lib/types";
import type { ColumnConfig } from "@/components/filterable-table";
import { formatGameDate } from "@/lib/format";
import { TeamLink, GameLink } from "@/components/entity-link";
import { FilterableTable } from "@/components/filterable-table";

type GameLogEntry = PlayerGameStats & {
	game_date: string;
	opponent_name: string;
};

export function PlayerGameLog({ games }: { games: GameLogEntry[] }) {
	const columns: ColumnConfig[] = [
		{
			key: "game_date",
			label: "Date",
			renderCell: (value, row) => (
				<GameLink gameId={row.game_id as string}>
					{formatGameDate(value as string)}
				</GameLink>
			),
		},
		{
			key: "opponent_name",
			label: "Opponent",
			renderCell: (value, row) => (
				<TeamLink teamId={row.opponent_id as string}>
					{value as string}
				</TeamLink>
			),
		},
		{ key: "goals", label: "G" },
		{ key: "assists", label: "A" },
		{ key: "points", label: "Pts" },
		{ key: "shots", label: "Shots" },
		{ key: "shots_on_goal", label: "SOG" },
		{ key: "ground_balls", label: "GB" },
		{ key: "turnovers", label: "TO" },
		{ key: "caused_turnovers", label: "CT" },
	];

	return (
		<div className="space-y-2">
			<h2 className="text-lg font-semibold">Game Log</h2>
			<FilterableTable
				data={games as unknown as Record<string, unknown>[]}
				columns={columns}
				defaultSort={{ key: "game_date", desc: true }}
				pageSize={20}
			/>
		</div>
	);
}
