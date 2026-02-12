"use client";

import { FilterableTable } from "@/components/filterable-table";
import type { ColumnConfig } from "@/components/filterable-table";
import { TeamLink } from "@/components/entity-link";
import { formatPct, formatRecord } from "@/lib/format";
import type { Ranking } from "@/lib/types";

const columns: ColumnConfig[] = [
	{ key: "rank", label: "Rank" },
	{
		key: "team_name",
		label: "Team",
		renderCell: (_value, row) => (
			<TeamLink teamId={row.team_id as string}>
				{row.team_name as string}
			</TeamLink>
		),
	},
	{
		key: "record",
		label: "Record",
		renderCell: (_value, row) =>
			formatRecord(row.wins as number, row.losses as number),
	},
	{
		key: "wp",
		label: "WP",
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "owp",
		label: "OWP",
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "oowp",
		label: "OOWP",
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "rpi",
		label: "RPI",
		renderCell: (value) => formatPct(value as number | null),
	},
	{
		key: "massey",
		label: "Massey",
		renderCell: (value) => {
			if (value === null || value === undefined) return "-";
			const num = typeof value === "string" ? parseFloat(value) : (value as number);
			if (isNaN(num)) return "-";
			return num.toFixed(2);
		},
	},
	{
		key: "massey_recency",
		label: "Massey Recency",
		visible: false,
		renderCell: (value) => {
			if (value === null || value === undefined) return "-";
			const num = typeof value === "string" ? parseFloat(value) : (value as number);
			if (isNaN(num)) return "-";
			return num.toFixed(2);
		},
	},
	{
		key: "projected_rpi_flat",
		label: "Proj. RPI Flat",
		visible: false,
		renderCell: (_value, row) => {
			const val = row.projected_rpi_flat as number | null;
			const low = row.projected_rpi_flat_low as number | null;
			const high = row.projected_rpi_flat_high as number | null;
			if (val === null || val === undefined) return "-";
			const range =
				low !== null && high !== null
					? ` (${formatPct(low)}-${formatPct(high)})`
					: "";
			return `${formatPct(val)}${range}`;
		},
	},
	{
		key: "projected_rpi_seeded",
		label: "Proj. RPI Seeded",
		visible: false,
		renderCell: (_value, row) => {
			const val = row.projected_rpi_seeded as number | null;
			const low = row.projected_rpi_seeded_low as number | null;
			const high = row.projected_rpi_seeded_high as number | null;
			if (val === null || val === undefined) return "-";
			const range =
				low !== null && high !== null
					? ` (${formatPct(low)}-${formatPct(high)})`
					: "";
			return `${formatPct(val)}${range}`;
		},
	},
];

export function RankingsTable({ rankings }: { rankings: Ranking[] }) {
	const rankedData = rankings.map((row, i) => ({
		...row,
		rank: i + 1,
	}));

	return (
		<FilterableTable
			data={rankedData}
			columns={columns}
			defaultSort={{ key: "rpi", desc: true }}
			pageSize={50}
		/>
	);
}
