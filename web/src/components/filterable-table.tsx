"use client";

import { useState, useMemo } from "react";
import {
	useReactTable,
	getCoreRowModel,
	getSortedRowModel,
	getPaginationRowModel,
	getFilteredRowModel,
	flexRender,
	type SortingState,
	type ColumnDef,
	type ColumnFiltersState,
	type VisibilityState,
} from "@tanstack/react-table";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ArrowUpDown, ChevronLeft, ChevronRight, Download, X, Columns3 } from "lucide-react";

export interface ColumnConfig {
	key: string;
	label: string;
	filterable?: boolean;
	renderCell?: (value: unknown, row: Record<string, unknown>) => React.ReactNode;
	visible?: boolean;
}

interface FilterableTableProps<T extends Record<string, unknown>> {
	data: T[];
	columns: ColumnConfig[];
	defaultSort?: { key: string; desc: boolean };
	pageSize?: number;
}

function formatCellValue(value: unknown): string {
	if (value === null || value === undefined) return "-";
	if (typeof value === "number") {
		return Number.isInteger(value) ? value.toString() : value.toFixed(2);
	}
	return String(value);
}

export function FilterableTable<T extends Record<string, unknown>>({
	data,
	columns: columnConfig,
	defaultSort,
	pageSize = 25,
}: FilterableTableProps<T>) {
	const [sorting, setSorting] = useState<SortingState>(
		defaultSort ? [{ id: defaultSort.key, desc: defaultSort.desc }] : [],
	);
	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
	const [globalFilter, setGlobalFilter] = useState("");

	const hasHiddenColumns = columnConfig.some((col) => col.visible === false);
	const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
		() => {
			const vis: VisibilityState = {};
			for (const col of columnConfig) {
				if (col.visible === false) {
					vis[col.key] = false;
				}
			}
			return vis;
		},
	);

	const filterableColumns = columnConfig.filter((col) => col.filterable);

	const filterOptions = useMemo(() => {
		const options: Record<string, string[]> = {};
		for (const col of filterableColumns) {
			const uniqueValues = [...new Set(data.map((row) => String(row[col.key] || "")))];
			options[col.key] = uniqueValues.sort();
		}
		return options;
	}, [data, filterableColumns]);

	const columns: ColumnDef<Record<string, unknown>>[] = columnConfig.map((col) => ({
		accessorKey: col.key,
		header: ({ column }) => (
			<Button
				variant="ghost"
				onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
				className="h-auto p-0 font-semibold hover:bg-transparent"
			>
				{col.label}
				<ArrowUpDown className="ml-2 h-4 w-4" />
			</Button>
		),
		cell: col.renderCell
			? ({ getValue, row }) => col.renderCell!(getValue(), row.original)
			: ({ getValue }) => formatCellValue(getValue()),
		filterFn: "includesString",
	}));

	const table = useReactTable({
		data,
		columns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
		onSortingChange: setSorting,
		onColumnFiltersChange: setColumnFilters,
		onGlobalFilterChange: setGlobalFilter,
		onColumnVisibilityChange: setColumnVisibility,
		state: {
			sorting,
			columnFilters,
			globalFilter,
			columnVisibility,
		},
		initialState: {
			pagination: {
				pageSize,
			},
		},
	});

	function exportToCSV() {
		const visibleCols = columnConfig.filter(
			(c) => columnVisibility[c.key] !== false,
		);
		const headers = visibleCols.map((c) => c.label).join(",");
		const rows = table
			.getFilteredRowModel()
			.rows.map((row) =>
				visibleCols
					.map((col) => {
						const value = row.original[col.key];
						const formatted = formatCellValue(value);
						return formatted.includes(",") ? `"${formatted}"` : formatted;
					})
					.join(","),
			)
			.join("\n");
		const csv = `${headers}\n${rows}`;
		const blob = new Blob([csv], { type: "text/csv" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "lacrosse-stats.csv";
		a.click();
		URL.revokeObjectURL(url);
	}

	function clearFilters() {
		setColumnFilters([]);
		setGlobalFilter("");
	}

	const hasActiveFilters = columnFilters.length > 0 || globalFilter.length > 0;

	return (
		<div className="space-y-4">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<Input
					placeholder="Search all columns..."
					value={globalFilter}
					onChange={(e) => setGlobalFilter(e.target.value)}
					className="max-w-sm"
				/>
				<div className="flex items-center gap-2">
					{hasActiveFilters && (
						<Button variant="ghost" size="sm" onClick={clearFilters}>
							<X className="mr-2 h-4 w-4" />
							Clear filters
						</Button>
					)}
					{hasHiddenColumns && (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button variant="outline" size="sm">
									<Columns3 className="mr-2 h-4 w-4" />
									Columns
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="end">
								{columnConfig.map((col) => (
									<DropdownMenuCheckboxItem
										key={col.key}
										checked={columnVisibility[col.key] !== false}
										onCheckedChange={(checked) =>
											setColumnVisibility((prev) => ({
												...prev,
												[col.key]: checked,
											}))
										}
									>
										{col.label}
									</DropdownMenuCheckboxItem>
								))}
							</DropdownMenuContent>
						</DropdownMenu>
					)}
					<Button variant="outline" size="sm" onClick={exportToCSV}>
						<Download className="mr-2 h-4 w-4" />
						Export
					</Button>
				</div>
			</div>

			{filterableColumns.length > 0 && (
				<div className="flex flex-wrap gap-2">
					{filterableColumns.map((col) => {
						const currentFilter = columnFilters.find((f) => f.id === col.key);
						return (
							<Select
								key={col.key}
								value={(currentFilter?.value as string) || ""}
								onValueChange={(value) => {
									if (value === "__all__") {
										setColumnFilters((prev) =>
											prev.filter((f) => f.id !== col.key),
										);
									} else {
										setColumnFilters((prev) => {
											const existing = prev.filter((f) => f.id !== col.key);
											return [...existing, { id: col.key, value }];
										});
									}
								}}
							>
								<SelectTrigger className="w-[180px]">
									<SelectValue placeholder={`Filter by ${col.label}`} />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="__all__">All {col.label}s</SelectItem>
									{filterOptions[col.key]
										?.filter((option) => option !== "")
										.slice(0, 100)
										.map((option) => (
											<SelectItem key={option} value={option}>
												{option}
											</SelectItem>
										))}
								</SelectContent>
							</Select>
						);
					})}
				</div>
			)}

			<div className="rounded-md border">
				<Table>
					<TableHeader>
						{table.getHeaderGroups().map((headerGroup) => (
							<TableRow key={headerGroup.id}>
								{headerGroup.headers.map((header) => (
									<TableHead key={header.id}>
										{header.isPlaceholder
											? null
											: flexRender(
													header.column.columnDef.header,
													header.getContext(),
												)}
									</TableHead>
								))}
							</TableRow>
						))}
					</TableHeader>
					<TableBody>
						{table.getRowModel().rows.length ? (
							table.getRowModel().rows.map((row) => (
								<TableRow key={row.id}>
									{row.getVisibleCells().map((cell) => (
										<TableCell key={cell.id}>
											{flexRender(
												cell.column.columnDef.cell,
												cell.getContext(),
											)}
										</TableCell>
									))}
								</TableRow>
							))
						) : (
							<TableRow>
								<TableCell
									colSpan={columns.length}
									className="h-24 text-center"
								>
									No results.
								</TableCell>
							</TableRow>
						)}
					</TableBody>
				</Table>
			</div>

			<div className="flex items-center justify-between">
				<p className="text-sm text-muted-foreground">
					{table.getFilteredRowModel().rows.length} results
					{hasActiveFilters && ` (filtered from ${data.length})`}
				</p>
				{table.getPageCount() > 1 && (
					<div className="flex items-center gap-2">
						<Button
							variant="outline"
							size="sm"
							onClick={() => table.previousPage()}
							disabled={!table.getCanPreviousPage()}
						>
							<ChevronLeft className="h-4 w-4" />
							Previous
						</Button>
						<span className="text-sm text-muted-foreground">
							Page {table.getState().pagination.pageIndex + 1} of{" "}
							{table.getPageCount()}
						</span>
						<Button
							variant="outline"
							size="sm"
							onClick={() => table.nextPage()}
							disabled={!table.getCanNextPage()}
						>
							Next
							<ChevronRight className="h-4 w-4" />
						</Button>
					</div>
				)}
			</div>
		</div>
	);
}
