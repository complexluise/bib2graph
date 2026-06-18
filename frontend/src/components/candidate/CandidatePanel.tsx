import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPaper, fetchScent, curatePaper } from "@/client/api";
import { useAppStore } from "@/store";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { CurationBadge } from "@/components/ui/Badge";
import { truncate } from "@/lib/format";
import type { Paper, Scent } from "@/types/api";

/**
 * CandidatePanel — columna derecha.
 *
 * Muestra el paper seleccionado (del grafo o al hacer clic).
 * Incluye: metadatos, scent (score + vecinos), botones de curación.
 * Al curar, hace refetch de la red para reflejar el estado actualizado.
 */
export function CandidatePanel() {
  const selectedPaperId = useAppStore((s) => s.selectedPaperId);

  if (!selectedPaperId) {
    return (
      <aside className="flex flex-col h-full border-l border-obs-border bg-obs-surface overflow-hidden">
        <div className="px-3 py-2.5 border-b border-obs-border shrink-0">
          <h2 className="obs-section-label">Candidato</h2>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 text-center">
          <div className="flex flex-col items-center gap-2">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              className="text-text-muted"
            >
              <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M12 8v4l3 3"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            <span className="text-text-muted text-xs leading-relaxed">
              Hacé clic en un nodo del grafo para ver los detalles del paper
            </span>
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex flex-col h-full border-l border-obs-border bg-obs-surface overflow-hidden">
      <PaperDetail paperId={selectedPaperId} />
    </aside>
  );
}

// ---------------------------------------------------------------------------
// PaperDetail
// ---------------------------------------------------------------------------

function PaperDetail({ paperId }: { paperId: string }) {
  const queryClient = useQueryClient();
  const activeKind = useAppStore((s) => s.activeKind);

  const {
    data: paper,
    isLoading: loadingPaper,
    error: errorPaper,
  } = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => fetchPaper(paperId),
  });

  const {
    data: scent,
    isLoading: loadingScent,
    error: errorScent,
  } = useQuery({
    queryKey: ["scent", paperId],
    queryFn: () => fetchScent(paperId),
    enabled: !!paper,
  });

  const curateMutation = useMutation({
    mutationFn: (decision: "accepted" | "rejected") =>
      curatePaper(paperId, decision),
    onSuccess: () => {
      // Refetch del paper y de la red para reflejar el cambio
      void queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
      void queryClient.invalidateQueries({ queryKey: ["network", activeKind] });
      void queryClient.invalidateQueries({ queryKey: ["workspace"] });
    },
  });

  return (
    <>
      {/* Header del panel */}
      <div className="px-3 py-2.5 border-b border-obs-border shrink-0">
        <h2 className="obs-section-label">Candidato</h2>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loadingPaper && (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        )}
        {errorPaper && (
          <div className="p-3">
            <ErrorBanner error={errorPaper} context={`paper/${paperId}`} />
          </div>
        )}

        {paper && (
          <>
            <PaperMeta paper={paper} />

            {/* Botones de curación */}
            {paper.curation_status !== "rejected" && (
              <div className="px-3 py-2.5 border-t border-obs-border">
                <p className="obs-section-label mb-2">Curar</p>
                <CurateActions
                  paper={paper}
                  onAccept={() => curateMutation.mutate("accepted")}
                  onReject={() => curateMutation.mutate("rejected")}
                  loading={curateMutation.isPending}
                  error={curateMutation.error}
                />
              </div>
            )}

            {/* Scent */}
            <div className="border-t border-obs-border">
              {loadingScent && (
                <div className="flex justify-center py-4">
                  <Spinner size={14} />
                </div>
              )}
              {errorScent && (
                <div className="p-3">
                  <ErrorBanner error={errorScent} context="scent" />
                </div>
              )}
              {scent && <ScentView scent={scent} />}
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// PaperMeta
// ---------------------------------------------------------------------------

function PaperMeta({ paper }: { paper: Paper }) {
  return (
    <div className="px-3 py-3">
      {/* Título */}
      <h3 className="text-sm font-medium text-text-primary leading-snug mb-2">
        {paper.title}
      </h3>

      {/* Estado + year */}
      <div className="flex items-center gap-2 mb-2.5">
        <CurationBadge
          status={paper.curation_status}
          isSeed={paper.is_seed}
        />
        {paper.year && (
          <span className="text-text-muted text-xs font-mono">{paper.year}</span>
        )}
      </div>

      {/* Autores */}
      {paper.authors_raw.length > 0 && (
        <div className="mb-2">
          <p className="obs-section-label mb-0.5">Autores</p>
          <p className="text-xs text-text-secondary leading-relaxed">
            {paper.authors_raw.slice(0, 3).join("; ")}
            {paper.authors_raw.length > 3 && ` +${paper.authors_raw.length - 3}`}
          </p>
        </div>
      )}

      {/* Abstract */}
      {paper.abstract && (
        <div className="mb-2">
          <p className="obs-section-label mb-0.5">Resumen</p>
          <p className="text-xs text-text-secondary leading-relaxed">
            {truncate(paper.abstract, 240)}
          </p>
        </div>
      )}

      {/* Keywords */}
      {paper.keywords_id.length > 0 && (
        <div className="mb-2">
          <p className="obs-section-label mb-0.5">Keywords</p>
          <div className="flex flex-wrap gap-1">
            {paper.keywords_id.slice(0, 6).map((kw) => (
              <span
                key={kw}
                className="text-2xs font-mono bg-obs-border/60 text-text-muted px-1 py-0.5 rounded"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* IDs */}
      <div className="flex flex-col gap-0.5">
        {paper.openalex_id && (
          <a
            href={`https://openalex.org/${paper.openalex_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-2xs font-mono text-action-primary hover:text-action-hover transition-colors"
          >
            {paper.openalex_id}
          </a>
        )}
        {paper.doi && (
          <a
            href={`https://doi.org/${paper.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-2xs font-mono text-text-muted hover:text-text-secondary transition-colors"
          >
            doi:{paper.doi}
          </a>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CurateActions
// ---------------------------------------------------------------------------

interface CurateActionsProps {
  paper: Paper;
  onAccept: () => void;
  onReject: () => void;
  loading: boolean;
  error: Error | null;
}

function CurateActions({
  paper,
  onAccept,
  onReject,
  loading,
  error,
}: CurateActionsProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-1.5">
        <Button
          variant="primary"
          size="sm"
          onClick={onAccept}
          loading={loading}
          disabled={paper.curation_status === "accepted"}
          className="flex-1"
        >
          Aceptar
        </Button>
        <Button
          variant="danger"
          size="sm"
          onClick={onReject}
          loading={loading}
          disabled={paper.curation_status === "rejected"}
          className="flex-1"
        >
          Rechazar
        </Button>
      </div>
      {error != null && <ErrorBanner error={error} context="curate" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ScentView — score + vecinos reales (no 4 paneles cosméticos del mock)
// ---------------------------------------------------------------------------

function ScentView({ scent }: { scent: Scent }) {
  return (
    <div className="px-3 py-3">
      {/* Score */}
      <div className="flex items-center gap-2 mb-3">
        <span className="obs-section-label">Scent bibliométrico</span>
        <span className="font-mono text-action-primary text-sm font-medium">
          {scent.score}
        </span>
      </div>

      {/* Coupling — vecinos con referencias compartidas */}
      {scent.coupling.length > 0 && (
        <div className="mb-3">
          <p className="obs-section-label mb-1">Acoplamiento</p>
          <div className="flex flex-col gap-1">
            {scent.coupling.slice(0, 5).map((n) => (
              <NeighborRow
                key={n.paper_id}
                title={n.title}
                {...(n.weight != null ? { weight: n.weight } : {})}
              />
            ))}
          </div>
        </div>
      )}

      {/* References */}
      {scent.references.length > 0 && (
        <div className="mb-3">
          <p className="obs-section-label mb-1">
            Referencias en corpus ({scent.references.length})
          </p>
          <div className="flex flex-col gap-1">
            {scent.references.slice(0, 4).map((n) => (
              <NeighborRow key={n.paper_id} title={n.title} />
            ))}
          </div>
        </div>
      )}

      {/* Cited by */}
      {scent.cited_by.length > 0 && (
        <div className="mb-3">
          <p className="obs-section-label mb-1">
            Citado por ({scent.cited_by.length})
          </p>
          <div className="flex flex-col gap-1">
            {scent.cited_by.slice(0, 4).map((n) => (
              <NeighborRow key={n.paper_id} title={n.title} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NeighborRow({
  title,
  weight,
}: {
  title: string | null;
  weight?: number;
}) {
  return (
    <div className="flex items-start gap-2 group">
      <div className="w-1 h-1 rounded-full bg-obs-border mt-1.5 shrink-0 group-hover:bg-action-primary transition-colors" />
      <div className="flex-1 min-w-0">
        <span className="text-xs text-text-secondary leading-snug line-clamp-2">
          {title ?? "(sin título)"}
        </span>
        {weight != null && (
          <span className="text-2xs font-mono text-text-muted">w={weight}</span>
        )}
      </div>
    </div>
  );
}
