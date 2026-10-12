import { useEffect, useState } from "react";
import { api, problemMessage, type Schemas } from "../../api/client";
import { formatBytes, formatNumber } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import {
  POSITIONS,
  STREETS,
  configToTree,
  treeToConfig,
  uniformTree,
  type Pos,
  type SolveRequest,
  type Street,
  type TreeFormState,
} from "./types";

type Estimate = Schemas["TreeEstimate"];
type Named = Schemas["NamedTreeConfig"];

type Props = {
  value: TreeFormState;
  onChange: (v: TreeFormState) => void;
  spot: SolveRequest["spot"];
  onEstimate: (e: Estimate | null) => void;
};

const STREET_LABEL: Record<Street, string> = { flop: "Flop", turn: "Turn", river: "River" };

export function TreeConfigEditor({ value, onChange, spot, onEstimate }: Props) {
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [estError, setEstError] = useState<string | null>(null);
  const [configs, setConfigs] = useState<Named[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [quickBets, setQuickBets] = useState("");
  const [quickRaises, setQuickRaises] = useState("");

  const reload = async () => {
    const { data } = await api.GET("/tree-configs");
    setConfigs(data ?? []);
  };
  useEffect(() => {
    void reload();
  }, []);

  const key = JSON.stringify([value, spot]);
  useEffect(() => {
    const id = setTimeout(async () => {
      const { data, error } = await api.POST("/trees/estimate", { body: { spot, tree: treeToConfig(value) } });
      if (error) {
        setEstError(problemMessage(error));
        setEstimate(null);
        onEstimate(null);
      } else if (data) {
        setEstError(null);
        setEstimate(data);
        onEstimate(data);
      }
    }, 300);
    return () => clearTimeout(id);
  }, [key]);

  const setSize = (kind: "bets" | "raises", st: Street, pos: Pos) => (v: string) =>
    onChange({ ...value, [kind]: { ...value[kind], [st]: { ...value[kind][st], [pos]: v } } });

  const current = configs.find((c) => c.id === selected);

  const save = async (overwrite = false) => {
    setMsg(null);
    const { data, error, response } = await api.POST("/tree-configs", {
      body: { name, config: treeToConfig(value), overwrite },
    });
    if (response.status === 409 && (error as { code?: string })?.code === "nome_em_uso" && !overwrite) {
      if (window.confirm(`Já existe "${name}". Sobrescrever?`)) await save(true);
      return;
    }
    if (error) return setMsg(problemMessage(error));
    setSelected(data!.id);
    setMsg(t.tree.saved);
    await reload();
  };

  const rename = async () => {
    if (!current) return;
    const { error } = await api.PUT("/tree-configs/{config_id}", {
      params: { path: { config_id: current.id } },
      body: { name, config: treeToConfig(value), overwrite: false },
    });
    setMsg(error ? problemMessage(error) : t.tree.saved);
    await reload();
  };

  const remove = async () => {
    if (!current || !window.confirm(`Excluir "${current.name}"?`)) return;
    const { error } = await api.DELETE("/tree-configs/{config_id}", { params: { path: { config_id: current.id } } });
    if (error) return setMsg(problemMessage(error));
    setSelected("");
    await reload();
  };

  return (
    <fieldset className="tree-editor">
      <legend>{t.spot.tree}</legend>
      <div className="row">
        <label>
          {t.tree.saved_configs}
          <select
            aria-label={t.tree.saved_configs}
            value={selected}
            onChange={(e) => {
              const c = configs.find((x) => x.id === e.target.value);
              setSelected(e.target.value);
              if (c) {
                onChange(configToTree(c.config));
                setName(c.name);
              }
            }}
          >
            <option value="">—</option>
            {configs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.is_default ? " (padrão)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t.tree.name}
          <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
        </label>
      </div>
      <div className="buttons">
        <button type="button" onClick={() => save()} disabled={!name.trim()}>
          {t.tree.save}
        </button>
        <button type="button" onClick={rename} disabled={!current || current.is_default || !name.trim()}>
          {t.tree.rename}
        </button>
        <button type="button" onClick={remove} disabled={!current || current.is_default}>
          {t.tree.remove}
        </button>
      </div>
      {msg && <small>{msg}</small>}

      <div className="row quick">
        <label>
          {t.tree.quickBets}
          <input value={quickBets} onChange={(e) => setQuickBets(e.target.value)} placeholder="33, 75" />
        </label>
        <label>
          {t.tree.quickRaises}
          <input value={quickRaises} onChange={(e) => setQuickRaises(e.target.value)} placeholder="100" />
        </label>
        <button
          type="button"
          onClick={() => {
            const base = uniformTree(quickBets || "33, 75", quickRaises || "100", value.maxRaises);
            onChange({ ...value, bets: base.bets, raises: base.raises });
          }}
        >
          {t.tree.applyAll}
        </button>
      </div>

      <table className="sizes">
        <thead>
          <tr>
            <th>Street</th>
            <th>Bets OOP (%)</th>
            <th>Bets IP (%)</th>
            <th>Raises OOP (%)</th>
            <th>Raises IP (%)</th>
          </tr>
        </thead>
        <tbody>
          {STREETS.map((st) => (
            <tr key={st}>
              <td>{STREET_LABEL[st]}</td>
              {(["bets", "raises"] as const).flatMap((kind) =>
                POSITIONS.map((pos) => (
                  <td key={kind + pos}>
                    <input
                      aria-label={`${kind === "bets" ? "Bets" : "Raises"} ${STREET_LABEL[st]} ${pos.toUpperCase()}`}
                      value={value[kind][st][pos]}
                      onChange={(e) => setSize(kind, st, pos)(e.target.value)}
                    />
                  </td>
                )),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row">
        <label>
          {t.tree.maxRaises}
          <input
            type="number"
            min={0}
            max={6}
            value={value.maxRaises}
            onChange={(e) => onChange({ ...value, maxRaises: e.target.value })}
          />
        </label>
        <label>
          {t.tree.threshold}
          <input value={value.threshold} onChange={(e) => onChange({ ...value, threshold: e.target.value })} />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={value.addAllin}
            onChange={(e) => onChange({ ...value, addAllin: e.target.checked })}
          />{" "}
          {t.tree.addAllin}
        </label>
        <label className="check">
          <input type="checkbox" checked={value.donk} onChange={(e) => onChange({ ...value, donk: e.target.checked })} />{" "}
          {t.tree.donk}
        </label>
      </div>

      <section className="estimate" aria-live="polite" data-testid="estimate">
        {estError && <p className="error">{estError}</p>}
        {estimate && (
          <>
            <p>
              {t.tree.estimate(
                formatNumber(estimate.decision_nodes, 0),
                formatBytes(estimate.estimated_bytes),
                formatBytes(estimate.estimated_solution_bytes),
              )}
            </p>
            {estimate.within_limit ? (
              <p className="ok">{t.tree.withinLimit(formatBytes(estimate.max_bytes))}</p>
            ) : (
              <div className="error" data-testid="estimate-over">
                <p>{t.tree.overLimit(formatBytes(estimate.max_bytes))}</p>
                <ul>
                  {(estimate.suggestions ?? []).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>
    </fieldset>
  );
}
