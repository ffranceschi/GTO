// Cliente REST tipado (openapi-fetch sobre o schema gerado do OpenAPI).
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "/api/v1" });

export type Schemas = components["schemas"];
export type Solve = Schemas["Solve"];
export type NodeView = Schemas["NodeView"];
export type Problem = Schemas["Problem"];

/** Extrai a mensagem pt-BR de um erro RFC 9457. */
export function problemMessage(error: unknown): string {
  const p = error as Partial<Problem> | undefined;
  if (p?.detail) {
    const fields = (p.errors ?? []).map((e) => `${e.field}: ${e.detail}`).join("; ");
    return fields ? `${p.detail} (${fields})` : p.detail;
  }
  return "Erro inesperado.";
}
