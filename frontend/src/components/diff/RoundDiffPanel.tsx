import { useQuery } from "@tanstack/react-query";
import { fetchCompare } from "@/client/api";
import { useAppStore } from "@/store";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { truncate } from "@/lib/format";
import type { RoundDiff } from "@/types/api";

/**
 * RoundDiffPanel — panel de diff entre dos rondas (EL DIFERENCIADOR, ADR 0027).
 *
 * Muestra: papers añadidos, papers eliminados, cambios en métricas.
 * Se activa desde la columna de RONDAS (selector A/B + botón "Ver diff").
 */
export function RoundDiffPanel() {
  const diffVisible = useAppStore((s) => s.diffVisible);
  const diffRoundA = useAppStore((s) => s.diffRoundA);
  const diffRoundB = useAppStore((s) => s.diffRoundB);
  const closeDiff = useAppStore((s) => s.closeDiff);

  if (!diffVisible) return null;

  return (
    <div
      className="absolute inset-y-0 right-0 z-30 w-96 bg-obs-surface border-l border-obs-border shadow-obs-md flex flex-col animate-fade-in"
      role="complementary"
      aria-label="Diff de rondas"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-obs-border shrink-0">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-sm font-medium text-text-primary">
            Diff de rondas
          </h2>
          <div className="flex items-center gap-1.5 text-2xs font-mono text-text-muted">
            <span className="text-action-primary">
              {diffRoundA ? truncate(diffRoundA, 12) : "—"}
            </span>
            <span>↔</span>
            <span className="text-community-2">
              {diffRoundB ? truncate(diffRoundB, 12) : "—"}
            </span>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={closeDiff}>
          ✕
        </Button>
      </div>

      {/* Contenido */}
      <div className="flex-1 overflow-y-auto">
        {diffRoundA && diffRoundB ? (
          <DiffContent roundA={diffRoundA} roundB={diffRoundB} />
        ) : (
          <div className="flex items-center justify-center h-full p-6 text-center">
            <span className="text-text-muted text-xs">
              Seleccioná dos rondas (A y B) para ver el diff
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DiffContent
// ---------------------------------------------------------------------------

function DiffContent({
  roundA,
  roundB,
}: {
  roundA: string;
  roundB: string;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["compare", roundA, roundB],
    queryFn: () => fetchCompare(roundA, roundB),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3">
        <ErrorBanner error={error} context="compare" />
      </div>
    );
  }

  if (!data) return null;

  return <DiffView diff={data} />;
}

// ---------------------------------------------------------------------------
// DiffView
// ---------------------------------------------------------------------------

function DiffView({ diff }: { diff: RoundDiff }) {
  const totalAdded = diff.added_paper_ids.length;
  const totalRemoved = diff.removed_paper_ids.length;
  const netChange = totalAdded - totalRemoved;

  return (
    <div className="p-3 flex flex-col gap-4">
      {/* Resumen */}
      <div className="obs-panel px-3 py-2.5">
        <p className="obs-section-label mb-2">Resumen</p>
        <div className="flex gap-4">
          <div className="flex flex-col items-center">
            <span className="text-curation-accepted text-lg font-mono font-medium">
              +{totalAdded}
            </span>
            <span className="text-2xs text-text-muted">añadidos</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-curation-rejected text-lg font-mono font-medium">
              -{totalRemoved}
            </span>
            <span className="text-2xs text-text-muted">eliminados</span>
          </div>
          <div className="flex flex-col items-center">
            <span
              className={`text-lg font-mono font-medium ${
                netChange > 0
                  ? "text-curation-accepted"
                  : netChange < 0
                    ? "text-curation-rejected"
                    : "text-text-muted"
              }`}
            >
              {netChange >= 0 ? "+" : ""}
              {netChange}
            </span>
            <span className="text-2xs text-text-muted">neto</span>
          </div>
        </div>
      </div>

      {/* Cambios en métricas */}
      {diff.metrics_change.length > 0 && (
        <div>
          <p className="obs-section-label mb-2">Métricas</p>
          <div className="flex flex-col gap-1">
            {diff.metrics_change.map((mc) => (
              <MetricRow key={mc.metric} change={mc} />
            ))}
          </div>
        </div>
      )}

      {/* Papers añadidos */}
      {totalAdded > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-2 h-2 rounded-full bg-curation-accepted shrink-0" />
            <p className="obs-section-label">Añadidos ({totalAdded})</p>
          </div>
          <div className="flex flex-col gap-0.5">
            {diff.added_paper_ids.map((id) => (
              <PaperIdRow key={id} id={id} variant="added" />
            ))}
          </div>
        </div>
      )}

      {/* Papers eliminados */}
      {totalRemoved > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-2 h-2 rounded-full bg-curation-rejected shrink-0" />
            <p className="obs-section-label">Eliminados ({totalRemoved})</p>
          </div>
          <div className="flex flex-col gap-0.5">
            {diff.removed_paper_ids.map((id) => (
              <PaperIdRow key={id} id={id} variant="removed" />
            ))}
          </div>
        </div>
      )}

      {totalAdded === 0 && totalRemoved === 0 && (
        <div className="text-center py-6">
          <span className="text-text-muted text-sm">
            Las rondas son idénticas
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponentes
// ---------------------------------------------------------------------------

function MetricRow({ change }: { change: { metric: string; before: number; after: number } }) {
  const delta = change.after - change.before;
  const isPositive = delta > 0;
  const isNeutral = delta === 0;

  return (
    <div className="flex items-center justify-between py-1 border-b border-obs-border/50">
      <span className="text-xs text-text-secondary font-mono">{change.metric}</span>
      <div className="flex items-center gap-2 text-xs font-mono">
        <span className="text-text-muted">{change.before}</span>
        <span className="text-text-muted">→</span>
        <span
          className={
            isNeutral
              ? "text-text-muted"
              : isPositive
                ? "text-curation-accepted"
                : "text-curation-rejected"
          }
        >
          {change.after}
        </span>
        {!isNeutral && (
          <span
            className={`text-2xs ${isPositive ? "text-curation-accepted" : "text-curation-rejected"}`}
          >
            ({isPositive ? "+" : ""}
            {delta})
          </span>
        )}
      </div>
    </div>
  );
}

function PaperIdRow({
  id,
  variant,
}: {
  id: string;
  variant: "added" | "removed";
}) {
  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-2xs font-mono ${
        variant === "added"
          ? "text-curation-accepted bg-curation-accepted/5"
          : "text-curation-rejected bg-curation-rejected/5"
      }`}
    >
      <span>{variant === "added" ? "+" : "-"}</span>
      <span className="truncate">{id}</span>
    </div>
  );
}
