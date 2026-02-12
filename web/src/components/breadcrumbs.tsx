import Link from "next/link";
import { ChevronRight } from "lucide-react";

interface Crumb {
	label: string;
	href?: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
	return (
		<nav className="flex items-center gap-1 text-sm text-muted-foreground mb-4">
			{items.map((item, i) => (
				<span key={i} className="flex items-center gap-1">
					{i > 0 && <ChevronRight className="h-3 w-3" />}
					{item.href ? (
						<Link href={item.href} className="hover:text-foreground">
							{item.label}
						</Link>
					) : (
						<span className="text-foreground">{item.label}</span>
					)}
				</span>
			))}
		</nav>
	);
}
