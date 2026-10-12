import { expect, test } from "@playwright/test";

test("resolve o spot de referência de river: progresso, pausa/retomada e estratégia da raiz", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Solver postflop/ })).toBeVisible();
  // spot de referência já vem preenchido; alvo baixo para dar tempo de pausar
  await page.getByLabel(/Explotabilidade alvo/).fill("0,00001");
  await page.getByLabel(/Tempo-limite/).fill("20");
  await page.getByRole("button", { name: "Resolver" }).click();

  const iterations = page.getByTestId("iterations");
  await expect(page.getByTestId("status")).toHaveText(/Rodando/, { timeout: 30_000 });
  await expect.poll(async () => Number((await iterations.textContent())?.replace(/\D/g, "") || 0)).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Pausar" }).click();
  await expect(page.getByTestId("status")).toHaveText("Pausado", { timeout: 2_000 });
  await page.getByRole("button", { name: "Retomar" }).click();
  await expect(page.getByTestId("status")).toHaveText("Rodando", { timeout: 2_000 });
  await page.getByRole("button", { name: "Parar" }).click();
  await expect(page.getByTestId("status")).toHaveText("Parado", { timeout: 10_000 });

  await expect(page.getByTestId("solution-header")).toContainText("Explotabilidade final");
  // o range OOP de referência não tem AK (A2s-AQs): AKs aparece fora do range
  await page.locator('.node-strategy [data-hand="AKs"]').click();
  await expect(page.locator(".detail")).toContainText("Fora do range");
  const aqs = page.locator('.node-strategy [data-hand="AQs"]');
  await expect(aqs.locator("rect[data-action]").first()).toBeVisible();
  await aqs.click();
  await expect(page.locator(".detail h3")).toContainText("AQs");
  await expect(page.locator(".detail tbody tr")).not.toHaveCount(0);
});
