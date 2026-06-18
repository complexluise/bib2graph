/**
 * lib/cytoscapeStyle.ts — Estilos de Cytoscape para la dirección D-2 "Observatorio".
 *
 * Reglas de diseño:
 * - Color del nodo = comunidad (paleta protagonist desde design tokens).
 * - Tamaño del nodo = degree_centrality (hubs más grandes, visible).
 * - Bordes/aristas: peso → opacidad, sin sobrecargar.
 * - El fondo es oscuro; los nodos brillan, la UI alrededor es silenciosa.
 */

import type { StylesheetStyle } from "cytoscape";
import type { CurationStatus } from "@/types/api";

/** Paleta de comunidades: índice → color hex (espeja los design tokens). */
export const COMMUNITY_COLORS: readonly string[] = [
  "#4fc3f7", // community-0: cyan
  "#a5d6a7", // community-1: verde
  "#ffb74d", // community-2: naranja
  "#ce93d8", // community-3: violeta
  "#ef9a9a", // community-4: rojo suave
  "#80cbc4", // community-5: teal
  "#fff176", // community-6: amarillo
  "#b0bec5", // community-7: gris azulado
] as const;

/** Colores de curación para anillo exterior (borde del nodo).
 *  Fuente única: deben coincidir con `theme.colors.curation` de tailwind.config.js. */
export const CURATION_BORDER: Record<CurationStatus, string> = {
  accepted:  "#4caf50",
  rejected:  "#f44336",
  candidate: "#607d8b",
};

/** Devuelve el color de la comunidad (modulo sobre la paleta). */
export function communityColor(community: number | undefined): string {
  if (community == null) return "#5c86e8"; // action.primary
  const color = COMMUNITY_COLORS[community % COMMUNITY_COLORS.length];
  return color ?? "#5c86e8";
}

/** Escala el degree_centrality [0,1] a un rango de tamaño de nodo en px. */
export function nodeSize(dc: number): number {
  const MIN = 12;
  const MAX = 48;
  return MIN + dc * (MAX - MIN);
}

/** Estilos Cytoscape para la dirección "Observatorio". */
export const graphStyles: StylesheetStyle[] = [
  {
    selector: "node",
    style: {
      "background-color": "#5c86e8",
      "width": 20,
      "height": 20,
      "border-width": 2,
      "border-color": "#252934",
      "label": "data(label)",
      "font-size": "9px",
      "font-family": "Inter, system-ui, sans-serif",
      "color": "#e8eaf0",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 3,
      "text-max-width": "80px",
      "text-wrap": "ellipsis",
      "overlay-opacity": 0,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#c5cfe8",
      "overlay-color": "#c5cfe8",
      "overlay-opacity": 0.1,
    },
  },
  {
    selector: "node.hovered",
    style: {
      "border-color": "#e8eaf0",
      "overlay-opacity": 0.08,
    },
  },
  {
    selector: "node.is-seed",
    style: {
      "border-color": "#ffd54f",
      "border-width": 2.5,
    },
  },
  {
    selector: "edge",
    style: {
      "line-color": "#252934",
      "width": 1,
      "opacity": 0.6,
      "curve-style": "bezier",
      "overlay-opacity": 0,
    },
  },
  {
    selector: "edge:selected",
    style: {
      "line-color": "#5c86e8",
      "opacity": 1,
      "width": 2,
    },
  },
];
