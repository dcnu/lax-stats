"use client";

import { FilterableTable } from "@/components/filterable-table";
import type { ColumnConfig } from "@/components/filterable-table";
import { PlayerLink, TeamLink } from "@/components/entity-link";
import { formatPct } from "@/lib/format";
import type { PlayerSeasonStats } from "@/lib/types";

const columns: ColumnConfig[] = [
	{
		key: "player_name",
		label: "Player",
		renderCell: (value, row) => (
			<PlayerLink playerId={row.player_id as number}>
				{value as string}
			</PlayerLink>
		),
	},
	{
		key: "team_name",
		label: "Team",
		filterable: true,
		renderCell: (value, row) => (
			<TeamLink teamSlug={row.team_slug as string} teamId={row.team_id as string}>
				{value as string}
			</TeamLink>
		),
	},
	{ key: "primary_position", label: "Pos", filterable: true },
	{ key: "games_played", label: "GP", filterable: true, filterType: "min" },
	{ key: "goals", label: "G", filterable: true, filterType: "min" },
	{ key: "assists", label: "A", filterable: true, filterType: "min" },
	{ key: "points", label: "Pts", filterable: true, filterType: "min" },
	{ key: "shots", label: "Shots" },
	{ key: "shots_on_goal", label: "SOG" },
	{ key: "ground_balls", label: "GB", filterable: true, filterType: "min" },
	{ key: "turnovers", label: "TO" },
	{ key: "caused_turnovers", label: "CT" },
	{
		key: "faceoff_wins",
		label: "FO Won",
		visible: false,
	},
	{
		key: "faceoffs_taken",
		label: "FO Taken",
		visible: false,
	},
	{
		key: "faceoff_pct",
		label: "FO%",
		visible: false,
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "shooting_pct",
		label: "Shooting%",
		visible: false,
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "points_per_game",
		label: "PPG",
	},
];

export function PlayersTable({ players }: { players: PlayerSeasonStats[] }) {
	return (
		<FilterableTable
			data={players as unknown as Record<string, unknown>[]}
			columns={columns}
			defaultSort={{ key: "points", desc: true }}
		/>
	);
}
