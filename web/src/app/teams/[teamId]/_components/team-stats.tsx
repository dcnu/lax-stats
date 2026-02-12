"use client";

import type { PlayerSeasonStats } from "@/lib/types";
import { PlayerLink } from "@/components/entity-link";
import { FilterableTable } from "@/components/filterable-table";
import type { ColumnConfig } from "@/components/filterable-table";

export function TeamStats({ stats }: { stats: PlayerSeasonStats[] }) {
	if (stats.length === 0) {
		return <p className="text-muted-foreground">No stats available.</p>;
	}

	const columns: ColumnConfig[] = [
		{
			key: "player_name",
			label: "Player",
			renderCell: (value, row) => (
				<PlayerLink playerId={row.player_id as number}>
					{String(value || "Unknown")}
				</PlayerLink>
			),
		},
		{
			key: "primary_position",
			label: "Pos",
			filterable: true,
		},
		{ key: "games_played", label: "GP" },
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
		<FilterableTable
			data={stats as unknown as Record<string, unknown>[]}
			columns={columns}
			defaultSort={{ key: "points", desc: true }}
		/>
	);
}
