import { api } from "../../api/client";
import type { JobState } from "../../api/jobEvents";
import { formatNumber, formatPctValue, formatSeconds } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";

function ExplChart({ history }: { history: [number, number, number][] }) {
  if (history.length < 2) return null;
  const w = 360;
  const h = 140;
  const its = history.map((p) => p[0]);
  const vals = history.map((p) => Math.log10(Math.max(p[2], 1e-4)));
  const [x0, x1] = [Math.min(...its), Math.max(...its)];
  const [y0, y1] = [Math.min(...vals), Math.max(...vals)];
  const sx = (x: number) => 30 + ((x - x0) / Math.max(1, x1 - x0)) * (w - 40);
  const sy = (y: number) => 10 + (1 - (y - y0) / Math.max(1e-9, y1 - y0)) * (h - 30);
  const d = history.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(vals[i]!).toFixed(1)}`).join(" ");
  return (
    <figure className="chart">
      <figcaption>{t.progress.chartTitle}</figcaption>
      <svg width={w} height={h} role="img" aria-label={t.progress.chartTitle}>
        <path d={d} fill="none" stroke="#d1495b" strokeWidth={2} />
        <text x={2} y={14} fontSize={10}>{formatPctValue(10 ** y1)}</text>
        <text x={2} y={h - 20} fontSize={10}>{formatPctValue(10 ** y0)}</text>
        <text x={30} y={h - 4} fontSize={10}>{formatNumber(x0, 0)}</text>
        <text x={w - 40} y={h - 4} fontSize={10}>{formatNumber(x1, 0)}</text>
      </svg>
    </figure>
  );
}

type Props = {
  solveId: string;
  job: JobState;
  stale: boolean;
  onRestore: () => void;
  onNewSolve: () => void;
};

export function SolveProgress({ solveId, job, stale, onRestore, onNewSolve }: Props) {
  const cmd = (c: "pause" | "resume" | "stop") => () =>
    api.POST(`/solves/{solve_id}/${c}` as "/solves/{solve_id}/pause", { params: { path: { solve_id: solveId } } });
  const cancel = () => api.DELETE("/solves/{solve_id}", { params: { path: { solve_id: solveId } } });
  const active = !job.finished;
  const finished = job.finished as { target_reached?: boolean } | null;
  return (
    <section className="progress" aria-live="polite">
      <h2>{t.progress.title}</h2>
      {stale && (
        <div className="banner" role="status">
          {t.progress.staleInputs}{" "}
          <button type="button" onClick={onRestore}>{t.progress.restoreInputs}</button>{" "}
          <button type="button" onClick={onNewSolve}>{t.progress.newSolve}</button>
        </div>
      )}
      <dl>
        <dt>Status</dt>
        <dd data-testid="status">{t.progress.status[job.status] ?? job.status}</dd>
        {job.queuePosition !== null && (
          <>
            <dt>Fila</dt>
            <dd>{t.progress.queuePosition(job.queuePosition)}</dd>
          </>
        )}
        <dt>{t.progress.iterations}</dt>
        <dd data-testid="iterations">{formatNumber(job.iteration, 0)}</dd>
        <dt>{t.progress.exploitability}</dt>
        <dd data-testid="exploitability">
          {job.exploitabilityPct === null ? "—" : `${formatPctValue(job.exploitabilityPct, 3)} do pote`}
        </dd>
        <dt>{t.progress.elapsed}</dt>
        <dd>{formatSeconds(job.elapsedS)}</dd>
      </dl>
      {finished && finished.target_reached === false && job.status !== "cancelled" && (
        <p className="warn">{t.progress.targetNotReached}</p>
      )}
      {job.error && <p className="error">{job.error.detail}</p>}
      {active && (
        <div className="buttons">
          {job.status === "paused" ? (
            <button type="button" onClick={cmd("resume")}>{t.progress.resume}</button>
          ) : (
            <button type="button" onClick={cmd("pause")} disabled={job.status !== "running"}>{t.progress.pause}</button>
          )}
          <button type="button" onClick={cmd("stop")} disabled={!["running", "paused"].includes(job.status)}>
            {t.progress.stop}
          </button>
          <button type="button" onClick={cancel}>{t.progress.cancel}</button>
        </div>
      )}
      <ExplChart history={job.history} />
    </section>
  );
}
