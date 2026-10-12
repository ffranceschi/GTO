import { fireEvent, render } from "@testing-library/react";
import { RangeGrid, actionColors, handAt } from "../../src/components/RangeGrid/RangeGrid";

const actions = [
  { id: "x", kind: "check", label: "Check" },
  { id: "b33", kind: "bet", label: "Bet 33% (3,3 bb)" },
  { id: "b75", kind: "bet", label: "Bet 75% (7,5 bb)" },
];

describe("RangeGrid", () => {
  it("ordem A..2, pares na diagonal, suited acima e offsuit abaixo", () => {
    expect(handAt(0, 0)).toBe("AA");
    expect(handAt(0, 1)).toBe("AKs");
    expect(handAt(1, 0)).toBe("AKo");
    expect(handAt(12, 12)).toBe("22");
    expect(handAt(3, 4)).toBe("JTs");
  });

  it("divide a célula em faixas proporcionais às frequências", () => {
    const { container } = render(
      <RangeGrid cells={{ AKs: { frequencies: [0.5, 0.25, 0.25], weight: 1 } }} actions={actions} size={130} />,
    );
    const cell = container.querySelector('[data-hand="AKs"]')!;
    const bars = Array.from(cell.querySelectorAll("rect[data-action]"));
    expect(bars.map((b) => Number(b.getAttribute("width")))).toEqual([5, 2.5, 2.5]);
  });

  it("cores fixas por tipo e legenda", () => {
    const colors = actionColors(actions);
    expect(colors[0]).toBe("#3fb27f");
    expect(colors[1]).not.toBe(colors[2]);
    const { getByText } = render(<RangeGrid cells={{}} actions={actions} />);
    expect(getByText("Bet 75% (7,5 bb)")).toBeTruthy();
  });

  it("seleciona célula por clique", () => {
    const onSelect = vi.fn();
    const { container } = render(<RangeGrid cells={{}} actions={actions} onSelect={onSelect} />);
    fireEvent.click(container.querySelector('[data-hand="QQ"]')!);
    expect(onSelect).toHaveBeenCalledWith("QQ");
  });
});
