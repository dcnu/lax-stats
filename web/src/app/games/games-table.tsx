"use client";

import { FilterableTable } from "@/components/filterable-table";
import type { ColumnConfig } from "@/components/filterable-table";
import { TeamLink, GameLink } from "@/components/entity-link";
import { formatGameDate } from "@/lib/format";
import type { Game } from "@/lib/types";

const columns: ColumnConfig[] = [
	{
		key: "game_date",
		label: "Date",
		renderCell: (value) => formatGameDate(value as string),
	},
	{
		key: "away_team_name",
		label: "Away Team",
		filterable: true,
		renderCell: (_, row) => (
			<TeamLink teamId={row.away_team_id as string}>
				{row.away_team_name as string}
			</TeamLink>
		),
	},
	{
		key: "score",
		label: "Score",
		renderCell: (_, row) => (
			<GameLink gameId={row.id as string}>
				{row.away_score as number} - {row.home_score as number}
			</GameLink>
		),
	},
	{
		key: "home_team_name",
		label: "Home Team",
		filterable: true,
		renderCell: (_, row) => (
			<TeamLink teamId={row.home_team_id as string}>
				{row.home_team_name as string}
			</TeamLink>
		),
	},
	{
		key: "location",
		label: "Location",
	},
];

export function GamesTable({ games }: { games: Game[] }) {
	return (
		<FilterableTable
			data={games as unknown as Record<string, unknown>[]}
			columns={columns}
			defaultSort={{ key: "game_date", desc: true }}
		/>
	);
}
