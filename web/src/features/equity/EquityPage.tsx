import { useEffect, useRef, useState } from "react";
import { api, problemMessage, type Schemas } from "../../api/client";
import { RangeEditor } from "../../components/RangeEditor/RangeEditor";
import { initialJobState, jobEventsUrl, subscribeJob, type JobState } from "../../api/jobEvents";
import { formatMarginPp, formatNumber, formatPct, formatSeconds } from "../../i18n/format";
import { t } from "../../i18n/pt-BR";
import { boardCards } from "../solver/types";
import { EquityDistribution } from "./EquityDistribution";

type Method = "auto" | "exact" | "monte_carlo";

export type EquityForm = {
  participants: string[];
  board: string;
  method: Method;
  target: string;
  timeLimit: string;
  seed: string;
};

export const DEFAULT_EQUITY_FORM: EquityForm = {
  participants: ["AA", "KK"],
  board: "",
  method: "auto",
  target: "0,1",
  timeLimit: "60",
  seed: "0",
};

const VALID_BOARD = [0, 3, 4, 5];
const num = (s: string) => Number(s.replace(",", "."));

export function toEquityRequest(f: EquityForm): Schemas["EquityRequest"] {
  return {
    participants: f.participants.map((notation) => ({ notation })),
    board: boardCards(f.board),
    method: f.method,
    target_margin_pp: num(f.target),
    time_limit_s: num(f.timeLimit),
    seed: Math.max(0, Math.trunc(num(f.seed) || 0)),
  };
}

const SPECIFIC = /^[AKQJT2-9][shdc][AKQJT2-9][shdc]$/i;

/** Cartas mortas para o participante i: board + mãos específicas dos outros (FR-011). */
export function deadCardsFor(participants: string[], board: string[], i: number): string[] {
  const dead = [...board];
  participants.forEach((p, j) => {
    const h = p.trim();
    if (j !== i && SPECIFIC.test(h)) dead.push(h.slice(0, 2), h.slice(2));
  });
  return dead;
}

function ParticipantField(props: {
  index: number;
  value: string;
  deadCards: string[];
  onChange: (v: string) => void;
  onRemove?: () => void;
}) {
  const label = t.equity.participant(props.index + 1);
  return (
    <div className="participant" data-testid={`participant-${props.index + 1}`}>
      <RangeEditor label={label} value={props.value} onChange={props.onChange} deadCards={props.deadCards} savedRanges />
      {props.onRemove && (
        <button type="button" onClick={props.onRemove} aria-label={`${t.equity.removeParticipant} ${label}`}>
          {t.equity.removeParticipant}
        </button>
      )}
    </div>
  );
}

function EquityProgressView({ jobId, job }: { jobId: string; job: JobState }) {
  const p: Record<string, unknown> = job.lastProgress ?? {};
  const mc = p.method === "monte_carlo";
  const active = !job.finished;
  const margins = (p.margins as number[] | undefined) ?? [];
  return (
    <section className="progress" aria-live="polite">
      <h2>{t.equity.progressTitle}</h2>
      <dl>
        <dt>{t.common.status}</dt>
        <dd data-testid="equity-status">{t.equity.status[job.status] ?? job.status}</dd>
        {mc ? (
          <>
            <dt>{t.equity.samples}</dt>
            <dd data-testid="samples">{formatNumber(Number(p.samples ?? 0), 0)}</dd>
            <dt>{t.equity.samplesPerS}</dt>
            <dd>{formatNumber(Number(p.samples_per_s ?? 0), 0)}</dd>
            <dt>{t.equity.margins}</dt>
            <dd data-testid="margins">{margins.map(formatMarginPp).join(" · ") || "—"}</dd>
          </>
        ) : (
          typeof p.fraction === "number" && (
            <>
              <dt>{t.equity.fraction}</dt>
              <dd data-testid="fraction">{formatPct(p.fraction, 0)}</dd>
            </>
          )
        )}
        <dt>{t.equity.elapsed}</dt>
        <dd>{formatSeconds(Number(p.elapsed_s ?? 0))}</dd>
      </dl>
      {job.error && <p className="error">{job.error.detail}</p>}
      {active && (
        <div className="buttons">
          <button
            type="button"
            disabled={job.status !== "running"}
            onClick={() => api.POST("/equity-jobs/{job_id}/stop", { params: { path: { job_id: jobId } } })}
          >
            {t.equity.stop}
          </button>{" "}
          <button
            type="button"
            onClick={() => api.DELETE("/equity-jobs/{job_id}", { params: { path: { job_id: jobId } } })}
          >
            {t.equity.cancel}
          </button>
        </div>
      )}
    </section>
  );
}

