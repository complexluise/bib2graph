/**
 * client/token.ts — Lee el token Bearer inyectado por b2g gui.
 *
 * Mecanismo (B-G4-3): b2g gui reemplaza el placeholder "__B2G_TOKEN__" en el
 * index.html antes de servirlo, tanto en el script inline (window.__B2G_TOKEN__)
 * como en la meta tag <meta name="b2g-token" content="...">.
 *
 * En modo desarrollo Vite (pnpm dev), el token se pasa como variable de entorno
 * VITE_B2G_TOKEN o se deja null (la API devuelve 401 y el banner lo indica).
 */

declare global {
  interface Window {
    __B2G_TOKEN__?: string;
  }
}

/** El placeholder literal que b2g gui reemplaza en el HTML. */
const PLACEHOLDER = "__B2G_TOKEN__";

/**
 * Devuelve el token efímero generado por b2g gui, o null si no está disponible.
 *
 * Prioridad:
 * 1. window.__B2G_TOKEN__ (inyectado en el script inline del index.html)
 * 2. <meta name="b2g-token"> (fallback si la inyección fue por meta)
 * 3. import.meta.env.VITE_B2G_TOKEN (desarrollo local con Vite)
 * 4. null (sin token — la API devuelve 401)
 */
export function getToken(): string | null {
  // 1. Script inline (mecanismo principal)
  const windowToken = window.__B2G_TOKEN__;
  if (windowToken && windowToken !== PLACEHOLDER) {
    return windowToken;
  }

  // 2. Meta tag
  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="b2g-token"]'
  );
  if (meta?.content && meta.content !== PLACEHOLDER) {
    return meta.content;
  }

  // 3. Variable de entorno de Vite (solo en desarrollo)
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const envToken = (import.meta as { env?: Record<string, string> }).env?.["VITE_B2G_TOKEN"];
  if (envToken) {
    return envToken;
  }

  return null;
}
