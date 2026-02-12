import { Skeleton } from "@/components/ui/skeleton";

export default function TeamsLoading() {
	return (
		<div>
			<Skeleton className="h-8 w-32 mb-6" />
			<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
				{Array.from({ length: 12 }).map((_, i) => (
					<Skeleton key={i} className="h-24 rounded-xl" />
				))}
			</div>
		</div>
	);
}
