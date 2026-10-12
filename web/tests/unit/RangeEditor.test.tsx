import { act, fireEvent, render, screen } from "@testing-library/react";
import { RangeEditor, type RangeService } from "../../src/components/RangeEditor/RangeEditor";
import { HAND_COMBOS, N_COMBOS, comboName, emptyWeights } from "../../src/components/RangeEditor/combos";

// serviço falso: "AKs" e "QQ" são as únicas notações válidas; format devolve um resumo dos pesos
function fakeService(): RangeService & { formatted: number[][] } {
  const formatted: number[][] = [];
  return {
    formatted,
    async parse(notation) {
      if (notation === "AKs" || notation === "QQ") {
        const w = emptyWeights();
        for (const k of HAND_COMBOS[notation]!) w[k] = 1;
        return { weights: w };
      }
      return { error: `Notação inválida: '${notation}' (posição 0).` };
    },
    async format(weights) {
      formatted.push(weights);
      return `fmt:${weights.filter((x) => x > 0).length}`;
    },
  };
}

const cell = (c: HTMLElement, hand: string) => c.querySelector(`[data-hand="${hand}"]`)!;
const count = () => screen.getByTestId("combo-count").textContent;

async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(400);
  });
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function setup(props: Partial<Parameters<typeof RangeEditor>[0]> = {}) {
  const service = fakeService();
  const onChange = vi.fn();
  const utils = render(
    <RangeEditor label="Range" value="" onChange={onChange} deadCards={[]} service={service} {...props} />,
  );
  return { ...utils, service, onChange };
}

describe("RangeEditor", () => {
  it("clique seleciona a célula com peso 100% e conta 4 combos para AKs; o texto vem do format", async () => {
    const { container, onChange } = setup();
    fireEvent.pointerDown(cell(container, "AKs"));
    fireEvent.pointerUp(window);
    expect(count()).toMatch(/^4,0 combos \(0,3%\)$/);
    await flush();
    expect(onChange).toHaveBeenLastCalledWith("fmt:4");
    expect(screen.getByRole("textbox", { name: "Range" })).toHaveProperty("value", "fmt:4");
  });

  it("arrasto a partir de célula vazia seleciona; a partir de célula selecionada remove (FR-006)", () => {
    const { container } = setup();
    fireEvent.pointerDown(cell(container, "AKs"));
    fireEvent.pointerEnter(cell(container, "AQs"), { buttons: 1 });
    fireEvent.pointerEnter(cell(container, "AJs"), { buttons: 1 });
    fireEvent.pointerUp(window);
    expect(count()).toMatch(/^12,0 combos/);
    fireEvent.pointerDown(cell(container, "AQs"));
    fireEvent.pointerEnter(cell(container, "AJs"), { buttons: 1 });
    fireEvent.pointerUp(window);
    expect(count()).toMatch(/^4,0 combos/);
    // sem botão pressionado, passar o mouse não altera nada
    fireEvent.pointerEnter(cell(container, "ATs"), { buttons: 0 });
    expect(count()).toMatch(/^4,0 combos/);
  });

  it("peso ativo de 50% em KQo ⇒ 6 combos e faixa com metade da altura (FR-007)", () => {
    const { container } = setup({ size: 130 });
    fireEvent.change(screen.getByLabelText("Peso ativo (%)"), { target: { value: "50" } });
    fireEvent.pointerDown(cell(container, "KQo"));
    fireEvent.pointerUp(window);
    expect(count()).toMatch(/^6,0 combos/);
    const bar = cell(container, "KQo").querySelector("rect[data-action]")!;
    expect(Number(bar.getAttribute("height"))).toBeCloseTo(5);
  });

  it("detalhe da célula: 4/6/12 combos e peso por combo (FR-008)", () => {
    const { container } = setup();
    for (const [hand, n] of [["AKs", 4], ["QQ", 6], ["AKo", 12]] as const) {
      fireEvent.pointerDown(cell(container, hand));
      fireEvent.pointerUp(window);
      expect(screen.getByTestId("cell-detail").querySelectorAll("tbody tr")).toHaveLength(n);
    }
    expect(count()).toMatch(/^22,0 combos/); // AKs + QQ + AKo
    fireEvent.pointerDown(cell(container, "AKs")); // remove
    fireEvent.pointerUp(window);
    expect(count()).toMatch(/^18,0 combos/);
    fireEvent.pointerDown(cell(container, "AKs")); // seleciona de novo e abre o detalhe
    fireEvent.pointerUp(window);
    const input = screen.getByLabelText(`Peso de ${comboName(HAND_COMBOS.AKs![0]!)} (%)`);
    fireEvent.change(input, { target: { value: "0" } });
    expect(count()).toMatch(/^21,0 combos/);
  });

  it("Limpar e Tudo (FR-010); cartas mortas descontadas da contagem (FR-011)", () => {
    const { rerender, service } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Tudo" }));
    expect(count()).toMatch(/^1\.326,0 combos \(100,0%\)$/);
    rerender(<RangeEditor label="Range" value="" onChange={() => {}} deadCards={["As", "Kd"]} service={service} />);
    expect(count()).toMatch(/^1\.225,0 combos/); // 1326 − 101 combos com As ou Kd
    fireEvent.click(screen.getByRole("button", { name: "Limpar" }));
    expect(count()).toMatch(/^0,0 combos/);
    expect(N_COMBOS).toBe(1326);
  });

  it("texto inválido mostra o trecho e não altera a grade (FR-004); texto válido atualiza a grade", async () => {
    const { container } = setup();
    const box = screen.getByRole("textbox", { name: "Range" });
    fireEvent.change(box, { target: { value: "QQ" } });
    await flush();
    expect(count()).toMatch(/^6,0 combos/);
    fireEvent.change(box, { target: { value: "AKx" } });
    await flush();
    expect(screen.getByRole("alert").textContent).toContain("'AKx'");
    expect(count()).toMatch(/^6,0 combos/);
    expect(cell(container, "QQ").querySelector("rect[data-action]")).not.toBeNull();
  });
});
