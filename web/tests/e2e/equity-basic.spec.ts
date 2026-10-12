import { expect, test } from "@playwright/test";

const FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Equity" }).click();
});

test("AA vs KK pré-flop: 81,9% / 18,1% exato", async ({ page }) => {
  await page.getByLabel("Participante 1", { exact: true }).fill("AA");
  await page.getByLabel("Participante 2", { exact: true }).fill("KK");
  await page.getByRole("button", { name: "Calcular" }).click();
  await expect(page.getByTestId("result-kind")).toContainText("Exato", { timeout: 30_000 });
  await expect(page.getByTestId("result-1").locator(".equity-value")).toHaveText(/^81,9\d%$/);
  await expect(page.getByTestId("result-2").locator(".equity-value")).toHaveText(/^18,0\d%$/);
});

test("3 ranges amplos: Monte Carlo estimado com margem por participante", async ({ page }) => {
  await page.getByLabel("Participante 1", { exact: true }).fill(FULL);
  await page.getByLabel("Participante 2", { exact: true }).fill(FULL);
  await page.getByRole("button", { name: "Adicionar participante" }).click();
  await page.getByLabel("Participante 3", { exact: true }).fill("QQ+, AK");
  await page.getByLabel("Semente").fill("7");
  await page.getByRole("button", { name: "Calcular" }).click();
  // o progresso (amostras, margens) aparece enquanto o job roda e é trocado pelo resultado
  await expect(page.getByTestId("equity-status").or(page.getByTestId("result-kind"))).toBeVisible();
  const kind = page.getByTestId("result-kind");
  await expect(kind).toContainText("Estimado", { timeout: 90_000 });
  await expect(kind).toContainText("Semente: 7");
  for (const i of [1, 2, 3]) await expect(page.getByTestId(`result-${i}`)).toContainText(/±0,\d\d pp/);
});

test("alterar um range durante o cálculo: 'Entradas alteradas' sem recalcular", async ({ page }) => {
  for (let i = 3; i <= 6; i++) await page.getByRole("button", { name: "Adicionar participante" }).click();
  for (let i = 1; i <= 6; i++) await page.getByLabel(`Participante ${i}`, { exact: true }).fill(FULL);
  await page.getByLabel("Margem-alvo").fill("0,05");
  await page.getByRole("button", { name: "Calcular" }).click();
  await expect(page.getByTestId("equity-status").or(page.getByTestId("result-kind"))).toBeVisible();
  await page.getByLabel("Participante 1", { exact: true }).fill("AA");
  await expect(page.getByTestId("stale")).toHaveText(/Entradas alteradas/);
  await expect(page.getByTestId("result-kind")).toHaveCount(0);
  // cancelado (ou já concluído antes da alteração): nenhum resultado das entradas antigas é exibido
  await expect(page.getByTestId("equity-status")).toHaveText(/Cancelado|Concluído/, { timeout: 5_000 });
});
