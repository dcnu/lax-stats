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
import { ArrowUpDown, ChevronLeft, ChevronRight, X, Columns3 } from "lucide-react";

export interface ColumnConfig {
	key: string;
	label: string;
	filterable?: boolean;
	filterType?: "select" | "min";
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

	const selectFilterColumns = columnConfig.filter(
		(col) => col.filterable && col.filterType !== "min",
	);
	const minFilterColumns = columnConfig.filter(
		(col) => col.filterable && col.filterType === "min",
	);

	const filterOptions = useMemo(() => {
		const options: Record<string, string[]> = {};
		for (const col of selectFilterColumns) {
			const uniqueValues = [...new Set(data.map((row) => String(row[col.key] || "")))];
			options[col.key] = uniqueValues.sort();
		}
		return options;
	}, [data, selectFilterColumns]);

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
		filterFn: col.filterType === "min"
			? (row, columnId, filterValue) => {
					const val = row.getValue(columnId);
					if (filterValue === "" || filterValue === undefined) return true;
					return Number(val) >= Number(filterValue);
				}
			: "includesString",
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

	function clearFilters() {
		setColumnFilters([]);
		setGlobalFilter("");
	}

	const hasActiveFilters = columnFilters.length > 0 || globalFilter.length > 0;

	return (
		<div className="space-y-4">
			<div className="flex flex-wrap items-center gap-2">
				<Input
					placeholder="Search all columns..."
					value={globalFilter}
					onChange={(e) => setGlobalFilter(e.target.value)}
					className="w-48 sm:w-64"
				/>
				{selectFilterColumns.map((col) => {
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
				{minFilterColumns.map((col) => {
					const currentFilter = columnFilters.find((f) => f.id === col.key);
					return (
						<Input
							key={col.key}
							type="number"
							placeholder={`Min ${col.label}`}
							value={(currentFilter?.value as string) ?? ""}
							onChange={(e) => {
								const val = e.target.value;
								if (val === "") {
									setColumnFilters((prev) =>
										prev.filter((f) => f.id !== col.key),
									);
								} else {
									setColumnFilters((prev) => {
										const existing = prev.filter((f) => f.id !== col.key);
										return [...existing, { id: col.key, value: val }];
									});
								}
							}}
							className="w-20"
						/>
					);
				})}
				<div className="flex-1" />
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
				</div>
			</div>

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
