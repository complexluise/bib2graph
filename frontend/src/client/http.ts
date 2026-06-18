/**
 * client/http.ts — Capa base de fetch para la API bib2graph.
 *
 * Responsabilidades:
 * - Añade Authorization: Bearer <token> a cada request.
 * - Valida que el envelope sea schema="1".
 * - Des-envuelve data del envelope en el camino feliz.
 * - Lanza ApiError con code STRING ante error !== null.
 * - Maneja 401 (sin token / token inválido) aparte del envelope estándar.
 */

import type { Envelope } from "@/types/api";
import { getToken } from "./token";

// ---------------------------------------------------------------------------
// ApiError — error.code es STRING (no number)
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  /** Código string del contrato: "DATA_ERROR" | "USAGE_ERROR" | etc. */
  readonly code: string;
  readonly exitCode: number;

  constructor(code: string, message: string, exitCode = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.exitCode = exitCode;
  }
}

export class AuthError extends Error {
  constructor() {
    super("No autorizado: token faltante o inválido (401)");
    this.name = "AuthError";
  }
}

// ---------------------------------------------------------------------------
// apiFetch — función base
// ---------------------------------------------------------------------------

/** Base URL de la API — misma origen en producción, proxy en dev. */
const BASE_URL = "";

/**
 * Realiza un fetch a la API, añade el Bearer y des-envuelve el envelope.
 *
 * @param path - Ruta relativa (p. ej. "/api/workspace").
 * @param init - Opciones de fetch estándar (method, body, etc.).
 * @returns El campo `data` del envelope tipado como T.
 * @throws AuthError si el servidor responde 401.
 * @throws ApiError si el envelope trae error !== null.
 * @throws Error si el envelope no es schema="1" o hay error de red.
 */
export async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
  });

  // 401 es del adaptador HTTP (sin token / token inválido), NO del envelope
  if (response.status === 401) {
    throw new AuthError();
  }

  const envelope = (await response.json()) as Envelope<T>;

  // Validar que sea el contrato esperado
  if (envelope.schema !== "1") {
    throw new Error(
      `Envelope inesperado: schema="${envelope.schema}" (esperado "1")`
    );
  }

  // error !== null → lanzar ApiError con code STRING
  if (envelope.error !== null) {
    throw new ApiError(
      envelope.error.code,
      envelope.error.message,
      envelope.exit_code
    );
  }

  return envelope.data;
}
