"use client";

import { SeasonDropdown } from "@/components/season-dropdown";

export function Navigation() {
	return (
		<header className="border-b">
			<div className="container mx-auto px-4 h-16 flex items-center justify-between">
				<div className="flex items-center gap-6">
					<h1 className="text-lg font-semibold">Lacrosse Stats</h1>
					<SeasonDropdown />
				</div>
			</div>
		</header>
	);
}
