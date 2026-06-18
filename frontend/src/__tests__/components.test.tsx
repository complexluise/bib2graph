/**
 * Tests de smoke de render para los componentes clave.
 *
 * Cobertura (docs/ROADMAP/05-gui.md §Tests G4):
 * 1. GraphCanvas monta con datos mínimos de NetworkData.
 * 2. RoundDiffPanel renderiza added/removed de un RoundDiff conocido.
 *
 * No se testea pixel-perfect ni Cytoscape real (requeriría jsdom + canvas).
 * GraphCanvas se testea sin el canvas de Cytoscape (stub del import dinámico).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { NetworkData, RoundDiff } from "@/types/api";

// ---------------------------------------------------------------------------
// Mocks — deben ir antes de los imports de los componentes
// ---------------------------------------------------------------------------

// Mock del store con los valores que necesitan los tests
const mockStoreState = {
  activeKind: "bibliographic_coupling" as const,
  selectPaper: vi.fn(),
  diffVisible: true,
  diffRoundA: "snap-2024-01" as string | null,
  diffRoundB: "live" as string | null,
  closeDiff: vi.fn(),
};

vi.mock("@/store", () => ({
  useAppStore: (selector: (s: typeof mockStoreState) => unknown) =>
    selector(mockStoreState),
}));

// Mock del cliente API con vi.fn() para poder configurar resoluciones por test
const mockFetchNetwork = vi.fn<() => Promise<NetworkData>>();
const mockFetchCompare = vi.fn<() => Promise<RoundDiff>>();

vi.mock("@/client/api", () => ({
  fetchNetwork: () => mockFetchNetwork(),
  fetchCompare: () => mockFetchCompare(),
}));

// Stub de cytoscape — evita que intente crear un canvas real en jsdom
vi.mock("cytoscape", () => ({
  default: () => ({
    nodes: () => ({ forEach: vi.fn() }),
    edges: () => ({ forEach: vi.fn() }),
    on: vi.fn(),
    destroy: vi.fn(),
  }),
}));

vi.mock("cytoscape-fcose", () => ({ default: vi.fn() }));

// ---------------------------------------------------------------------------
// Datos mock
// ---------------------------------------------------------------------------

const MOCK_NETWORK: NetworkData = {
  nodes: [
    {
      id: "P1",
      label: "Paper de prueba",
      degree_centrality: 0.8,
      community: 0,
      year: 2020,
      is_seed: true,
      curation_status: "accepted",
    },
    {
      id: "P2",
      label: "Otro paper",
      degree_centrality: 0.3,
      community: 1,
      year: 2021,
      is_seed: false,
      curation_status: "candidate",
    },
  ],
  edges: [{ source: "P1", target: "P2", weight: 2 }],
  metrics: {
    n_nodes: 2,
    n_edges: 1,
    density: 1.0,
    num_components: 1,
    avg_clustering: 0.0,
    n_communities: 2,
  },
};

const MOCK_DIFF: RoundDiff = {
  round_a: "snap-2024-01",
  round_b: "live",
  added_paper_ids: ["P3", "P4"],
  removed_paper_ids: ["P0"],
  mutated_hubs: [],
  metrics_change: [{ metric: "n_papers", before: 10, after: 12 }],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeQueryClient()}>
      {children}
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Test 1: GraphCanvas monta con datos mock de NetworkData
// ---------------------------------------------------------------------------

describe("GraphCanvas", () => {
  beforeEach(() => {
    mockFetchNetwork.mockResolvedValue(MOCK_NETWORK);
  });

  it("monta sin errores con datos mínimos de NetworkData", async () => {
    const { GraphCanvas } = await import("@/components/graph/GraphCanvas");

    const { container } = render(
      <Wrapper>
        <GraphCanvas />
      </Wrapper>
    );

    // El componente monta sin lanzar errores
    expect(container).toBeDefined();
    // El main wrapper debe estar presente
    const main = container.querySelector("main");
    expect(main).not.toBeNull();
  });

  it("muestra el hint de interacción del grafo", async () => {
    const { GraphCanvas } = await import("@/components/graph/GraphCanvas");

    render(
      <Wrapper>
        <GraphCanvas />
      </Wrapper>
    );

    // El texto de ayuda del scroll/drag debe estar en el DOM
    expect(screen.getByText(/scroll para zoom/i)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Test 2: RoundDiffPanel renderiza added/removed de un RoundDiff conocido
// ---------------------------------------------------------------------------

describe("RoundDiffPanel", () => {
  beforeEach(() => {
    mockFetchCompare.mockResolvedValue(MOCK_DIFF);
    // Asegurar que diffVisible=true y los rounds están configurados
    mockStoreState.diffVisible = true;
    mockStoreState.diffRoundA = "snap-2024-01";
    mockStoreState.diffRoundB = "live";
  });

  it("renderiza el panel cuando diffVisible=true con roundA y roundB", async () => {
    const { RoundDiffPanel } = await import(
      "@/components/diff/RoundDiffPanel"
    );

    render(
      <Wrapper>
        <RoundDiffPanel />
      </Wrapper>
    );

    // El panel debe estar visible
    expect(screen.getByRole("complementary")).toBeDefined();
    expect(screen.getByText("Diff de rondas")).toBeDefined();
  });

  it("muestra los ids de las rondas A y B en el header", async () => {
    const { RoundDiffPanel } = await import(
      "@/components/diff/RoundDiffPanel"
    );

    render(
      <Wrapper>
        <RoundDiffPanel />
      </Wrapper>
    );

    // Buscar los ids de rondas en el panel
    expect(screen.getByText(/snap-2024-01/)).toBeDefined();
    expect(screen.getByText(/live/)).toBeDefined();
  });

  it("muestra los added_paper_ids cuando la query resuelve", async () => {
    const { RoundDiffPanel } = await import(
      "@/components/diff/RoundDiffPanel"
    );

    const { findByText } = render(
      <Wrapper>
        <RoundDiffPanel />
      </Wrapper>
    );

    // Esperar que la query async resuelva
    const p3El = await findByText(/P3/);
    expect(p3El).toBeDefined();

    const p4El = await findByText(/P4/);
    expect(p4El).toBeDefined();
  });

  it("muestra los removed_paper_ids cuando la query resuelve", async () => {
    const { RoundDiffPanel } = await import(
      "@/components/diff/RoundDiffPanel"
    );

    const { findByText } = render(
      <Wrapper>
        <RoundDiffPanel />
      </Wrapper>
    );

    const p0El = await findByText(/P0/);
    expect(p0El).toBeDefined();
  });

  it("no renderiza nada cuando diffVisible=false", async () => {
    mockStoreState.diffVisible = false;

    const { RoundDiffPanel } = await import(
      "@/components/diff/RoundDiffPanel"
    );

    const { container } = render(
      <Wrapper>
        <RoundDiffPanel />
      </Wrapper>
    );

    // Sin contenido visible
    expect(container.firstChild).toBeNull();
  });
});
