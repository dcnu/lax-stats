import { Skeleton } from "@/components/ui/skeleton";

export default function GameDetailLoading() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-4 w-48" />
			<div className="flex items-center justify-between gap-8">
				<Skeleton className="h-16 w-48" />
				<Skeleton className="h-16 w-24" />
				<Skeleton className="h-16 w-48" />
			</div>
			<Skeleton className="h-9 w-64" />
			<div className="rounded-md border">
				<div className="space-y-2 p-4">
					{Array.from({ length: 8 }).map((_, i) => (
						<Skeleton key={i} className="h-10 w-full" />
					))}
				</div>
			</div>
		</div>
	);
}
