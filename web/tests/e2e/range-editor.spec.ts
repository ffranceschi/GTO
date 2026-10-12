import { expect, test, type Locator, type Page } from "@playwright/test";

const P1 = (page: Page) => page.getByTestId("participant-1");
const box = (page: Page) => page.getByLabel("Participante 1", { exact: true });

async function center(l: Locator) {
  const b = (await l.boundingBox())!;
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Equity" }).click();
  await box(page).fill("");
  await expect(P1(page).getByTestId("combo-count")).toHaveText(/^0,0 combos/);
});

test("monta 22+, A2s+, KTo+ só pela grade: texto canônico e 162 combos (12,2%)", async ({ page }) => {
  const cell = (h: string) => P1(page).locator(`[data-hand="${h}"]`);
  // arrasto na linha dos suited de ás: AKs → A2s
  const from = await center(cell("AKs"));
  const to = await center(cell("A2s"));
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 24 });
  await page.mouse.up();
  for (const h of ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22", "KQo", "KJo", "KTo"]) {
    await cell(h).click();
  }
  await expect(box(page)).toHaveValue("22+, A2s+, KTo+");
  await expect(P1(page).getByTestId("combo-count")).toHaveText("162,0 combos (12,2%)");
});

test("board As 7d 2c com AA ⇒ 3 combos", async ({ page }) => {
  await box(page).fill("AA");
  await expect(P1(page).getByTestId("combo-count")).toHaveText(/^6,0 combos/);
  await page.locator(".equity-form").getByLabel(/^Board/).fill("As 7d 2c");
  await expect(P1(page).getByTestId("combo-count")).toHaveText(/^3,0 combos/);
});

test("detalhe de AKs: desmarcar AsKs ⇒ AhKh, AdKd, AcKc", async ({ page }) => {
  await P1(page).locator('[data-hand="AKs"]').click();
  await expect(box(page)).toHaveValue("AKs");
  await expect(P1(page).getByTestId("cell-detail").locator("tbody tr")).toHaveCount(4);
  await P1(page).getByLabel("Peso de AsKs (%)").fill("0");
  await expect(box(page)).toHaveValue("AhKh, AdKd, AcKc");
  await expect(P1(page).getByTestId("combo-count")).toHaveText(/^3,0 combos/);
});
