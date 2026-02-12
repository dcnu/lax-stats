import { Skeleton } from "@/components/ui/skeleton";

export default function GamesLoading() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-9 w-32" />
			<Skeleton className="h-10 w-full max-w-sm" />
			<div className="rounded-md border">
				<div className="space-y-2 p-4">
					{Array.from({ length: 10 }).map((_, i) => (
						<Skeleton key={i} className="h-10 w-full" />
					))}
				</div>
			</div>
		</div>
	);
}
