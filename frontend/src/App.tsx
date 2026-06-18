import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Header } from "@/components/workspace/Header";
import { RoundsColumn } from "@/components/rounds/RoundsColumn";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { CandidatePanel } from "@/components/candidate/CandidatePanel";
import { RoundDiffPanel } from "@/components/diff/RoundDiffPanel";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * App — Layout de 3 columnas: RONDAS · GRAFO · CANDIDATO.
 *
 * El RoundDiffPanel se superpone sobre el área del grafo cuando está activo.
 * Una sola pantalla sin modales que rompan el flujo (ADR 0027 §diseño).
 */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex flex-col h-full">
        {/* Header: nombre del workspace, estado, staleness */}
        <Header />

        {/* Layout de 3 columnas */}
        <div className="flex flex-1 overflow-hidden relative">
          {/* Columna izquierda: RONDAS */}
          <div className="w-col-left shrink-0">
            <RoundsColumn />
          </div>

          {/* Centro: GRAFO (el héroe) */}
          <GraphCanvas />

          {/* Columna derecha: CANDIDATO */}
          <div className="w-col-right shrink-0">
            <CandidatePanel />
          </div>

          {/* Overlay del diff (sobre el grafo) */}
          <RoundDiffPanel />
        </div>
      </div>
    </QueryClientProvider>
  );
}
