/**
 * lib/format.ts — Funciones de formato para la UI.
 */

/** Trunca un string a maxLen caracteres con ellipsis. */
export function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "…";
}

/** Formatea una fecha ISO a "DD MMM YYYY". */
export function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

/** Formatea un número con separador de miles. */
export function formatCount(n: number): string {
  return n.toLocaleString("es-AR");
}

/** Formatea un float a N decimales, con fallback "-". */
export function formatFloat(n: number | null | undefined, decimals = 3): string {
  if (n == null || isNaN(n)) return "-";
  return n.toFixed(decimals);
}

/** Nombre legible del NetworkKind para la UI. */
export const KIND_LABELS: Record<string, string> = {
  bibliographic_coupling: "Acoplamiento",
  cocitation:             "Co-citación",
  author_collab:          "Colaboración",
  institution_collab:     "Instituciones",
  keyword_cooccurrence:   "Keywords",
};

/** Etiqueta corta del CurationStatus para badges. */
export const STATUS_LABELS: Record<string, string> = {
  candidate: "candidato",
  accepted:  "aceptado",
  rejected:  "rechazado",
};
