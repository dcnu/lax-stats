import Link from "next/link";
import { getSeasons, getCurrentSeasonId } from "@/lib/queries/seasons";
import { SeasonDivisionSelector } from "@/components/season-division-selector";

const navLinks = [
	{ href: "/teams", label: "Teams" },
	{ href: "/games", label: "Games" },
	{ href: "/players", label: "Players" },
	{ href: "/rankings", label: "Rankings" },
];

export async function Navigation() {
	const [seasons, currentSeasonId] = await Promise.all([
		getSeasons(),
		getCurrentSeasonId(),
	]);

	return (
		<header className="border-b">
			<div className="container mx-auto px-4 h-14 flex items-center justify-between">
				<div className="flex items-center gap-6">
					<Link href="/teams" className="text-lg font-semibold">
						Lacrosse Stats
					</Link>
					<nav className="flex items-center gap-4">
						{navLinks.map((link) => (
							<Link
								key={link.href}
								href={link.href}
								className="text-sm text-muted-foreground hover:text-foreground transition-colors"
							>
								{link.label}
							</Link>
						))}
					</nav>
				</div>
				<SeasonDivisionSelector
					seasons={seasons}
					currentSeasonId={currentSeasonId}
				/>
			</div>
		</header>
	);
}
