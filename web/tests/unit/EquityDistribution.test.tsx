import { fireEvent, render, screen, within } from "@testing-library/react";
import {
  EquityDistribution,
  equityColor,
  equityCurve,
  type Participant,
} from "../../src/features/equity/EquityDistribution";

const hand = (h: string, equity: number, combos: number, margin = 0, samples = 0) => ({
  hand: h, combos, equity, win: equity - 0.01, tie: 0.01, margin, samples,
});
const combo = (c: string, weight: number, equity: number, margin = 0, samples = 0) => ({
  combo: c, weight, equity, win: equity, tie: 0, margin, samples,
});

const exact: Participant = {
  equity: 0.6, win: 0.59, tie: 0.01, margin: 0,
  hands: [hand("AA", 0.8, 6), hand("KK", 0.9, 3), hand("AKs", 0.3, 3)],
  combos: [combo("AsAh", 1, 0.8), combo("KhKd", 1, 0.9), combo("AhKh", 0.5, 0.3), combo("AdKd", 1, 0.3)],
};

const mc: Participant = {
  ...exact,
  margin: 0.004,
  hands: [hand("AA", 0.8, 6, 0.01, 5000), hand("AKs", 0.3, 3, 0.031, 400)],
};

const rows = () => screen.getAllByTestId("hand-row");

describe("EquityDistribution", () => {
  it("tabela por mão ordenável por equity, com combos, win e tie", () => {
    render(<EquityDistribution participant={exact} method="exact" label="Participante 1" />);
    expect(rows().map((r) => r.dataset.hand)).toEqual(["KK", "AA", "AKs"]);
    expect(within(rows()[1]!).getByText("80,0%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Equity/ }));
    expect(rows().map((r) => r.dataset.hand)).toEqual(["AKs", "AA", "KK"]);
    expect(screen.queryByText("Amostras")).toBeNull(); // exato: sem margem/amostras
  });

  it("Monte Carlo: margem e amostras por mão, destaque acima de ±2 pp", () => {
    render(<EquityDistribution participant={mc} method="monte_carlo" label="Participante 1" />);
    expect(screen.getAllByText("Amostras").length).toBeGreaterThan(0);
    const aks = rows().find((r) => r.dataset.hand === "AKs")!;
    expect(aks.className).toContain("high-margin");
    expect(within(aks).getByText("±3,10 pp")).toBeTruthy();
    expect(rows().find((r) => r.dataset.hand === "AA")!.className).not.toContain("high-margin");
  });

  it("tabela por combo", () => {
    render(<EquityDistribution participant={exact} method="exact" label="Participante 1" />);
    fireEvent.click(screen.getByRole("button", { name: "Por combo" }));
    expect(screen.getAllByTestId("combo-row")).toHaveLength(4);
  });

  it("grade colorida pela equity média, com legenda", () => {
    const { container } = render(<EquityDistribution participant={exact} method="exact" label="P1" />);
    const kk = container.querySelector('[data-hand="KK"] rect')!;
    expect(kk.getAttribute("fill")).toBe(equityColor(0.9));
    expect(container.querySelector('[data-hand="QQ"] rect')!.getAttribute("fill")).toBe("#e6e6e6");
    expect(equityColor(0)).not.toBe(equityColor(1));
    expect(screen.getByTestId("equity-legend")).toBeTruthy();
  });

  it("curva: fração do range (por peso) com equity ≥ X", () => {
    const pts = equityCurve(exact.combos);
    // pesos 1 (0,9), 1 (0,8), 1,5 (0,3) — total 3,5
    expect(pts[0]).toEqual([0, 0.9]);
    expect(pts.at(-1)![0]).toBeCloseTo(1);
    const atLeast = (x: number) => Math.max(...pts.filter((p) => p[1] >= x).map((p) => p[0]));
    expect(atLeast(0.8)).toBeCloseTo(2 / 3.5);
    render(<EquityDistribution participant={exact} method="exact" label="P1" />);
    expect(screen.getByRole("img", { name: /Fração do range/ })).toBeTruthy();
  });
});
