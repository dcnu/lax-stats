import type { Player } from "@/lib/types";
import { TeamLink } from "@/components/entity-link";

export function PlayerHeader({ player }: { player: Player }) {
	return (
		<div className="space-y-1">
			<h1 className="text-2xl font-bold">{player.name}</h1>
			<div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
				{player.jersey_number !== null && (
					<span>#{player.jersey_number}</span>
				)}
				{player.primary_position && (
					<span>{player.primary_position}</span>
				)}
				{player.team_id && (
					<TeamLink teamId={player.team_id}>
						{player.team_id}
					</TeamLink>
				)}
				{player.hometown && (
					<span>{player.hometown}</span>
				)}
				{player.high_school && (
					<span>{player.high_school}</span>
				)}
			</div>
		</div>
	);
}
