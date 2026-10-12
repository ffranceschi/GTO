import { expect, test } from "@playwright/test";

const FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Equity" }).click();
});

test("QQ+, AKs vs JJ-99 no flop Ks 7d 2c: mãos do primeiro range e grade colorida", async ({ page }) => {
  await page.getByLabel("Participante 1", { exact: true }).fill("QQ+, AKs");
  await page.getByLabel("Participante 2", { exact: true }).fill("JJ-99");
  await page.locator(".equity-form").getByLabel(/^Board/).fill("Ks 7d 2c");
  await page.getByRole("button", { name: "Calcular" }).click();
  await expect(page.getByTestId("result-kind")).toContainText("Exato", { timeout: 30_000 });

  const dist = page.getByTestId("distribution");
  await expect(dist).toContainText("Participante 1");
  const hands = dist.getByTestId("hand-row");
  await expect(hands).toHaveCount(4);
  await expect(hands.first()).toHaveAttribute("data-hand", "KK"); // trinca: maior equity
  const sorted = await hands.evaluateAll((rows) => rows.map((r) => (r as HTMLElement).dataset.hand));
  expect(new Set(sorted)).toEqual(new Set(["AA", "KK", "QQ", "AKs"]));
  // células do range coloridas; fora do range, cinza
  await expect(dist.locator('[data-hand="KK"] rect')).not.toHaveAttribute("fill", "#e6e6e6");
  await expect(dist.locator('[data-hand="JJ"] rect')).toHaveAttribute("fill", "#e6e6e6");
  await expect(dist.getByRole("img", { name: /Fração do range/ })).toBeVisible();

  await page.getByRole("button", { name: "Participante 2", exact: true }).click();
  await expect(dist.getByTestId("hand-row")).toHaveCount(3);
});

test("3 ranges amplos (Monte Carlo): margens e amostras por mão", async ({ page }) => {
  await page.getByLabel("Participante 1", { exact: true }).fill(FULL);
  await page.getByLabel("Participante 2", { exact: true }).fill(FULL);
  await page.getByRole("button", { name: "Adicionar participante" }).click();
  await page.getByLabel("Participante 3", { exact: true }).fill(FULL);
  await page.getByLabel("Margem-alvo").fill("1");
  await page.getByRole("button", { name: "Calcular" }).click();
  await expect(page.getByTestId("result-kind")).toContainText("Estimado", { timeout: 60_000 });
  const dist = page.getByTestId("distribution");
  await expect(dist.getByRole("columnheader", { name: "Margem" })).toBeVisible();
  await expect(dist.getByRole("columnheader", { name: "Amostras" })).toBeVisible();
  await expect(dist.getByTestId("hand-row")).toHaveCount(169);
  await expect(dist.getByTestId("hand-row").first()).toContainText(/±\d+,\d\d pp/);
  // com ±1 pp no total, há mãos com margem acima de ±2 pp destacadas
  await expect(dist.locator("tr.high-margin").first()).toBeVisible();
});
