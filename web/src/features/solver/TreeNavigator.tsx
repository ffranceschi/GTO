import { useMemo, useState } from "react";
import type { NodeView } from "../../api/client";
import { RANKS, RangeGrid, type CellData } from "../../components/RangeGrid/RangeGrid";
import { formatBb, formatNumber, formatPct, formatPctValue } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import { NodeStrategyView, cellOf, useNodeView } from "./NodeStrategy";

const SUITS = ["s", "h", "d", "c"] as const;
const SUIT_SYMBOL: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };

/** Pesos (1326, ordem do motor) → células da grade. */
function cellsFromRange(weights: number[]): Record<string, CellData> {
  const acc: Record<string, { w: number; n: number }> = {};
  const cards: string[] = [];
  for (let r = 0; r < 13; r++) for (const s of SUITS) cards.push("23456789TJQKA"[r]! + s);
  let k = 0;
  for (let a = 0; a < 52; a++) {
    for (let b = a + 1; b < 52; b++) {
      const w = weights[k++] ?? 0;
      const hand = cellOf(cards[b]! + cards[a]!);
      const e = (acc[hand] ??= { w: 0, n: 0 });
      e.w += w;
      e.n += 1;
    }
  }
  const out: Record<string, CellData> = {};
  for (const [h, { w, n }] of Object.entries(acc)) out[h] = { frequencies: [w > 0 ? 1 : 0], weight: w / n };
  return out;
}

function CardPicker({ available, onPick }: { available: string[]; onPick: (c: string) => void }) {
  const set = new Set(available);
  return (
    <div className="card-picker" role="group" aria-label={t.nav.chooseCard}>
      <p>{t.nav.chooseCard}</p>
      {SUITS.map((s) => (
        <div key={s} className="card-row">
          {RANKS.map((r) => {
            const card = r + s;
            return (
              <button
                key={card}
                type="button"
                className={`card suit-${s}`}
                disabled={!set.has(card)}
                onClick={() => onPick(card)}
                aria-label={card}
              >
                {r}
                {SUIT_SYMBOL[s]}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TerminalView({ view }: { view: NodeView }) {
  const term = view.terminal!;
  return (
    <section className="terminal" data-testid="terminal">
      <h3>{t.nav.terminal[term.kind ?? "showdown"]}</h3>
      <p>{t.nav.expected}</p>
      <div className="terminal-results">
        {(term.results ?? []).map((r, i) => (
          <table key={r.player ?? i}>
            <caption>{(r.player ?? "").toUpperCase()}</caption>
            <thead>
              <tr>
                <th>{t.node.combo}</th>
                <th>{t.node.ev}</th>
                <th>{t.node.equity}</th>
              </tr>
            </thead>
            <tbody>
              {(r.combos ?? []).map((c) => (
                <tr key={c.combo}>
                  <td>{c.combo}</td>
                  <td>{formatBb(c.ev_bb)}</td>
                  <td>{formatPct(c.equity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
    </section>
  );
}

export function TreeNavigator({ solveId }: { solveId: string }) {
  const [path, setPath] = useState<string[]>([]);
  const { view, error } = useNodeView(solveId, path.join("/"));
  const ranges = useMemo(
    () => (view?.ranges ?? []).map((r) => ({ player: r.player, combos: r.combos, cells: cellsFromRange(r.weights) })),
    [view],
  );
  const go = (step: string) => setPath((p) => [...p, step]);
  const sol = view?.solution;

  return (
    <section className="navigator">
      {sol && (
        <p className="solution-header" data-testid="solution-header">
          {t.node.solutionHeader(
            sol.exploitability_pct == null ? "—" : `${formatPctValue(sol.exploitability_pct, 3)} do pote`,
            sol.iterations ?? 0,
            t.node.stopReason[sol.stop_reason ?? ""] ?? "",
          )}
        </p>
      )}
      <nav className="breadcrumb" aria-label="Caminho">
        <button type="button" onClick={() => setPath([])} aria-current={path.length === 0}>
          {t.nav.root}
        </button>
        {(view?.breadcrumb ?? []).map((label, i) => (
          <span key={i}>
            {" › "}
            <button type="button" onClick={() => setPath(path.slice(0, i + 1))} aria-current={i === path.length - 1}>
              {label}
            </button>
          </span>
        ))}
      </nav>
      {error && <p className="error">{error}</p>}
      {view && (
        <>
          <p>
            Pote {formatBb(view.pot)} · {t.nav.stacks(formatBb(view.stacks.oop ?? 0), formatBb(view.stacks.ip ?? 0))}
          </p>
          {view.kind === "decision" && (
            <>
              <div className="action-buttons">
                {(view.actions ?? []).map((a) => (
                  <button key={a.id} type="button" onClick={() => go(a.id)}>
                    {a.label}
                  </button>
                ))}
              </div>
              <NodeStrategyView key={path.join("/")} view={view} showHeader={false} />
            </>
          )}
          {view.kind === "chance" && <CardPicker available={view.next_cards ?? []} onPick={go} />}
          {view.kind === "terminal" && <TerminalView view={view} />}
          <details className="ranges-at-node">
            <summary>{t.nav.rangesTitle}</summary>
            <div className="ranges">
              {ranges.map((r) => (
                <figure key={r.player}>
                  <figcaption>
                    {r.player.toUpperCase()} · {formatNumber(r.combos, 1)} combos
                  </figcaption>
                  <RangeGrid cells={r.cells} actions={[{ id: "in", kind: "check", label: "No range" }]} size={260} />
                </figure>
              ))}
            </div>
          </details>
        </>
      )}
    </section>
  );
}

