import { useEffect, useState } from "react";
import { api, problemMessage, type Schemas, type Solve } from "../../api/client";
import { jobEventsUrl, subscribeJob, type JobState } from "../../api/jobEvents";
import { formatBytes, formatPct, formatPctValue, formatRelativeDays } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import { TreeNavigator } from "../solver/TreeNavigator";

type Storage = Schemas["StorageUsage"];
const SOON_MS = 7 * 86_400_000;

/** Acompanha um job auxiliar via WebSocket até terminar; devolve o estado final. */
function watchJob(jobId: string, onState: (s: JobState) => void): Promise<JobState> {
  return new Promise((resolve) => {
    const stop = subscribeJob({
      url: jobEventsUrl(jobId),
      onState: (s) => {
        onState(s);
        if (s.finished) {
          stop();
          resolve(s);
        }
      },
    });
  });
}

function ExportButton({ solve }: { solve: Solve }) {
  const [state, setState] = useState<JobState | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setErr(null);
    setUrl(null);
    const { data, error } = await api.POST("/solves/{solve_id}/exports", { params: { path: { solve_id: solve.id } } });
    if (error || !data) return setErr(problemMessage(error));
    const final = await watchJob(data.id, setState);
    if (final.status === "completed") setUrl(`/api/v1/aux-jobs/${data.id}/file`);
    else setErr(final.error?.detail ?? t.solutions.exportFailed);
  };
  const running = state && !state.finished;
  return (
    <span className="export">
      <button type="button" onClick={run} disabled={!!running}>
        {t.solutions.export}
      </button>
      {running && <small> {formatPct(state.progress ?? 0, 0)}</small>}
      {url && (
        <a href={url} download data-testid={`download-${solve.id}`}>
          {" "}
          {t.solutions.download}
        </a>
      )}
      {err && <small className="error"> {err}</small>}
    </span>
  );
}

export function SolutionsPage() {
  const [solves, setSolves] = useState<Solve[]>([]);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [importState, setImportState] = useState<JobState | null>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const reload = async () => {
    const [{ data: list }, { data: st }] = await Promise.all([api.GET("/solves"), api.GET("/storage")]);
    setSolves((list ?? []).filter((s) => s.status === "completed" || s.status === "stopped"));
    setStorage(st ?? null);
  };
  useEffect(() => {
    void reload();
  }, []);

  const pin = async (s: Solve) => {
    await api.PATCH("/solves/{solve_id}", { params: { path: { solve_id: s.id } }, body: { pinned: !s.pinned } });
    await reload();
  };
  const remove = async (s: Solve) => {
    if (!window.confirm(t.solutions.confirmDelete)) return;
    await api.DELETE("/solves/{solve_id}", { params: { path: { solve_id: s.id } } });
    if (open === s.id) setOpen(null);
    await reload();
  };
  const importFile = async (file: File) => {
    setImportMsg(null);
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/v1/solutions/import", { method: "POST", body });
    const job = await res.json();
    if (!res.ok) return setImportMsg(problemMessage(job));
    const final = await watchJob(job.id, setImportState);
    if (final.status !== "completed") return setImportMsg(final.error?.detail ?? t.solutions.importFailed);
    const { data } = await api.GET("/aux-jobs/{job_id}", { params: { path: { job_id: job.id } } });
    await reload();
    if (data?.solve_id) {
      setImportMsg(t.solutions.imported);
      setOpen(data.solve_id);
    }
  };

  const now = Date.now();
  return (
    <main>
      <h1>{t.solutions.title}</h1>
      {storage && (
        <p data-testid="storage">
          {t.solutions.storage(formatBytes(storage.total_bytes), storage.solutions, storage.pinned, storage.retention_days)}
          {storage.expiring_soon > 0 && <strong> · {t.solutions.expiringSoon(storage.expiring_soon)}</strong>}
        </p>
      )}
      <label className="import">
        {t.solutions.import}
        <input
          type="file"
          accept=".npz"
          aria-label={t.solutions.import}
          onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])}
        />
      </label>
      {importState && !importState.finished && <small> {formatPct(importState.progress ?? 0, 0)}</small>}
      {importMsg && <p data-testid="import-msg">{importMsg}</p>}
      <table className="solutions">
        <thead>
          <tr>
            <th>{t.spot.board}</th>
            <th>{t.solutions.origin}</th>
            <th>{t.progress.exploitability}</th>
            <th>{t.solutions.size}</th>
            <th>{t.solutions.lastUsed}</th>
            <th>{t.solutions.expires}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {solves.map((s) => {
            const spot = s.spot as { board?: string[] } | null;
            const exp = s.expires_at ? new Date(s.expires_at).getTime() : null;
            const soon = exp !== null && exp - now <= SOON_MS;
            return (
              <tr key={s.id} data-testid={`solve-${s.id}`} className={soon ? "soon" : ""}>
                <td>{spot?.board?.join(" ")}</td>
                <td>{s.origin === "import" ? t.solutions.fromImport : t.solutions.fromSolve}</td>
                <td>{s.exploitability_pct == null ? "—" : formatPctValue(s.exploitability_pct, 3)}</td>
                <td>{s.size_bytes ? formatBytes(s.size_bytes) : "—"}</td>
                <td>{s.last_used_at ? formatRelativeDays(s.last_used_at) : "—"}</td>
                <td data-testid={`expires-${s.id}`}>
                  {s.pinned ? t.solutions.pinned : s.expires_at ? formatRelativeDays(s.expires_at) : "—"}
                </td>
                <td className="buttons">
                  <button type="button" onClick={() => setOpen(s.id)}>
                    {t.solutions.open}
                  </button>
                  <button type="button" onClick={() => pin(s)} aria-pressed={!!s.pinned}>
                    {s.pinned ? t.solutions.unpin : t.solutions.pin}
                  </button>
                  <ExportButton solve={s} />
                  <button type="button" onClick={() => remove(s)}>
                    {t.solutions.remove}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {open && <TreeNavigator key={open} solveId={open} />}
    </main>
  );
}
