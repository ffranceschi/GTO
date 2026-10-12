// Gera web/src/api/schema.d.ts a partir do OpenAPI da API local; se a API não estiver no ar,
// usa o contrato de referência specs/002-postflop-solver/contracts/openapi.yaml.
import { execFileSync } from "node:child_process";

const live = "http://127.0.0.1:8000/openapi.json";
const fallback = "../specs/002-postflop-solver/contracts/openapi.yaml";
let source = fallback;
try {
  const res = await fetch(live, { signal: AbortSignal.timeout(1500) });
  if (res.ok) source = live;
} catch {
  // API fora do ar: usa o contrato de referência
}
console.log(`gen:api usando ${source}`);
execFileSync("npx", ["openapi-typescript", source, "-o", "src/api/schema.d.ts"], { stdio: "inherit" });
