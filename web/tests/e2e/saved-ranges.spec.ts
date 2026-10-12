import { expect, test } from "@playwright/test";

const NAME = "BTN open 100bb";
const BTN = "22+, A2s+, KTs+, ATo+, KQo:0.5";
const API = "http://127.0.0.1:8000/api/v1";

test.beforeEach(async ({ request }) => {
  // o banco do E2E persiste entre execuções: remove o range de execuções anteriores
  const rows = (await (await request.get(`${API}/saved-ranges`)).json()) as { id: string; name: string }[];
  for (const r of rows.filter((x) => x.name === NAME)) await request.delete(`${API}/saved-ranges/${r.id}`);
});

test("salva com KQo:0.5, recarrega e carrega igual; o mesmo range carrega no solver", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await page.goto("/");
  await page.getByRole("tab", { name: "Equity" }).click();
  const p1 = page.getByTestId("participant-1");
  const box = page.getByLabel("Participante 1", { exact: true });
  await box.fill(BTN);
  await expect(p1.getByTestId("combo-count")).toHaveText(/^\d+,\d combos/);
  const count = await p1.getByTestId("combo-count").textContent();
  await p1.getByLabel("Nome do range").fill(NAME);
  await p1.getByRole("button", { name: "Salvar range" }).click();
  await expect(p1.getByRole("status")).toHaveText(`Range "${NAME}" salvo.`);
  await expect(p1.getByLabel("Range salvo")).not.toHaveValue("");

  // salvar de novo com o mesmo nome pede confirmação (aceita) e sobrescreve
  const dialog = page.waitForEvent("dialog");
  const overwrite = page.waitForResponse(
    (r) => r.url().endsWith("/saved-ranges") && r.request().method() === "POST" && r.status() === 201,
  );
  await p1.getByRole("button", { name: "Salvar range" }).click();
  expect((await dialog).message()).toContain("Sobrescrever?");
  await overwrite;

  await page.reload();
  await page.getByRole("tab", { name: "Equity" }).click();
  const p2 = page.getByTestId("participant-2");
  await p2.getByLabel("Range salvo").selectOption({ label: NAME });
  await p2.getByRole("button", { name: "Carregar range" }).click();
  const box2 = page.getByLabel("Participante 2", { exact: true });
  await expect(box2).toHaveValue(/KQo:0\.5/);
  await expect(p2.getByTestId("combo-count")).toHaveText(count!);

  // formulário do solver (T098 da 002)
  await page.getByRole("tab", { name: "Solver" }).click();
  const oop = page.locator(".spot-form .range-field").first();
  await oop.getByLabel("Range salvo").selectOption({ label: NAME });
  await oop.getByRole("button", { name: "Carregar range" }).click();
  await expect(page.getByLabel("Range OOP", { exact: true })).toHaveValue(/KQo:0\.5/);
  await expect(oop.getByTestId("combo-count")).toBeVisible();
});
