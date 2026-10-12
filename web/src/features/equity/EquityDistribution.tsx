// Distribuição de equity de um participante (US3, FR-023/FR-024): tabela por mão e por combo
// (ordenável), grade 13x13 colorida pela equity média e curva "fração do range com equity ≥ X".
import { useMemo, useState } from "react";
import type { Schemas } from "../../api/client";
import { RANKS, handAt } from "../../components/RangeGrid/RangeGrid";
import { formatMarginPp, formatNumber, formatPct } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";

export type Participant = Schemas["ParticipantResult"];
type Combo = Schemas["ComboResult"];

const HIGH_MARGIN = 0.02; // ±2 pp (FR-023)
const EMPTY = "#e6e6e6";
// escala contínua vermelho (0%) → amarelo (50%) → verde (100%)
const STOPS: [number, [number, number, number]][] = [
  [0, [215, 48, 39]],
  [0.5, [254, 224, 139]],
  [1, [26, 152, 80]],
];

export function equityColor(eq: number): string {
  const x = Math.min(1, Math.max(0, eq));
  const i = x <= 0.5 ? 0 : 1;
  const [x0, c0] = STOPS[i]!;
  const [x1, c1] = STOPS[i + 1]!;
  const f = (x - x0) / (x1 - x0);
  const rgb = c0.map((v, k) => Math.round(v + (c1[k]! - v) * f));
  return `rgb(${rgb.join(", ")})`;
}

/** Combos em ordem decrescente de equity → degraus [fração acumulada do range (por peso), equity]. */
export function equityCurve(combos: Combo[]): [number, number][] {
  const sorted = combos.filter((c) => c.weight > 0).sort((a, b) => b.equity - a.equity);
  const total = sorted.reduce((s, c) => s + c.weight, 0);
  const pts: [number, number][] = [];
  let acc = 0;
  for (const c of sorted) {
    pts.push([acc / total, c.equity]);
    acc += c.weight;
    pts.push([acc / total, c.equity]);
  }
  return pts;
}

function Curve({ combos }: { combos: Combo[] }) {
  const pts = useMemo(() => equityCurve(combos), [combos]);
  const [w, h, pad] = [320, 180, 28];
  const sx = (x: number) => pad + x * (w - pad - 8);
  const sy = (y: number) => 8 + (1 - y) * (h - pad - 8);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
  return (
    <figure className="chart">
      <figcaption>{t.distribution.curveTitle}</figcaption>
      <svg width={w} height={h} role="img" aria-label={t.distribution.curveTitle}>
        <line x1={pad} y1={sy(0)} x2={w - 8} y2={sy(0)} stroke="#999" />
        <line x1={pad} y1={sy(0)} x2={pad} y2={sy(1)} stroke="#999" />
        {[0, 0.5, 1].map((v) => (
          <text key={`y${v}`} x={2} y={sy(v) + 4} fontSize={10}>
            {formatPct(v, 0)}
          </text>
        ))}
        {[0.5, 1].map((v) => (
          <text key={`x${v}`} x={sx(v) - 14} y={h - 6} fontSize={10}>
            {formatPct(v, 0)}
          </text>
        ))}
        <path d={d} fill="none" stroke="#1f5fbf" strokeWidth={2} />
      </svg>
    </figure>
  );
}

function EquityGrid({ hands, size = 286 }: { hands: Participant["hands"]; size?: number }) {
  const by = new Map(hands.map((x) => [x.hand, x]));
  const cell = size / 13;
  return (
    <figure className="chart">
      <figcaption>{t.distribution.gridTitle}</figcaption>
      <svg width={size} height={size} role="grid" aria-label={t.distribution.gridTitle}>
        {RANKS.map((_, row) =>
          RANKS.map((__, col) => {
            const hand = handAt(row, col);
            const r = by.get(hand);
            return (
              <g key={hand} data-hand={hand}>
                <rect
                  x={col * cell}
                  y={row * cell}
                  width={cell}
                  height={cell}
                  fill={r ? equityColor(r.equity) : EMPTY}
                  stroke="#fff"
                  strokeWidth={0.5}
                >
                  {r && <title>{`${hand}: ${formatPct(r.equity, 1)}`}</title>}
                </rect>
                <text x={col * cell + 2} y={row * cell + 11} fontSize={9} fill="#333">
                  {hand}
                </text>
              </g>
            );
          }),
        )}
      </svg>
      <div className="equity-legend" data-testid="equity-legend">
        <span>0%</span>
        <span
          className="bar"
          style={{ background: `linear-gradient(to right, ${equityColor(0)}, ${equityColor(0.5)}, ${equityColor(1)})` }}
        />
        <span>100%</span>
      </div>
    </figure>
  );
}

