import { useQuery } from "@tanstack/react-query";
import { fetchRounds } from "@/client/api";
import { useAppStore } from "@/store";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import type { NetworkKind, RoundEntry } from "@/types/api";
import { KIND_LABELS, formatDate, truncate } from "@/lib/format";

const NETWORK_KINDS: NetworkKind[] = [
  "bibliographic_coupling",
  "cocitation",
  "author_collab",
  "institution_collab",
  "keyword_cooccurrence",
];

/** Columna izquierda: listado de rondas/snapshots + selector de NetworkKind + control A/B para diff. */
export function RoundsColumn() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["rounds"],
    queryFn: fetchRounds,
    staleTime: 15_000,
  });

  const activeKind = useAppStore((s) => s.activeKind);
  const setActiveKind = useAppStore((s) => s.setActiveKind);
  const diffRoundA = useAppStore((s) => s.diffRoundA);
  const diffRoundB = useAppStore((s) => s.diffRoundB);
  const setDiffRoundA = useAppStore((s) => s.setDiffRoundA);
  const setDiffRoundB = useAppStore((s) => s.setDiffRoundB);
  const toggleDiff = useAppStore((s) => s.toggleDiff);

  const rounds = data?.rounds ?? [];

  return (
    <aside className="flex flex-col h-full border-r border-obs-border bg-obs-surface overflow-hidden">
      {/* Título */}
      <div className="px-3 py-2.5 border-b border-obs-border shrink-0">
        <h2 className="obs-section-label">Rondas</h2>
      </div>

      {/* Selector de NetworkKind */}
      <div className="px-3 py-2 border-b border-obs-border shrink-0">
        <p className="obs-section-label mb-1.5">Red activa</p>
        <div className="flex flex-col gap-0.5">
          {NETWORK_KINDS.map((kind) => (
            <button
              key={kind}
              onClick={() => setActiveKind(kind)}
              className={`text-left text-xs px-2 py-1 rounded transition-colors ${
                activeKind === kind
                  ? "bg-action-primary/20 text-action-hover border border-action-primary/40"
                  : "text-text-secondary hover:text-text-primary hover:bg-obs-overlay"
              }`}
            >
              {KIND_LABELS[kind] ?? kind}
            </button>
          ))}
        </div>
      </div>

      {/* Lista de rondas */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {isLoading && (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        )}
        {error && (
          <div className="px-1">
            <ErrorBanner error={error} context="rounds" />
          </div>
        )}
        {rounds.map((round) => (
          <RoundItem
            key={round.id}
            round={round}
            isSelectedA={diffRoundA === round.id}
            isSelectedB={diffRoundB === round.id}
            onSelectA={() =>
              setDiffRoundA(diffRoundA === round.id ? null : round.id)
            }
            onSelectB={() =>
              setDiffRoundB(diffRoundB === round.id ? null : round.id)
            }
          />
        ))}
      </div>

      {/* Control de diff: botón activo cuando hay A y B */}
      <div className="px-3 py-2.5 border-t border-obs-border shrink-0">
        <p className="obs-section-label mb-1.5">Comparar rondas</p>
        <div className="flex gap-1.5 items-center text-xs text-text-muted mb-2">
          <span>A: {diffRoundA ? truncate(diffRoundA, 10) : "—"}</span>
          <span className="text-obs-border">↔</span>
          <span>B: {diffRoundB ? truncate(diffRoundB, 10) : "—"}</span>
        </div>
        <Button
          size="sm"
          variant={diffRoundA && diffRoundB ? "primary" : "secondary"}
          disabled={!(diffRoundA && diffRoundB)}
          onClick={toggleDiff}
          className="w-full"
        >
          Ver diff
        </Button>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// RoundItem
// ---------------------------------------------------------------------------

interface RoundItemProps {
  round: RoundEntry;
  isSelectedA: boolean;
  isSelectedB: boolean;
  onSelectA: () => void;
  onSelectB: () => void;
}

function RoundItem({
  round,
  isSelectedA,
  isSelectedB,
  onSelectA,
  onSelectB,
}: RoundItemProps) {
  const isLive = round.id === "live";

  return (
    <div
      className={`mb-1 rounded-obs px-2 py-1.5 border transition-colors ${
        isSelectedA || isSelectedB
          ? "border-action-primary/40 bg-action-primary/10"
          : "border-obs-border bg-obs-bg hover:border-obs-overlay hover:bg-obs-overlay/50"
      }`}
    >
      {/* ID y tipo */}
      <div className="flex items-center gap-1.5 mb-0.5">
        {isLive ? (
          <span className="text-2xs font-mono text-action-primary bg-action-primary/20 px-1 py-0.5 rounded">
            live
          </span>
        ) : (
          <span className="text-2xs font-mono text-text-muted">snap</span>
        )}
        <span className="text-xs text-text-secondary font-mono truncate">
          {truncate(round.id, 14)}
        </span>
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-2 text-2xs text-text-muted">
        <span>{round.total_papers} papers</span>
        {round.created_at && <span>{formatDate(round.created_at)}</span>}
        {isLive && round.loop_state && (
          <span className="font-mono">{round.loop_state}</span>
        )}
      </div>

      {/* Selectores A/B */}
      <div className="flex gap-1 mt-1.5">
        <button
          onClick={onSelectA}
          className={`text-2xs px-1.5 py-0.5 rounded font-mono transition-colors ${
            isSelectedA
              ? "bg-action-primary text-obs-bg"
              : "bg-obs-border/50 text-text-muted hover:text-text-primary"
          }`}
        >
          A
        </button>
        <button
          onClick={onSelectB}
          className={`text-2xs px-1.5 py-0.5 rounded font-mono transition-colors ${
            isSelectedB
              ? "bg-community-2 text-obs-bg"
              : "bg-obs-border/50 text-text-muted hover:text-text-primary"
          }`}
        >
          B
        </button>
      </div>
    </div>
  );
}
