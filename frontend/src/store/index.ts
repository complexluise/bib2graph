/**
 * store/index.ts — Estado global mínimo (Zustand).
 *
 * Solo lo que cruza columnas:
 * - paper seleccionado (clic en el grafo → panel candidato)
 * - kind de red activo (toggle en RONDAS → grafo)
 * - par A/B para el diff de rondas
 * - si el panel diff está visible
 */

import { create } from "zustand";
import type { NetworkKind } from "@/types/api";

interface AppState {
  /** Id del paper seleccionado (clic en nodo del grafo). */
  selectedPaperId: string | null;

  /** Tipo de red activa. */
  activeKind: NetworkKind;

  /** Ronda A seleccionada para el diff. */
  diffRoundA: string | null;

  /** Ronda B seleccionada para el diff. */
  diffRoundB: string | null;

  /** Si el panel de diff está visible. */
  diffVisible: boolean;

  // Mutaciones
  selectPaper: (id: string | null) => void;
  setActiveKind: (kind: NetworkKind) => void;
  setDiffRoundA: (id: string | null) => void;
  setDiffRoundB: (id: string | null) => void;
  toggleDiff: () => void;
  closeDiff: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedPaperId: null,
  activeKind: "bibliographic_coupling",
  diffRoundA: null,
  diffRoundB: null,
  diffVisible: false,

  selectPaper: (id) => set({ selectedPaperId: id }),
  setActiveKind: (kind) => set({ activeKind: kind }),
  setDiffRoundA: (id) => set({ diffRoundA: id }),
  setDiffRoundB: (id) => set({ diffRoundB: id }),
  toggleDiff: () => set((s) => ({ diffVisible: !s.diffVisible })),
  closeDiff: () => set({ diffVisible: false }),
}));
