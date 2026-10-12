// Editor de range: grade 13x13 interativa + texto, sincronizados (FR-005 a FR-012, research R11).
// A grade edita os 1326 pesos no cliente; o texto canônico vem de /ranges/format e o texto digitado
// vira pesos por /ranges/parse — um único formatador/parser, o do motor (research R8).
import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { api, problemMessage } from "../../api/client";
import { formatNumber, formatPct } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import { SavedRangesMenu } from "../../features/ranges/SavedRangesMenu";
import { RangeGrid, type CellData } from "../RangeGrid/RangeGrid";
import { HAND_COMBOS, N_COMBOS, cellWeights, comboName, countCombos, deadMask, emptyWeights } from "./combos";

export type RangeService = {
  parse: (notation: string) => Promise<{ weights: number[] } | { error: string }>;
  format: (weights: number[]) => Promise<string>;
};

export const apiRangeService: RangeService = {
  async parse(notation) {
    const { data, error } = await api.POST("/ranges/parse", { body: { notation } });
    return data ? { weights: data.weights } : { error: problemMessage(error) };
  },
  async format(weights) {
    const { data } = await api.POST("/ranges/format", { body: { weights } });
    return data?.canonical ?? "";
  },
};

const DEBOUNCE_MS = 150;
const ACTIONS = [{ id: "in", kind: "check", label: t.rangeEditor.inRange }];

type Props = {
  label: string;
  value: string;
  onChange: (notation: string) => void;
  /** board + cartas das mãos específicas dos outros participantes (FR-011) */
  deadCards: string[];
  size?: number;
  service?: RangeService;
  /** mostra o menu de ranges salvos (US4) */
  savedRanges?: boolean;
};