function EquityResultView({ result, labels }: { result: Schemas["EquityResult"]; labels: string[] }) {
  const exact = result.method === "exact";
  const [shown, setShown] = useState(0);
  return (
    <section className="progress equity-result">
      <h2>{t.equity.resultTitle}</h2>
      <p data-testid="result-kind">
        <strong>{exact ? t.equity.exact : t.equity.estimated}</strong> · {t.equity.stopReason[result.stop_reason]} ·{" "}
        {formatSeconds(result.elapsed_s)}
        {!exact && ` · ${formatNumber(result.samples, 0)} ${t.equity.samples.toLowerCase()} · ${t.equity.seedUsed(result.seed)}`}
      </p>
      <table className="solutions">
        <thead>
          <tr>
            <th />
            <th>{t.equity.equityCol}</th>
            <th>{t.equity.win}</th>
            <th>{t.equity.tie}</th>
            <th>{t.equity.margin}</th>
          </tr>
        </thead>
        <tbody>
          {result.participants.map((p, i) => (
            <tr key={i} data-testid={`result-${i + 1}`}>
              <td>
                {t.equity.participant(i + 1)} <small>{labels[i]}</small>
              </td>
              <td className="equity-value">{formatPct(p.equity, 2)}</td>
              <td>{formatPct(p.win, 2)}</td>
              <td>{formatPct(p.tie, 2)}</td>
              <td>{exact ? t.equity.exact : formatMarginPp(p.margin)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="buttons" role="group" aria-label={t.distribution.choose}>
        {result.participants.map((_, i) => (
          <button key={i} type="button" aria-pressed={shown === i} onClick={() => setShown(i)}>
            {t.equity.participant(i + 1)}
          </button>
        ))}
      </div>
      {result.participants[shown] && (
        <EquityDistribution
          participant={result.participants[shown]}
          method={result.method}
          label={t.equity.participant(shown + 1)}
        />
      )}
    </section>
  );
}

export function EquityPage() {
  const [form, setForm] = useState<EquityForm>(DEFAULT_EQUITY_FORM);
  const [submitted, setSubmitted] = useState<EquityForm | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobState>(initialJobState);
  const [result, setResult] = useState<Schemas["EquityResult"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cancelled = useRef<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setJob(initialJobState);
    return subscribeJob({ url: jobEventsUrl(jobId), onState: setJob });
  }, [jobId]);

  useEffect(() => {
    if (!jobId || job.finished?.status !== "completed") return;
    void api.GET("/equity-jobs/{job_id}", { params: { path: { job_id: jobId } } }).then(({ data }) => {
      if (data?.result) setResult(data.result);
    });
  }, [jobId, job.finished]);

  const stale = !!submitted && JSON.stringify(submitted) !== JSON.stringify(form);

  // R6: alterar qualquer entrada com job ativo cancela o cálculo (sem recalcular)
  useEffect(() => {
    if (stale && jobId && !job.finished && cancelled.current !== jobId) {
      cancelled.current = jobId;
      void api.DELETE("/equity-jobs/{job_id}", { params: { path: { job_id: jobId } } });
    }
  }, [stale, jobId, job.finished]);

  const cards = boardCards(form.board);
  const boardOk = VALID_BOARD.includes(cards.length);

  const update = (patch: Partial<EquityForm>) => setForm((f) => ({ ...f, ...patch }));
  // funcional: o RangeEditor informa o texto canônico depois de um debounce
  const setParticipant = (i: number) => (v: string) =>
    setForm((f) => ({ ...f, participants: f.participants.map((p, j) => (j === i ? v : p)) }));

  const calculate = async () => {
    setBusy(true);
    setError(null);
    const body = toEquityRequest(form);
    if (form.method === "exact") {
      const est = await api.POST("/equity/estimate", { body });
      if (est.data && est.data.estimated_exact_s > 2 && !window.confirm(t.equity.confirmSlowExact(formatSeconds(est.data.estimated_exact_s)))) {
        setBusy(false);
        return;
      }
    }
    const { data, error: err } = await api.POST("/equity-jobs", { body });
    setBusy(false);
    if (err) {
      setError(problemMessage(err));
      return;
    }
    if (data) {
      setResult(null);
      setSubmitted(form);
      setJobId(data.id);
    }
  };

  return (
    <main>
      <h1>{t.equity.title}</h1>
      <form
        className="spot-form equity-form"
        onSubmit={(e) => {
          e.preventDefault();
          void calculate();
        }}
      >
        <div className="ranges">
          {form.participants.map((p, i) => (
            <ParticipantField
              key={i}
              index={i}
              value={p}
              deadCards={deadCardsFor(form.participants, boardOk ? cards : [], i)}
              onChange={setParticipant(i)}
              onRemove={
                form.participants.length > 2
                  ? () => update({ participants: form.participants.filter((_, j) => j !== i) })
                  : undefined
              }
            />
          ))}
        </div>
        {form.participants.length < 6 && (
          <button type="button" onClick={() => update({ participants: [...form.participants, ""] })}>
            {t.equity.addParticipant}
          </button>
        )}
        <label>
          {t.equity.board}
          <input value={form.board} onChange={(e) => update({ board: e.target.value })} placeholder="Ks 7d 2c" />
        </label>
        {!boardOk && <small className="warn">{t.equity.boardSize}</small>}
        <div className="row">
          <label>
            {t.equity.method}
            <select value={form.method} onChange={(e) => update({ method: e.target.value as Method })}>
              {(["auto", "exact", "monte_carlo"] as const).map((m) => (
                <option key={m} value={m}>
                  {t.equity.methods[m]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t.equity.target}
            <input value={form.target} onChange={(e) => update({ target: e.target.value })} inputMode="decimal" />
          </label>
          <label>
            {t.equity.timeLimit}
            <input value={form.timeLimit} onChange={(e) => update({ timeLimit: e.target.value })} inputMode="decimal" />
          </label>
          <label>
            {t.equity.seed}
            <input value={form.seed} onChange={(e) => update({ seed: e.target.value })} inputMode="numeric" />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || !boardOk}>
          {t.equity.calculate}
        </button>
      </form>
      {stale && (
        <div className="banner" role="status" data-testid="stale">
          {t.equity.staleInputs}
        </div>
      )}
      {jobId && (!result || stale) && <EquityProgressView jobId={jobId} job={job} />}
      {result && !stale && <EquityResultView result={result} labels={(submitted ?? form).participants} />}
    </main>
  );
}
