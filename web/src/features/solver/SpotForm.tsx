import { useEffect, useState } from "react";
import { api, problemMessage } from "../../api/client";
import { RangeGrid, type CellData } from "../../components/RangeGrid/RangeGrid";
import { formatNumber, formatPct } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import { boardCards, defaultTimeLimit, type SpotFormState } from "./types";

type Props = {
  value: SpotFormState;
  onChange: (v: SpotFormState) => void;
  onSubmit: () => void;
  errors: Record<string, string>;
  busy: boolean;
};

const RANK_ORDER = "AKQJT98765432";
const SUITS = "shdc";

/** Pesos (1326) → células da grade, só para exibição. */
function cellsFromWeights(weights: number[]): Record<string, CellData> {
  const acc: Record<string, { w: number; n: number }> = {};
  let k = 0;
  const cards: string[] = [];
  for (let r = 0; r < 13; r++) for (let s = 0; s < 4; s++) cards.push("23456789TJQKA"[r]! + SUITS[s]!);
  for (let a = 0; a < 52; a++) {
    for (let b = a + 1; b < 52; b++) {
      const w = weights[k++] ?? 0;
      const [c1, c2] = [cards[a]!, cards[b]!];
      const hi = RANK_ORDER.indexOf(c1[0]!) < RANK_ORDER.indexOf(c2[0]!) ? c1 : c2;
      const lo = hi === c1 ? c2 : c1;
      const hand = hi[0] === lo[0] ? hi[0]! + lo[0]! : hi[0]! + lo[0]! + (hi[1] === lo[1] ? "s" : "o");
      const e = (acc[hand] ??= { w: 0, n: 0 });
      e.w += w;
      e.n += 1;
    }
  }
  const out: Record<string, CellData> = {};
  for (const [h, { w, n }] of Object.entries(acc)) out[h] = { frequencies: [w > 0 ? 1 : 0], weight: w / n };
  return out;
}

function RangeField(props: { label: string; value: string; board: string[]; onChange: (v: string) => void; error?: string }) {
  const [info, setInfo] = useState<{ combos: number; pct: number; weights: number[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const id = setTimeout(async () => {
      const { data, error } = await api.POST("/ranges/parse", {
        body: { notation: props.value, board: props.board.length <= 5 ? props.board : [] },
      });
      if (error) {
        setErr(problemMessage(error));
        setInfo(null);
      } else if (data) {
        setErr(null);
        setInfo({ combos: data.combos_after_board, pct: data.pct_of_total, weights: data.weights });
      }
    }, 250);
    return () => clearTimeout(id);
  }, [props.value, props.board.join(" ")]);
  return (
    <fieldset className="range-field">
      <label>
        {props.label}
        <textarea value={props.value} onChange={(e) => props.onChange(e.target.value)} rows={3} />
      </label>
      {info && <small>{t.spot.combos(formatNumber(info.combos, 1), formatPct(info.pct))}</small>}
      {(err ?? props.error) && <small className="error">{err ?? props.error}</small>}
      {info && (
        <RangeGrid cells={cellsFromWeights(info.weights)} actions={[{ id: "in", kind: "check", label: "No range" }]} size={260} />
      )}
    </fieldset>
  );
}

export function SpotForm({ value, onChange, onSubmit, errors, busy }: Props) {
  const set = (k: keyof SpotFormState) => (v: string) => onChange({ ...value, [k]: v });
  const cards = boardCards(value.board);
  return (
    <form
      className="spot-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <h2>{t.spot.title}</h2>
      <div className="ranges">
        <RangeField label={t.spot.oopRange} value={value.oopRange} board={cards} onChange={set("oopRange")} error={errors["spot.oop_range"]} />
        <RangeField label={t.spot.ipRange} value={value.ipRange} board={cards} onChange={set("ipRange")} error={errors["spot.ip_range"]} />
      </div>
      <label>
        {t.spot.board}
        <input value={value.board} onChange={(e) => set("board")(e.target.value)} placeholder="Ks 7d 2c Jh 3s" />
      </label>
      {(cards.length < 3 || cards.length > 5) && <small className="warn">{t.spot.boardSize}</small>}
      {errors["spot.board"] && <small className="error">{errors["spot.board"]}</small>}
      <div className="row">
        <label>
          {t.spot.pot}
          <input value={value.pot} onChange={(e) => set("pot")(e.target.value)} inputMode="decimal" />
          {errors["spot.pot"] && <small className="error">{errors["spot.pot"]}</small>}
        </label>
        <label>
          {t.spot.stack}
          <input value={value.stack} onChange={(e) => set("stack")(e.target.value)} inputMode="decimal" />
          {errors["spot.effective_stack"] && <small className="error">{errors["spot.effective_stack"]}</small>}
        </label>
        <label>
          {t.spot.target}
          <input value={value.target} onChange={(e) => set("target")(e.target.value)} inputMode="decimal" />
        </label>
        <label>
          {t.spot.timeLimit}
          <input
            value={value.timeLimit}
            placeholder={String(defaultTimeLimit(cards.length))}
            onChange={(e) => set("timeLimit")(e.target.value)}
            inputMode="decimal"
          />
        </label>
      </div>
      <details>
        <summary>{t.spot.tree}</summary>
        <p>{t.spot.treeDefault}</p>
        <label>
          {t.spot.betSizes}
          <input value={value.bets} onChange={(e) => set("bets")(e.target.value)} />
        </label>
        <label>
          {t.spot.raiseSizes}
          <input value={value.raises} onChange={(e) => set("raises")(e.target.value)} />
        </label>
      </details>
      {errors._ && <p className="error">{errors._}</p>}
      <button type="submit" disabled={busy || cards.length < 3 || cards.length > 5}>
        {t.spot.solve}
      </button>
    </form>
  );
}
