import { useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchNetwork } from "@/client/api";
import { useAppStore } from "@/store";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  graphStyles,
  communityColor,
  nodeSize,
  CURATION_BORDER,
} from "@/lib/cytoscapeStyle";
import type { NetworkData } from "@/types/api";

// Cytoscape se importa de forma dinámica para no bloquear el bundle inicial
// y porque fcose es un layout plugin que se registra en el prototipo global.

/**
 * GraphCanvas — componente central, el HÉROE de la interfaz.
 *
 * Renderiza la red usando Cytoscape.js + fcose.
 * Color de nodo = comunidad, tamaño = degree_centrality.
 * Hover muestra tooltip; clic fija el paper en el store.
 */
export function GraphCanvas() {
  const activeKind = useAppStore((s) => s.activeKind);
  const selectPaper = useAppStore((s) => s.selectPaper);

  const { data, isLoading, error } = useQuery({
    queryKey: ["network", activeKind],
    queryFn: () => fetchNetwork(activeKind),
    staleTime: 60_000,
  });

  return (
    <main className="relative flex-1 flex flex-col overflow-hidden bg-obs-bg">
      {/* Controles del grafo */}
      <GraphControls />

      {/* Contenedor del canvas */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Spinner size={32} />
              <span className="text-text-muted text-xs font-mono">
                calculando red…
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-8">
            <div className="max-w-sm w-full">
              <ErrorBanner error={error} context={`network/${activeKind}`} />
            </div>
          </div>
        )}

        {data && !isLoading && (
          <CytoscapeCanvas
            data={data}
            onNodeClick={selectPaper}
          />
        )}

        {/* Leyenda de comunidades */}
        {data && <GraphLegend data={data} />}

        {/* Métricas */}
        {data && <GraphMetrics data={data} />}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// GraphControls
// ---------------------------------------------------------------------------

function GraphControls() {
  return (
    <div className="absolute top-3 left-3 z-10 flex gap-1.5">
      {/* Los controles se manejan con las teclas de Cytoscape; aquí solo info. */}
      <div className="bg-obs-surface/80 backdrop-blur-sm border border-obs-border rounded-obs px-2 py-1">
        <span className="text-text-muted text-2xs font-mono">
          scroll para zoom · drag para mover
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GraphLegend — comunidades del grafo como paleta protagonista
// ---------------------------------------------------------------------------

function GraphLegend({ data }: { data: NetworkData }) {
  const communities = new Set(
    data.nodes
      .map((n) => n.community)
      .filter((c): c is number => c != null)
  );

  if (communities.size === 0) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10 bg-obs-surface/80 backdrop-blur-sm border border-obs-border rounded-obs px-2.5 py-2">
      <p className="obs-section-label mb-1.5">Comunidades</p>
      <div className="flex flex-col gap-1">
        {[...communities].sort((a, b) => a - b).map((c) => (
          <div key={c} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: communityColor(c) }}
            />
            <span className="text-text-secondary text-2xs font-mono">
              C{c}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GraphMetrics — métricas de la red
// ---------------------------------------------------------------------------

function GraphMetrics({ data }: { data: NetworkData }) {
  const m = data.metrics;
  return (
    <div className="absolute bottom-4 right-4 z-10 bg-obs-surface/80 backdrop-blur-sm border border-obs-border rounded-obs px-2.5 py-2">
      <p className="obs-section-label mb-1.5">Métricas</p>
      <div className="flex flex-col gap-0.5 text-2xs font-mono text-text-secondary">
        <span>{m.n_nodes} nodos · {m.n_edges} aristas</span>
        <span>densidad {m.density.toFixed(4)}</span>
        <span>{m.n_communities} comunidades</span>
        <span>componentes {m.num_components}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CytoscapeCanvas — el corazón del grafo
// ---------------------------------------------------------------------------

interface CytoscapeCanvasProps {
  data: NetworkData;
  onNodeClick: (id: string) => void;
}

function CytoscapeCanvas({ data, onNodeClick }: CytoscapeCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cyRef = useRef<any>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const handleNodeClick = useCallback(
    (id: string) => {
      onNodeClick(id);
    },
    [onNodeClick]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;

    // Carga dinámica de Cytoscape + fcose
    Promise.all([
      import("cytoscape"),
      import("cytoscape-fcose"),
    ]).then(([cytoscapeModule, fcoseModule]) => {
      if (destroyed) return;

      const cytoscape = cytoscapeModule.default;
      const fcose = fcoseModule.default;

      // Registrar el layout fcose solo una vez
      try {
        cytoscape.use(fcose);
      } catch {
        // Ya registrado, ignorar
      }

      // Construir elementos desde los datos reales de la API
      const elements = [
        ...data.nodes.map((n) => ({
          data: {
            id: n.id,
            label: n.label,
            degree_centrality: n.degree_centrality,
            community: n.community,
            year: n.year,
            is_seed: n.is_seed,
            curation_status: n.curation_status,
          },
          classes: [
            n.is_seed ? "is-seed" : "",
          ].filter(Boolean).join(" "),
        })),
        ...data.edges.map((e) => ({
          data: {
            id: `${e.source}->${e.target}`,
            source: e.source,
            target: e.target,
            weight: e.weight,
          },
        })),
      ];

      // Opciones del layout fcose (tipado como any porque las opciones propias
      // de fcose no están en los tipos base de Cytoscape).
      const fcoseLayout: Record<string, unknown> = {
        name: "fcose",
        animate: true,
        animationDuration: 600,
        fit: true,
        padding: 40,
        idealEdgeLength: 80,
        nodeRepulsion: 6000,
        edgeElasticity: 0.45,
        gravity: 0.2,
      };

      const cy = cytoscape({
        container: containerRef.current!,
        elements,
        style: graphStyles,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layout: fcoseLayout as any,
        wheelSensitivity: 0.2,
        minZoom: 0.05,
        maxZoom: 8,
      });

      // Decorar nodos: color por comunidad, tamaño por centralidad
      cy.nodes().forEach((node) => {
        const community = node.data("community") as number | undefined;
        const dc = (node.data("degree_centrality") as number | undefined) ?? 0;
        const status = node.data("curation_status") as string | undefined;

        const borderColor =
          status != null && status in CURATION_BORDER
            ? CURATION_BORDER[status as keyof typeof CURATION_BORDER]
            : "#252934";

        node.style({
          "background-color": communityColor(community),
          "width": nodeSize(dc),
          "height": nodeSize(dc),
          "border-color": borderColor,
        });
      });

      // Decorar aristas: peso → opacidad
      cy.edges().forEach((edge) => {
        const weight = (edge.data("weight") as number | undefined) ?? 1;
        const maxWeight = Math.max(
          ...data.edges.map((e) => e.weight),
          1
        );
        const opacity = 0.15 + (weight / maxWeight) * 0.65;
        edge.style({ opacity, "line-color": "#3a4058" });
      });

      // Eventos: hover para tooltip, click para seleccionar
      cy.on("mouseover", "node", (evt) => {
        const node = evt.target;
        node.addClass("hovered");

        const tooltip = tooltipRef.current;
        if (!tooltip) return;

        const label = node.data("label") as string;
        const dc = ((node.data("degree_centrality") as number | undefined) ?? 0).toFixed(3);
        const community = node.data("community") as number | undefined;
        const year = node.data("year") as number | undefined;
        const status = node.data("curation_status") as string | undefined;

        tooltip.innerHTML = [
          `<span class="font-medium text-text-primary">${label}</span>`,
          `<span class="font-mono text-2xs text-text-muted">centralidad ${dc}</span>`,
          community != null
            ? `<span class="font-mono text-2xs" style="color:${communityColor(community)}">comunidad ${community}</span>`
            : "",
          year ? `<span class="text-2xs text-text-muted">${year}</span>` : "",
          status ? `<span class="text-2xs text-text-muted">${status}</span>` : "",
        ]
          .filter(Boolean)
          .join("\n");

        tooltip.style.display = "flex";
      });

      cy.on("mouseout", "node", (evt) => {
        evt.target.removeClass("hovered");
        if (tooltipRef.current) {
          tooltipRef.current.style.display = "none";
        }
      });

      cy.on("mousemove", (evt) => {
        const tooltip = tooltipRef.current;
        if (!tooltip || tooltip.style.display === "none") return;
        const renderedPos = evt.renderedPosition;
        tooltip.style.left = `${renderedPos.x + 14}px`;
        tooltip.style.top = `${renderedPos.y - 10}px`;
      });

      cy.on("tap", "node", (evt) => {
        const node = evt.target;
        handleNodeClick(node.data("id") as string);
      });

      cyRef.current = cy;
    });

    return () => {
      destroyed = true;
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [data, handleNodeClick]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Tooltip flotante */}
      <div
        ref={tooltipRef}
        style={{ display: "none", position: "absolute", pointerEvents: "none" }}
        className="flex flex-col gap-0.5 bg-obs-surface border border-obs-border rounded-obs px-2.5 py-2 shadow-obs-md z-20 max-w-48 text-xs animate-fade-in"
      />
    </div>
  );
}
