// Grade 13x13 somente leitura (SVG): pares na diagonal, suited acima, offsuit abaixo.
// Cada célula é dividida em faixas proporcionais às frequências das ações.
import { useMemo } from "react";

export const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;

export type CellData = {
  /** frequência de cada ação (mesma ordem de `actions`), soma ≤ 1; vazio = fora do range */
  frequencies: number[];
  /** peso da célula no range (0–1), usado para a altura das faixas */
  weight: number;
};

export type GridAction = { id: string; kind: string; label: string };

export function handAt(row: number, col: number): string {
  const r1 = RANKS[row]!;
  const r2 = RANKS[col]!;
  if (row === col) return `${r1}${r2}`;
  return row < col ? `${r1}${r2}s` : `${r2}${r1}o`;
}

const PALETTE: Record<string, string> = {
  fold: "#5b8def",
  check: "#3fb27f",
  call: "#3fb27f",
  allin: "#7a1f2b",
};
const AGGR = ["#f4a261", "#e76f51", "#d1495b", "#b5179e", "#9d0208"];

/** Cor fixa por tipo de ação; bets/raises ficam mais escuras conforme o tamanho. */
export function actionColors(actions: GridAction[]): string[] {
  const aggressive = actions.filter((a) => a.kind === "bet" || a.kind === "raise");
  return actions.map((a) => {
    if (a.kind === "bet" || a.kind === "raise") {
      const i = aggressive.indexOf(a);
      return AGGR[Math.min(i, AGGR.length - 1)]!;
    }
    return PALETTE[a.kind] ?? "#999";
  });
}

type Props = {
  cells: Record<string, CellData>;
  actions: GridAction[];
  selected?: string | null;
  onSelect?: (hand: string) => void;
  size?: number;
};

export function RangeGrid({ cells, actions, selected, onSelect, size = 520 }: Props) {
  const cell = size / 13;
  const colors = useMemo(() => actionColors(actions), [actions]);
  return (
    <div className="range-grid">
      <svg width={size} height={size} role="grid" aria-label="Grade de mãos 13x13">
        {RANKS.map((_, row) =>
          RANKS.map((__, col) => {
            const hand = handAt(row, col);
            const data = cells[hand];
            const x = col * cell;
            const y = row * cell;
            const freqs = data?.frequencies ?? [];
            const inRange = !!data && data.weight > 0 && freqs.some((f) => f > 0);
            let offset = 0;
            return (
              <g
                key={hand}
                role="gridcell"
                data-hand={hand}
                aria-selected={selected === hand}
                onClick={() => onSelect?.(hand)}
                style={{ cursor: onSelect ? "pointer" : "default" }}
              >
                <rect x={x} y={y} width={cell} height={cell} fill={inRange ? "#2b2b2b" : "#d9d9d9"} />
                {inRange &&
                  freqs.map((f, i) => {
                    const w = f * cell;
                    const r = (
                      <rect
                        key={i}
                        data-action={actions[i]?.id}
                        x={x + offset}
                        y={y + cell * (1 - data.weight)}
                        width={w}
                        height={cell * data.weight}
                        fill={colors[i]}
                      />
                    );
                    offset += w;
                    return r;
                  })}
                <rect
                  x={x}
                  y={y}
                  width={cell}
                  height={cell}
                  fill="none"
                  stroke={selected === hand ? "#000" : "#fff"}
                  strokeWidth={selected === hand ? 2.5 : 0.5}
                />
                <text x={x + 3} y={y + 13} fontSize={11} fill={inRange ? "#fff" : "#666"}>
                  {hand}
                </text>
              </g>
            );
          }),
        )}
      </svg>
      <ul className="legend" aria-label="Legenda">
        {actions.map((a, i) => (
          <li key={a.id}>
            <span className="swatch" style={{ background: colors[i] }} /> {a.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
