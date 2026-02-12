import { Skeleton } from "@/components/ui/skeleton";

export default function RankingsLoading() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-9 w-48" />
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<Skeleton className="h-10 w-64" />
					<Skeleton className="h-9 w-24" />
				</div>
				<div className="rounded-md border">
					<div className="space-y-0">
						<Skeleton className="h-10 w-full" />
						{Array.from({ length: 15 }).map((_, i) => (
							<Skeleton key={i} className="h-10 w-full" />
						))}
					</div>
				</div>
			</div>
		</div>
	);
}
