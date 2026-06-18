/**
 * client/api.ts — Las 7 llamadas tipadas (1:1 con los endpoints de G3).
 *
 * Cada función refleja un endpoint real de la API (API.md §0.2).
 * Los tipos de retorno espejant los DTOs de src/types/api.ts.
 */

import type {
  CurateRequest,
  CurateResult,
  NetworkData,
  NetworkKind,
  Paper,
  RoundDiff,
  RoundsData,
  Scent,
  WorkspaceState,
} from "@/types/api";
import { apiFetch } from "./http";

// ---------------------------------------------------------------------------
// Lecturas (GET)
// ---------------------------------------------------------------------------

/** GET /api/workspace — estado del workspace activo. */
export async function fetchWorkspace(): Promise<WorkspaceState> {
  return apiFetch<WorkspaceState>("/api/workspace");
}

/** GET /api/rounds — snapshots sellados + entrada "live". */
export async function fetchRounds(): Promise<RoundsData> {
  return apiFetch<RoundsData>("/api/rounds");
}

/** GET /api/paper/{id} — fila del corpus por id. */
export async function fetchPaper(paperId: string): Promise<Paper> {
  return apiFetch<Paper>(`/api/paper/${encodeURIComponent(paperId)}`);
}

/** GET /api/paper/{id}/scent — score de acoplamiento + vecinos. */
export async function fetchScent(paperId: string): Promise<Scent> {
  return apiFetch<Scent>(`/api/paper/${encodeURIComponent(paperId)}/scent`);
}

/** GET /api/network/{kind} — red de la ronda viva por kind. */
export async function fetchNetwork(kind: NetworkKind): Promise<NetworkData> {
  return apiFetch<NetworkData>(`/api/network/${kind}`);
}

/**
 * GET /api/compare?a=&b= — diff entre dos snapshots.
 *
 * @param roundA - id del snapshot A (o "live").
 * @param roundB - id del snapshot B (o "live").
 */
export async function fetchCompare(
  roundA: string,
  roundB: string
): Promise<RoundDiff> {
  const params = new URLSearchParams({ a: roundA, b: roundB });
  return apiFetch<RoundDiff>(`/api/compare?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Escritura (POST)
// ---------------------------------------------------------------------------

/**
 * POST /api/paper/{id}/curate — acepta o rechaza un paper.
 *
 * @param paperId - id del paper a curar.
 * @param decision - "accepted" | "rejected".
 */
export async function curatePaper(
  paperId: string,
  decision: CurateRequest["decision"]
): Promise<CurateResult> {
  return apiFetch<CurateResult>(
    `/api/paper/${encodeURIComponent(paperId)}/curate`,
    {
      method: "POST",
      body: JSON.stringify({ decision } satisfies CurateRequest),
    }
  );
}
