import { useQuery } from "@tanstack/react-query";
import { fetchWorkspace } from "@/client/api";
import { Spinner } from "@/components/ui/Spinner";
import { Badge } from "@/components/ui/Badge";

/** Header global — nombre del workspace, estado del lazo, aviso de staleness. */
export function Header() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["workspace"],
    queryFn: fetchWorkspace,
    staleTime: 30_000,
  });

  return (
    <header className="flex items-center gap-4 px-4 h-10 bg-obs-surface border-b border-obs-border shrink-0">
      {/* Logotipo / nombre del producto */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-mono text-action-primary font-medium tracking-tight">
          bib2graph
        </span>
        <span className="text-text-muted text-2xs">observatorio</span>
      </div>

      <div className="w-px h-4 bg-obs-border" />

      {isLoading && <Spinner size={14} />}

      {data && (
        <>
          {/* Nombre del workspace */}
          <span className="text-sm text-text-primary font-medium truncate max-w-40">
            {data.name}
          </span>

          <div className="w-px h-4 bg-obs-border" />

          {/* Estado del lazo */}
          {data.loop_state && (
            <Badge variant="neutral">
              {data.loop_state.toLowerCase()}
            </Badge>
          )}

          {/* Ronda */}
          <span className="text-text-muted text-xs font-mono">
            ronda {data.round}
          </span>

          {/* Total papers */}
          <span className="text-text-muted text-xs">
            {data.total_papers.toLocaleString("es-AR")} papers
          </span>

          {/* Staleness: aviso si la cache de redes está desactualizada */}
          {data.networks_cache_stale && (
            <Badge variant="warn" className="ml-auto">
              redes desactualizadas — ejecutá b2g build
            </Badge>
          )}
        </>
      )}

      {error && (
        <span className="text-curation-rejected text-xs ml-2">
          Error al cargar workspace
        </span>
      )}
    </header>
  );
}
