/**
 * Tests del cliente HTTP — contrato costura cliente↔API.
 *
 * Cobertura (docs/ROADMAP/05-gui.md §Tests G4):
 * 1. apiFetch des-envuelve data de un envelope schema="1" válido.
 * 2. apiFetch lanza ApiError con code STRING ante error !== null.
 * 3. apiFetch manda el header Authorization: Bearer <token>.
 * 4. apiFetch lanza AuthError ante 401.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { ApiError, AuthError, apiFetch } from "@/client/http";

// ---------------------------------------------------------------------------
// Mock del token
// ---------------------------------------------------------------------------

vi.mock("@/client/token", () => ({
  getToken: () => "test-token-12345",
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response);
}

function envelopeResponse<T>(data: T, status = 200): Response {
  return new Response(
    JSON.stringify({
      schema: "1",
      ok: true,
      command: "test",
      exit_code: 0,
      data,
      warnings: [],
      error: null,
    }),
    { status, headers: { "Content-Type": "application/json" } }
  );
}

function errorEnvelopeResponse(
  code: string,
  message: string,
  exitCode = 2
): Response {
  return new Response(
    JSON.stringify({
      schema: "1",
      ok: false,
      command: "test",
      exit_code: exitCode,
      data: {},
      warnings: [],
      error: { code, message },
    }),
    { status: 422, headers: { "Content-Type": "application/json" } }
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("apiFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("des-envuelve data de un envelope schema='1' válido", async () => {
    const payload = { name: "mi-workspace", total_papers: 42 };
    mockFetch(envelopeResponse(payload));

    const result = await apiFetch<typeof payload>("/api/workspace");

    expect(result).toEqual(payload);
    expect(result.total_papers).toBe(42);
  });

  it("lanza ApiError con code STRING cuando error !== null", async () => {
    mockFetch(errorEnvelopeResponse("DATA_ERROR", "El paper no existe", 2));

    await expect(apiFetch("/api/paper/no-existe")).rejects.toThrow(ApiError);

    mockFetch(errorEnvelopeResponse("INTERNAL_ERROR", "Bug interno", 0));
    let caught: unknown = null;
    try {
      await apiFetch("/api/test");
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(ApiError);
    const apiErr = caught as ApiError;
    // code es STRING, no number
    expect(typeof apiErr.code).toBe("string");
    expect(apiErr.code).toBe("INTERNAL_ERROR");
  });

  it("manda el header Authorization: Bearer <token>", async () => {
    const payload = { rounds: [] };
    const fetchSpy = mockFetch(envelopeResponse(payload));

    await apiFetch<typeof payload>("/api/rounds");

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    const headers = init?.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer test-token-12345");
  });

  it("lanza AuthError ante respuesta 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 401 })
    );

    await expect(apiFetch("/api/workspace")).rejects.toThrow(AuthError);
  });

  it("lanza Error si el envelope no es schema='1'", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({ schema: "2", ok: true, data: {}, error: null }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    await expect(apiFetch("/api/workspace")).rejects.toThrow(
      /schema.*"2".*esperado "1"/
    );
  });
});

describe("ApiError", () => {
  it("preserva code como string y message", () => {
    const err = new ApiError("DATA_ERROR", "no existe", 2);
    expect(err.code).toBe("DATA_ERROR");
    expect(typeof err.code).toBe("string");
    expect(err.message).toBe("no existe");
    expect(err.exitCode).toBe(2);
    expect(err).toBeInstanceOf(Error);
  });

  it("code nunca es number (regresión vs mock antiguo)", () => {
    // El mock antiguo tipaba code: number — esto fue el drift identificado.
    const err = new ApiError("USAGE_ERROR", "uso incorrecto", 1);
    expect(typeof err.code).toBe("string");
    // @ts-expect-error — intento de asignar number a string: el tipo previene esto
    const _coercion: number = err.code;
    void _coercion; // silenciar unused
  });
});
