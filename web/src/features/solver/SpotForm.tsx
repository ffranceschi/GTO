import { useState } from "react";
import type { Schemas } from "../../api/client";
import { RangeEditor } from "../../components/RangeEditor/RangeEditor";
import { t } from "../../i18n/pt-BR";
import { TreeConfigEditor } from "./TreeConfigEditor";
import { boardCards, defaultTimeLimit, toSpot, type SpotFormState } from "./types";

type Props = {
  value: SpotFormState;
  onChange: (v: SpotFormState) => void;
  onSubmit: () => void;
  errors: Record<string, string>;
  busy: boolean;
};

function RangeField(props: { label: string; value: string; board: string[]; onChange: (v: string) => void; error?: string }) {
  return (
    <div className="range-field">
      <RangeEditor
        label={props.label}
        value={props.value}
        onChange={props.onChange}
        deadCards={props.board.length <= 5 ? props.board : []}
        savedRanges
      />
      {props.error && <small className="error">{props.error}</small>}
    </div>
  );
}

export function SpotForm({ value, onChange, onSubmit, errors, busy }: Props) {
  const set = (k: keyof SpotFormState) => (v: string) => onChange({ ...value, [k]: v });
  const [estimate, setEstimate] = useState<Schemas["TreeEstimate"] | null>(null);
  const overLimit = estimate !== null && !estimate.within_limit;
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
      <TreeConfigEditor
        value={value.tree}
        onChange={(tree) => onChange({ ...value, tree })}
        spot={toSpot(value)}
        onEstimate={setEstimate}
      />
      {errors._ && <p className="error">{errors._}</p>}
      <button type="submit" disabled={busy || overLimit || cards.length < 3 || cards.length > 5}>
        {t.spot.solve}
      </button>
    </form>
  );
}
