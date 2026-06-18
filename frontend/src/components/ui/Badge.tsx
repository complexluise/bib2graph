import type { CurationStatus } from "@/types/api";
import { STATUS_LABELS } from "@/lib/format";

interface Props {
  status: CurationStatus;
  isSeed?: boolean;
  className?: string;
}

/** Badge de estado de curación. isSeed tiene precedencia visual. */
export function CurationBadge({ status, isSeed, className = "" }: Props) {
  if (isSeed) {
    return (
      <span
        className={`inline-flex items-center px-1.5 py-0.5 rounded text-2xs font-mono badge-seed ${className}`}
      >
        semilla
      </span>
    );
  }

  const cls =
    status === "accepted"
      ? "badge-accepted"
      : status === "rejected"
        ? "badge-rejected"
        : "badge-candidate";

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-2xs font-mono ${cls} ${className}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

interface SimpleBadgeProps {
  children: React.ReactNode;
  variant?: "neutral" | "accent" | "warn";
  className?: string;
}

export function Badge({ children, variant = "neutral", className = "" }: SimpleBadgeProps) {
  const cls =
    variant === "accent"
      ? "bg-action-primary/20 text-action-hover border border-action-primary/30"
      : variant === "warn"
        ? "bg-curation-seed/20 text-curation-seed border border-curation-seed/30"
        : "bg-obs-border/50 text-text-secondary border border-obs-border";

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-2xs font-mono ${cls} ${className}`}
    >
      {children}
    </span>
  );
}
