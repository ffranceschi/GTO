import { useEffect, useMemo, useState } from "react";
import { api, problemMessage, type NodeView } from "../../api/client";
import { RangeGrid, actionColors, type CellData } from "../../components/RangeGrid/RangeGrid";
import { formatBb, formatNumber, formatPct, formatPctValue } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";

export function useNodeView(solveId: string, path: string) {
  const [view, setView] = useState<NodeView | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .GET("/solves/{solve_id}/nodes", { params: { path: { solve_id: solveId }, query: { path } } })
      .then(({ data, error }) => {
        if (!alive) return;
        if (error) setError(problemMessage(error));
        else setView(data ?? null);
      });
    return () => {
      alive = false;
    };
  }, [solveId, path]);
  return { view, error };
}

export function NodeStrategy({ solveId, path = "" }: { solveId: string; path?: string }) {
  const { view, error } = useNodeView(solveId, path);
  if (error) return <p className="error">{error}</p>;
  if (!view) return <p>Carregando…</p>;
  return <NodeStrategyView view={view} />;
}

export function NodeStrategyView({ view, showHeader = true }: { view: NodeView; showHeader?: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const actions = view?.actions ?? [];
  const colors = useMemo(() => actionColors(actions), [actions]);
  const cells = useMemo(() => {
    const out: Record<string, CellData> = {};
    for (const h of view?.hands ?? []) {
      const n = h.hand.length === 2 ? 6 : h.hand.endsWith("s") ? 4 : 12;
      out[h.hand] = { frequencies: actions.map((a) => h.frequencies[a.id] ?? 0), weight: Math.min(1, h.combos / n) };
    }
    return out;
  }, [view, actions]);

  const sol = view.solution;
  const hand = view.hands?.find((h) => h.hand === selected);
  const combos = (view.combos ?? []).filter((c) => selected && cellOf(c.combo) === selected);

  return (
    <section className="node-strategy">
      {showHeader && sol && (
        <p className="solution-header" data-testid="solution-header">
          {t.node.solutionHeader(
            sol.exploitability_pct == null ? "—" : `${formatPctValue(sol.exploitability_pct, 3)} do pote`,
            sol.iterations ?? 0,
            t.node.stopReason[sol.stop_reason ?? ""] ?? "",
          )}
        </p>
      )}
      <h2>
        {view.player?.toUpperCase()} · pote {formatBb(view.pot)}
      </h2>
      <table className="actions">
        <thead>
          <tr>
            <th>{t.node.actions}</th>
            <th>{t.node.frequency}</th>
            <th>{t.node.combos}</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((a, i) => (
            <tr key={a.id}>
              <td>
                <span className="swatch" style={{ background: colors[i] }} /> {a.label}
              </td>
              <td>{formatPct(a.aggregate_frequency)}</td>
              <td>{formatNumber(a.combos, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="grid-and-detail">
        <RangeGrid cells={cells} actions={actions} selected={selected} onSelect={setSelected} />
        <aside className="detail">
          {!selected && <p>{t.node.selectHand}</p>}
          {selected && (!hand || hand.combos === 0) && <p>{selected}: {t.node.outOfRange}</p>}
          {hand && hand.combos > 0 && (
            <>
              <h3>
                {hand.hand} · {formatNumber(hand.combos, 2)} combos · EV {formatBb(hand.ev_bb)} · equity {formatPct(hand.equity)}
              </h3>
              <table>
                <thead>
                  <tr>
                    <th>{t.node.combo}</th>
                    {actions.map((a) => (
                      <th key={a.id}>{a.label}</th>
                    ))}
                    <th>{t.node.ev}</th>
                    <th>{t.node.equity}</th>
                  </tr>
                </thead>
                <tbody>
                  {combos.map((c) => (
                    <tr key={c.combo} className={c.reach_weight === 0 ? "out" : ""}>
                      <td>{c.combo}</td>
                      {actions.map((a) => (
                        <td key={a.id}>{c.reach_weight === 0 ? "—" : formatPct(c.frequencies[a.id] ?? 0)}</td>
                      ))}
                      <td>{formatBb(c.ev_bb)}</td>
                      <td>{formatPct(c.equity)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

const R = "AKQJT98765432";
/** "AhKh" → "AKs" */
export function cellOf(combo: string): string {
  const [r1, s1, r2, s2] = [combo[0]!, combo[1]!, combo[2]!, combo[3]!];
  if (r1 === r2) return r1 + r2;
  const [hi, lo] = R.indexOf(r1) < R.indexOf(r2) ? [r1, r2] : [r2, r1];
  return hi + lo + (s1 === s2 ? "s" : "o");
}
