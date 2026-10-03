"use client";

import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionLoading?: boolean;
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  onAction,
  actionLoading = false,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`rounded-[var(--radius-md)] border border-dashed border-[var(--border-subtle)] bg-[var(--bg-surface)] p-8 text-center flex flex-col items-center justify-center max-w-lg mx-auto my-6 ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-muted)] mb-3">
        <Icon className="w-6 h-6 text-indigo-400" />
      </div>

      <h3 className="text-sm font-semibold text-white tracking-tight">{title}</h3>
      <p className="text-xs text-[var(--text-muted)] mt-1.5 leading-relaxed max-w-sm">
        {description}
      </p>

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          disabled={actionLoading}
          className="mt-4 px-3.5 py-1.5 rounded-[var(--radius-sm)] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold transition shadow-md shadow-indigo-600/20"
        >
          {actionLoading ? "Triggering..." : actionLabel}
        </button>
      )}
    </div>
  );
}