export function RangeEditor({
  label,
  value,
  onChange,
  deadCards,
  size = 312,
  service = apiRangeService,
  savedRanges = false,
}: Props) {
  const [text, setText] = useState(value);
  const [weights, setWeightsState] = useState<number[]>(emptyWeights);
  const latest = useRef(weights); // pesos mais recentes, mesmo antes do próximo render (arrasto rápido)
  const setWeights = (w: number[]) => {
    latest.current = w;
    setWeightsState(w);
  };
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(100);
  const [detail, setDetail] = useState<string | null>(null);
  const emitted = useRef(value); // último texto informado ao pai (evita reprocessar o próprio eco)
  const onChangeRef = useRef(onChange); // o texto canônico chega depois do debounce: usa o handler atual
  onChangeRef.current = onChange;
  const drag = useRef<"select" | "remove" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0); // descarta respostas fora de ordem

  const schedule = (fn: () => Promise<void>) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void fn(), DEBOUNCE_MS);
  };

  const parseText = async (notation: string) => {
    const my = ++seq.current;
    if (!notation.trim()) {
      setWeights(emptyWeights());
      setError(null);
      return;
    }
    const r = await service.parse(notation);
    if (my !== seq.current) return;
    if ("error" in r) setError(r.error); // FR-004: a grade fica como estava
    else {
      setError(null);
      setWeights(r.weights);
    }
  };

  // texto vindo de fora (valor inicial, range salvo carregado…)
  useEffect(() => {
    if (value === emitted.current && seq.current > 0) return;
    emitted.current = value;
    setText(value);
    void parseText(value);
  }, [value]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    const up = () => (drag.current = null);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  }, []);

  const emit = (notation: string) => {
    emitted.current = notation;
    onChangeRef.current(notation);
  };

  const onText = (v: string) => {
    seq.current++; // invalida respostas de parse/format em andamento (ex.: a do valor inicial)
    setText(v);
    emit(v);
    schedule(() => parseText(v));
  };

  /** Edição pela grade: pesos na hora (contagem imediata — FR-012), texto canônico com debounce. */
  const editWeights = (next: number[]) => {
    setWeights(next);
    setError(null);
    const my = ++seq.current;
    schedule(async () => {
      const canonical = await service.format(next);
      if (my !== seq.current) return;
      setText(canonical);
      emit(canonical);
    });
  };

  const cellAvg = useMemo(() => cellWeights(weights), [weights]);
  const dead = useMemo(() => deadMask(deadCards), [deadCards.join(" ")]);
  const combos = countCombos(weights, dead);

  const applyCell = (hand: string, action: "select" | "remove") => {
    const next = latest.current.slice();
    for (const k of HAND_COMBOS[hand]!) next[k] = action === "select" ? active / 100 : 0;
    return next;
  };

  const onDown = (hand: string, e: PointerEvent) => {
    // toque: libera a captura implícita para que o arrasto alcance as outras células
    (e.target as Element).releasePointerCapture?.(e.pointerId);
    drag.current = (cellAvg[hand] ?? 0) > 0 ? "remove" : "select";
    setDetail(hand);
    editWeights(applyCell(hand, drag.current));
  };

  const onEnter = (hand: string, e: PointerEvent) => {
    if (!drag.current || e.buttons === 0) return;
    const want = drag.current === "select" ? active / 100 : 0;
    if (HAND_COMBOS[hand]!.every((k) => latest.current[k] === want)) return;
    editWeights(applyCell(hand, drag.current));
  };

  const setCombo = (k: number, pct: number) => {
    const next = latest.current.slice();
    next[k] = Math.min(100, Math.max(0, Math.round(pct))) / 100;
    editWeights(next);
  };

  const cells: Record<string, CellData> = {};
  for (const [hand, w] of Object.entries(cellAvg)) cells[hand] = { frequencies: [w > 0 ? 1 : 0], weight: w };

  return (
    <fieldset className="range-editor">
      <label>
        {label}
        <textarea aria-label={label} value={text} onChange={(e) => onText(e.target.value)} rows={2} />
      </label>
      {error && (
        <small className="error" role="alert">
          {error}
        </small>
      )}
      <small data-testid="combo-count">{t.spot.combos(formatNumber(combos, 1), formatPct(combos / N_COMBOS))}</small>
      <div className="editor-tools">
        <label className="active-weight">
          {t.rangeEditor.activeWeight}
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            value={active}
            onChange={(e) => setActive(Math.min(100, Math.max(0, Math.round(Number(e.target.value) || 0))))}
          />
        </label>
        <button type="button" onClick={() => editWeights(emptyWeights())}>
          {t.rangeEditor.clear}
        </button>
        <button type="button" onClick={() => editWeights(new Array<number>(N_COMBOS).fill(active / 100))}>
          {t.rangeEditor.all}
        </button>
      </div>
      <div className="grid-and-detail">
        <RangeGrid
          cells={cells}
          actions={ACTIONS}
          selected={detail}
          size={size}
          showLegend={false}
          onCellPointerDown={onDown}
          onCellPointerEnter={onEnter}
        />
        <div className="cell-detail" data-testid="cell-detail">
          {detail ? (
            <>
              <h4>{t.rangeEditor.detailTitle(detail)}</h4>
              <table>
                <tbody>
                  {HAND_COMBOS[detail]!.map((k) => {
                    const name = comboName(k);
                    return (
                      <tr key={k} className={dead[k] ? "out" : undefined}>
                        <td>{name}</td>
                        <td>
                          <input
                            type="number"
                            min={0}
                            max={100}
                            step={1}
                            aria-label={t.rangeEditor.comboWeight(name)}
                            value={Math.round((weights[k] ?? 0) * 100)}
                            onChange={(e) => setCombo(k, Number(e.target.value) || 0)}
                          />
                        </td>
                        <td>{dead[k] ? t.rangeEditor.blocked : ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          ) : (
            <small>{t.rangeEditor.detailHint}</small>
          )}
        </div>
      </div>
      {savedRanges && <SavedRangesMenu notation={text} onLoad={onText} />}
    </fieldset>
  );
}
