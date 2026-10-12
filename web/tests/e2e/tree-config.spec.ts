import { expect, test } from "@playwright/test";

const FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32";

test("árvore customizada no river: ações conferem com a configuração", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Range OOP").fill("AA, KK, 77, AK, KQs, QJs, T9s");
  await page.getByLabel("Range IP").fill("QQ+, AK, KJ, 76s");
  await page.getByLabel("Bets em todas as streets (%)").fill("50");
  await page.getByLabel("Raises em todas as streets (%)").fill("100");
  await page.getByRole("button", { name: "Aplicar a todas" }).click();
  await page.getByLabel(/Limite de raises/).fill("1");
  await expect(page.getByTestId("estimate")).toContainText("Dentro do limite");
  await page.getByRole("button", { name: "Resolver" }).click();
  await expect(page.getByTestId("status")).toHaveText(/Concluído|Parado/, { timeout: 60_000 });

  const nav = page.locator(".navigator .action-buttons");
  await expect(nav.getByRole("button")).toHaveText(["Check", "Bet 50% (5 bb)"]);
  await nav.getByRole("button", { name: /^Bet 50%/ }).click();
  await expect(nav.getByRole("button")).toHaveText(["Fold", "Call (5 bb)", /^Raise 100%/]);
  await nav.getByRole("button", { name: /^Raise 100%/ }).click();
  await expect(nav.getByRole("button")).toHaveText(["Fold", /^Call/]); // limite de 1 raise
});

test("árvore padrão de flop: estimativa acima do limite bloqueia o Resolver com sugestões", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Range OOP").fill(FULL);
  await page.getByLabel("Range IP").fill(FULL);
  await page.getByLabel("Board").fill("Ks 7d 2c");
  await page.getByLabel("Pote (bb)").fill("6");
  await page.getByLabel("Stack efetivo (bb)").fill("97");
  await expect(page.getByTestId("estimate-over")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("estimate-over")).toContainText("Reduza o limite de raises");
  await expect(page.getByRole("button", { name: "Resolver" })).toBeDisabled();
});

test("salvar, carregar e excluir uma configuração nomeada", async ({ page }) => {
  const nome = `E2E ${Date.now()}`;
  await page.goto("/");
  page.on("dialog", (d) => d.accept());
  await page.getByLabel("Bets em todas as streets (%)").fill("66");
  await page.getByRole("button", { name: "Aplicar a todas" }).click();
  await page.getByLabel("Nome da configuração").fill(nome);
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByText("Configuração salva.")).toBeVisible();
  await page.getByLabel("Configurações salvas").selectOption({ label: "Padrão (padrão)" });
  await expect(page.getByLabel("Bets River OOP")).toHaveValue("33, 75");
  await page.getByLabel("Configurações salvas").selectOption({ label: nome });
  await expect(page.getByLabel("Bets River OOP")).toHaveValue("66");
  await page.getByRole("button", { name: "Excluir" }).click();
  await expect(page.getByLabel("Configurações salvas").locator("option", { hasText: nome })).toHaveCount(0);
});
