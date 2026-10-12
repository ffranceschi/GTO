// Menu de ranges salvos (US4, FR-025 a FR-027): salvar com nome (confirmando a sobrescrita),
// listar, carregar no editor, renomear e excluir (com confirmação).
import { useEffect, useState } from "react";
import { api, problemMessage, type Schemas } from "../../api/client";
import { t } from "../../i18n/pt-BR";

type SavedRange = Schemas["SavedRange"];

type Props = {
  /** notação atual do editor (o que será salvo) */
  notation: string;
  onLoad: (notation: string) => void;
  confirm?: (msg: string) => boolean;
  prompt?: (msg: string, value: string) => string | null;
};

export function SavedRangesMenu({
  notation,
  onLoad,
  confirm = (m) => window.confirm(m),
  prompt = (m, v) => window.prompt(m, v),
}: Props) {
  const [list, setList] = useState<SavedRange[]>([]);
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState("");
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);

  const refresh = async () => {
    const { data } = await api.GET("/saved-ranges");
    if (data) setList(data);
  };
  useEffect(() => {
    void refresh();
  }, []);

  const current = list.find((r) => r.id === chosen) ?? null;
  const fail = (e: unknown) => setMsg({ text: problemMessage(e), error: true });

  const save = async () => {
    const body = { name: name.trim(), notation };
    let res = await api.POST("/saved-ranges", { body });
    if (res.error && (res.error as { code?: string }).code === "nome_em_uso") {
      if (!confirm(t.savedRanges.confirmOverwrite(body.name))) return;
      res = await api.POST("/saved-ranges", { body: { ...body, overwrite: true } });
    }
    if (res.error) return fail(res.error);
    setMsg({ text: t.savedRanges.saved(res.data.name), error: false });
    await refresh();
    setChosen(res.data.id);
  };

  const rename = async () => {
    if (!current) return;
    const next = prompt(t.savedRanges.renamePrompt, current.name);
    if (next === null || next.trim() === current.name) return;
    const { error } = await api.PUT("/saved-ranges/{range_id}", {
      params: { path: { range_id: current.id } },
      body: { name: next.trim(), notation: current.notation },
    });
    if (error) return fail(error);
    setMsg(null);
    await refresh();
  };

  const remove = async () => {
    if (!current || !confirm(t.savedRanges.confirmDelete(current.name))) return;
    const { error } = await api.DELETE("/saved-ranges/{range_id}", { params: { path: { range_id: current.id } } });
    if (error) return fail(error);
    setChosen("");
    setMsg(null);
    await refresh();
  };

  return (
    <div className="saved-ranges" aria-label={t.savedRanges.title} role="group">
      <div className="row">
        <label>
          {t.savedRanges.name}
          <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="button" disabled={!name.trim() || !notation.trim()} onClick={() => void save()}>
          {t.savedRanges.save}
        </button>
      </div>
      <div className="row">
        <label>
          {t.savedRanges.choose}
          <select value={chosen} onFocus={() => void refresh()} onChange={(e) => setChosen(e.target.value)}>
            <option value="">{t.savedRanges.none}</option>
            {list.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        {current && (
          <>
            <button type="button" onClick={() => onLoad(current.notation)}>
              {t.savedRanges.load}
            </button>
            <button type="button" onClick={() => void rename()}>
              {t.savedRanges.rename}
            </button>
            <button type="button" onClick={() => void remove()}>
              {t.savedRanges.remove}
            </button>
          </>
        )}
      </div>
      {msg && (
        <small className={msg.error ? "error" : "ok"} role="status">
          {msg.text}
        </small>
      )}
    </div>
  );
}
