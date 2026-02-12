import Link from "next/link";

export function TeamLink({
	teamId,
	children,
	className,
}: {
	teamId: string;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<Link
			href={`/teams/${teamId}`}
			className={className ?? "text-primary hover:underline"}
		>
			{children}
		</Link>
	);
}

export function PlayerLink({
	playerId,
	children,
	className,
}: {
	playerId: number;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<Link
			href={`/players/${playerId}`}
			className={className ?? "text-primary hover:underline"}
		>
			{children}
		</Link>
	);
}

export function GameLink({
	gameId,
	children,
	className,
}: {
	gameId: string;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<Link
			href={`/games/${gameId}`}
			className={className ?? "text-primary hover:underline"}
		>
			{children}
		</Link>
	);
}
