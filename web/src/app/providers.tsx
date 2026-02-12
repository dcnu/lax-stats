"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Suspense, useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
	const [queryClient] = useState(
		() =>
			new QueryClient({
				defaultOptions: {
					queries: {
						staleTime: 5 * 60 * 1000,
						gcTime: 10 * 60 * 1000,
						retry: false,
						refetchOnWindowFocus: false,
					},
				},
			}),
	);

	return (
		<Suspense>
			<NuqsAdapter>
				<QueryClientProvider client={queryClient}>
					{children}
				</QueryClientProvider>
			</NuqsAdapter>
		</Suspense>
	);
}
