import { ApiError, AuthError } from "@/client/http";

interface Props {
  error: unknown;
  context?: string;
}

/**
 * Muestra errores de API con el code string del contrato.
 * No hace reset — el parent decide cómo recuperarse.
 */
export function ErrorBanner({ error, context }: Props) {
  if (!error) return null;

  let title = "Error inesperado";
  let detail = String(error);
  let code: string | null = null;

  if (error instanceof AuthError) {
    title = "Sin autorización";
    detail = "Token faltante o inválido. Reiniciá b2g gui para obtener un token nuevo.";
  } else if (error instanceof ApiError) {
    code = error.code;
    title = `Error: ${error.code}`;
    detail = error.message;
  } else if (error instanceof Error) {
    detail = error.message;
  }

  return (
    <div
      role="alert"
      className="flex flex-col gap-1 rounded-obs bg-curation-rejected/10 border border-curation-rejected/30 px-3 py-2 text-sm animate-fade-in"
    >
      <div className="flex items-center gap-2">
        <span className="text-curation-rejected font-medium">{title}</span>
        {context && (
          <span className="text-text-muted text-2xs font-mono">[{context}]</span>
        )}
      </div>
      <p className="text-text-secondary text-xs leading-relaxed">{detail}</p>
      {code && (
        <code className="text-2xs font-mono text-text-muted">code: {code}</code>
      )}
    </div>
  );
}