type Props = { participant: Participant; method: "exact" | "monte_carlo"; label: string };

export function EquityDistribution({ participant, method, label }: Props) {
  const [view, setView] = useState<"hand" | "combo">("hand");
  const [desc, setDesc] = useState(true);
  const mc = method === "monte_carlo";
  const order = (a: { equity: number }, b: { equity: number }) => (desc ? b.equity - a.equity : a.equity - b.equity);
  const hands = useMemo(() => [...participant.hands].sort(order), [participant, desc]);
  const combos = useMemo(() => [...participant.combos].sort(order), [participant, desc]);
  const sortButton = (
    <button type="button" className="link" onClick={() => setDesc((d) => !d)}>
      {t.distribution.equity} {desc ? "▼" : "▲"}
    </button>
  );
  const stats = (r: { equity: number; win: number; tie: number; margin: number; samples: number }) => (
    <>
      <td>{formatPct(r.equity, 1)}</td>
      <td>{formatPct(r.win, 1)}</td>
      <td>{formatPct(r.tie, 1)}</td>
      {mc && (
        <>
          <td>{formatMarginPp(r.margin)}</td>
          <td>{formatNumber(r.samples, 0)}</td>
        </>
      )}
    </>
  );
  const head = (first: string, second: string) => (
    <tr>
      <th>{first}</th>
      <th>{second}</th>
      <th>{sortButton}</th>
      <th>{t.distribution.win}</th>
      <th>{t.distribution.tie}</th>
      {mc && (
        <>
          <th>{t.distribution.margin}</th>
          <th>{t.distribution.samples}</th>
        </>
      )}
    </tr>
  );
  return (
    <section className="progress distribution" data-testid="distribution">
      <h3>{t.distribution.title(label)}</h3>
      <div className="grid-and-detail">
        <EquityGrid hands={participant.hands} />
        <Curve combos={participant.combos} />
      </div>
      <div className="buttons">
        <button type="button" aria-pressed={view === "hand"} onClick={() => setView("hand")}>
          {t.distribution.byHand}
        </button>{" "}
        <button type="button" aria-pressed={view === "combo"} onClick={() => setView("combo")}>
          {t.distribution.byCombo}
        </button>
      </div>
      <div className="table-scroll">
        {view === "hand" ? (
          <table className="solutions">
            <thead>{head(t.distribution.hand, t.distribution.combos)}</thead>
            <tbody>
              {hands.map((r) => (
                <tr
                  key={r.hand}
                  data-testid="hand-row"
                  data-hand={r.hand}
                  className={mc && r.margin > HIGH_MARGIN ? "high-margin" : undefined}
                  title={mc && r.margin > HIGH_MARGIN ? t.distribution.highMargin : undefined}
                >
                  <td>{r.hand}</td>
                  <td>{formatNumber(r.combos, 1)}</td>
                  {stats(r)}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="solutions">
            <thead>{head(t.distribution.combo, t.distribution.weight)}</thead>
            <tbody>
              {combos.map((r) => (
                <tr
                  key={r.combo}
                  data-testid="combo-row"
                  className={mc && r.margin > HIGH_MARGIN ? "high-margin" : undefined}
                >
                  <td>{r.combo}</td>
                  <td>{formatPct(r.weight, 0)}</td>
                  {stats(r)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
