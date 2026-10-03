"use client";

import { useState } from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { TableSkeleton } from "./Skeletons";
import { EmptyState } from "./EmptyState";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  loading?: boolean;
  searchPlaceholder?: string;
  searchColumn?: string;
  onRowClick?: (row: TData) => void;
  selectedRowId?: string | null;
  getRowId?: (row: TData) => string;
  emptyTitle?: string;
  emptyDescription?: string;
  pageSize?: number;
  showPagination?: boolean;
  className?: string;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  loading = false,
  searchPlaceholder = "Filter records...",
  searchColumn,
  onRowClick,
  selectedRowId,
  getRowId,
  emptyTitle = "No records found",
  emptyDescription = "There are no data rows matching the current filter criteria.",
  pageSize = 20,
  showPagination = true,
  className = "",
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    initialState: {
      pagination: {
        pageSize,
      },
    },
  });

  if (loading) {
    return <TableSkeleton rows={pageSize} columns={columns.length} className={className} />;
  }

  return (
    <div className={`w-full flex flex-col space-y-2.5 ${className}`}>
      {/* Top Filter Controls */}
      {searchPlaceholder && (
        <div className="flex items-center justify-between gap-3">
          <div className="relative w-72">
            <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={globalFilter ?? ""}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-[var(--radius-sm)] text-white placeholder-[var(--text-dim)] focus:outline-none focus:border-indigo-400"
            />
          </div>

          <div className="text-[11px] font-mono text-[var(--text-muted)]">
            Showing <span className="text-white font-semibold">{table.getFilteredRowModel().rows.length}</span> records
          </div>
        </div>
      )}

      {/* Table Frame */}
      <div className="w-full rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-x-auto shadow-sm">
        <table className="w-full text-xs text-left border-collapse">
          {/* Header */}
          <thead className="bg-[var(--bg-card)] border-b border-[var(--border-subtle)] text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider select-none">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sortDirection = header.column.getIsSorted();

                  return (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={`px-3 py-2.5 whitespace-nowrap ${
                        canSort ? "cursor-pointer hover:text-white transition" : ""
                      }`}
                      style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                    >
                      <div className="flex items-center gap-1.5">
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}

                        {canSort && (
                          <span className="text-[var(--text-dim)]">
                            {sortDirection === "asc" ? (
                              <ArrowUp className="w-3 h-3 text-indigo-400" />
                            ) : sortDirection === "desc" ? (
                              <ArrowDown className="w-3 h-3 text-indigo-400" />
                            ) : (
                              <ArrowUpDown className="w-2.5 h-2.5 opacity-50 hover:opacity-100" />
                            )}
                          </span>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>

          {/* Body */}
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-12 text-center">
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => {
                const rowKey = getRowId ? getRowId(row.original) : row.id;
                const isSelected = selectedRowId === rowKey;

                return (
                  <tr
                    key={row.id}
                    onClick={() => onRowClick && onRowClick(row.original)}
                    className={`transition-colors ${
                      onRowClick ? "cursor-pointer" : ""
                    } ${
                      isSelected
                        ? "bg-indigo-950/40 border-l-2 border-indigo-400"
                        : "hover:bg-[var(--bg-card-hover)]"
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2.5 whitespace-nowrap">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {showPagination && table.getPageCount() > 1 && (
        <div className="flex items-center justify-between px-2 pt-1 text-xs text-[var(--text-muted)] select-none">
          <div className="flex items-center gap-1.5 font-mono text-[11px]">
            <span>Page</span>
            <span className="font-semibold text-white">
              {table.getState().pagination.pageIndex + 1}
            </span>
            <span>of</span>
            <span className="font-semibold text-white">{table.getPageCount()}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="px-2 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-white disabled:opacity-30 disabled:pointer-events-none transition"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="px-2 py-1 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-white disabled:opacity-30 disabled:pointer-events-none transition"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
