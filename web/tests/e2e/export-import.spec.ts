import { expect, test } from "@playwright/test";

test("exporta uma solução de river, importa e confere a raiz; fixa e desafixa", async ({ page }, info) => {
  await page.goto("/");
  await page.getByLabel("Range OOP").fill("AA, KK, 77, AK, KQs, QJs, T9s");
  await page.getByLabel("Range IP").fill("QQ+, AK, KJ, 76s");
  await page.getByLabel("Pote (bb)").fill(String(20 + Math.floor(Math.random() * 1000) / 100)); // spot único
  await page.getByLabel(/Explotabilidade alvo/).fill("1");
  await page.getByRole("button", { name: "Resolver" }).click();
  await expect(page.getByTestId("status")).toHaveText(/Concluído/, { timeout: 60_000 });

  await page.getByRole("tab", { name: "Soluções" }).click();
  const main = page.locator("main", { hasText: "Soluções salvas" });
  const row = main.locator("tbody tr").first();
  await row.getByRole("button", { name: "Abrir" }).click();
  const header = main.getByTestId("solution-header");
  await expect(header).toContainText("Explotabilidade final");
  const original = await header.textContent();
  const freqs = async () => main.locator("table.actions tbody").textContent();
  const originalFreqs = await freqs();

  await row.getByRole("button", { name: "Exportar" }).click();
  const link = row.getByRole("link", { name: "Baixar .npz" });
  await expect(link).toBeVisible({ timeout: 30_000 });
  const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
  const file = info.outputPath("solucao.npz");
  await download.saveAs(file);

  await main.getByLabel("Importar solução (.npz)").setInputFiles(file);
  await expect(main.getByTestId("import-msg")).toHaveText("Solução importada.", { timeout: 30_000 });
  await expect(header).toHaveText(original!);
  await expect.poll(freqs).toBe(originalFreqs);
  await expect(main.locator("tbody tr", { hasText: "importada" }).first()).toBeVisible();

  await row.getByRole("button", { name: "Fixar" }).click();
  await expect(row.locator("td").nth(5)).toHaveText("fixada");
  await row.getByRole("button", { name: "Desafixar" }).click();
  await expect(row.locator("td").nth(5)).toHaveText("em 30 dias");
});
