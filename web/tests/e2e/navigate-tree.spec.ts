import { expect, test } from "@playwright/test";

test("resolve um turn pequeno e navega pela árvore com cartas", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Range OOP").fill("AA, KK, 77, AK, KQs, QJs, T9s");
  await page.getByLabel("Range IP").fill("QQ+, AK, KJ, 76s");
  await page.getByLabel("Board").fill("Ks 7d 2c Jh");
  await page.getByLabel(/Explotabilidade alvo/).fill("1");
  await page.getByLabel("Bets em todas as streets (%)").fill("75");
  await page.getByRole("button", { name: "Aplicar a todas" }).click();
  await page.getByRole("button", { name: "Resolver" }).click();
  await expect(page.getByTestId("status")).toHaveText(/Concluído|Parado/, { timeout: 60_000 });

  const nav = page.locator(".navigator");
  await nav.locator(".action-buttons").getByRole("button", { name: "Check" }).click();
  await nav.locator(".action-buttons").getByRole("button", { name: /^Bet 75%/ }).click();
  await nav.locator(".action-buttons").getByRole("button", { name: /^Call/ }).click();
  await expect(nav.locator(".card-picker")).toBeVisible();
  await expect(nav.getByRole("button", { name: "Ks", exact: true })).toBeDisabled();
  await nav.getByRole("button", { name: "Ah", exact: true }).click();
  await expect(nav.locator(".breadcrumb")).toContainText("Check › Bet 75% (7,5 bb) › Call (7,5 bb) › Ah");
  await expect(nav.locator(".node-strategy")).toBeVisible();

  await nav.locator(".breadcrumb").getByRole("button", { name: "Check", exact: true }).click();
  await expect(nav.locator(".breadcrumb")).not.toContainText("Ah");
  await expect(nav.locator(".action-buttons").getByRole("button", { name: /^Bet 75%/ })).toBeVisible();
});
