import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md";
  loading?: boolean;
}

/** Botón base para el tema "Observatorio". */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  children,
  disabled,
  className = "",
  ...rest
}: Props) {
  const base =
    "inline-flex items-center justify-center gap-1.5 font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-action-primary disabled:opacity-40 disabled:cursor-not-allowed rounded-obs";

  const variantCls =
    variant === "primary"
      ? "bg-action-primary text-obs-bg hover:bg-action-hover active:bg-action-focus"
      : variant === "secondary"
        ? "bg-obs-overlay text-text-primary border border-obs-border hover:border-text-muted"
        : variant === "danger"
          ? "bg-curation-rejected/20 text-curation-rejected border border-curation-rejected/40 hover:bg-curation-rejected/30"
          : /* ghost */ "text-text-secondary hover:text-text-primary hover:bg-obs-overlay";

  const sizeCls =
    size === "sm"
      ? "text-xs px-2 py-1"
      : "text-sm px-3 py-1.5";

  return (
    <button
      {...rest}
      disabled={disabled ?? loading}
      className={`${base} ${variantCls} ${sizeCls} ${className}`}
    >
      {loading ? (
        <svg
          className="animate-spin w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeDasharray="32"
            strokeDashoffset="8"
            opacity="0.3"
          />
          <path
            d="M12 2a10 10 0 0 1 10 10"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      {children}
    </button>
  );
}
