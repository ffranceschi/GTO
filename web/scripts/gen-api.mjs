// Gera web/src/api/schema.d.ts a partir do OpenAPI da API local; se a API não estiver no ar,
// usa o contrato de referência specs/002-postflop-solver/contracts/openapi.yaml.
// O OpenAPI da API traz os caminhos com /api/v1, que o cliente usa como baseUrl: o prefixo é removido.
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const live = "http://127.0.0.1:8000/openapi.json";
const fallback = "../specs/002-postflop-solver/contracts/openapi.yaml";
let source = fallback;
try {
  const res = await fetch(live, { signal: AbortSignal.timeout(1500) });
  if (res.ok) {
    const doc = await res.json();
    doc.paths = Object.fromEntries(Object.entries(doc.paths).map(([k, v]) => [k.replace(/^\/api\/v1/, ""), v]));
    source = join(mkdtempSync(join(tmpdir(), "gen-api-")), "openapi.json");
    writeFileSync(source, JSON.stringify(doc));
  }
} catch {
  // API fora do ar: usa o contrato de referência
}
console.log(`gen:api usando ${source}`);
execFileSync("npx", ["openapi-typescript", source, "--default-non-nullable", "false", "-o", "src/api/schema.d.ts"], { stdio: "inherit" });
