import Link from "next/link";

export function TeamLink({
	teamId,
	teamSlug,
	children,
	className,
}: {
	teamId?: string;
	teamSlug?: string;
	children: React.ReactNode;
	className?: string;
}) {
	const href = `/teams/${teamSlug ?? teamId}`;
	return (
		<Link
			href={href}
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
