"use client";

import type { PlayerSeason } from "@/lib/types";
import { PlayerLink } from "@/components/entity-link";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

type RosterPlayer = PlayerSeason & {
	name: string;
	hometown: string | null;
	high_school: string | null;
};

export function TeamRoster({ roster }: { roster: RosterPlayer[] }) {
	if (roster.length === 0) {
		return <p className="text-muted-foreground">No roster available.</p>;
	}

	return (
		<div className="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead className="w-12">#</TableHead>
						<TableHead>Name</TableHead>
						<TableHead>Pos</TableHead>
						<TableHead>Class</TableHead>
						<TableHead>Hometown</TableHead>
						<TableHead>High School</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{roster.map((player) => (
						<TableRow key={player.id}>
							<TableCell>{player.jersey_number ?? "-"}</TableCell>
							<TableCell>
								<PlayerLink playerId={player.player_id}>
									{player.name}
								</PlayerLink>
							</TableCell>
							<TableCell>{player.primary_position || "-"}</TableCell>
							<TableCell>{player.class_year || "-"}</TableCell>
							<TableCell className="text-muted-foreground">
								{player.hometown || "-"}
							</TableCell>
							<TableCell className="text-muted-foreground">
								{player.high_school || "-"}
							</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}
