import { TeamLink } from "@/components/entity-link";
import { formatGameDate } from "@/lib/format";
import type { Game } from "@/lib/types";

export function GameHeader({ game }: { game: Game }) {
	return (
		<div className="space-y-3">
			<div className="flex items-center justify-center gap-6 text-center">
				<div className="flex-1 text-right">
					<TeamLink teamId={game.away_team_id} className="text-xl font-bold hover:underline">
						{game.away_team_name}
					</TeamLink>
					{game.away_team_wins !== null && game.away_team_losses !== null && (
						<p className="text-sm text-muted-foreground">
							({game.away_team_wins}-{game.away_team_losses})
						</p>
					)}
				</div>
				<div className="flex flex-col items-center">
					<div className="text-3xl font-bold tabular-nums">
						{game.away_score} - {game.home_score}
					</div>
					<span className="text-xs text-muted-foreground uppercase">Final</span>
				</div>
				<div className="flex-1 text-left">
					<TeamLink teamId={game.home_team_id} className="text-xl font-bold hover:underline">
						{game.home_team_name}
					</TeamLink>
					{game.home_team_wins !== null && game.home_team_losses !== null && (
						<p className="text-sm text-muted-foreground">
							({game.home_team_wins}-{game.home_team_losses})
						</p>
					)}
				</div>
			</div>
			<div className="flex items-center justify-center gap-4 text-sm text-muted-foreground">
				<span>{formatGameDate(game.game_date)}</span>
				{game.location && (
					<>
						<span>&middot;</span>
						<span>{game.location}</span>
					</>
				)}
				{game.attendance && (
					<>
						<span>&middot;</span>
						<span>Attendance: {game.attendance.toLocaleString()}</span>
					</>
				)}
			</div>
		</div>
	);
}
