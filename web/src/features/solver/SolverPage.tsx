import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { initialJobState, jobEventsUrl, subscribeJob, type JobState } from "../../api/jobEvents";
import { t } from "../../i18n/pt-BR";
import { TreeNavigator } from "./TreeNavigator";
import { SolveProgress } from "./SolveProgress";
import { SpotForm } from "./SpotForm";
import { DEFAULT_FORM, toRequest, type SpotFormState } from "./types";

export function SolverPage() {
  const [form, setForm] = useState<SpotFormState>(DEFAULT_FORM);
  const [submitted, setSubmitted] = useState<SpotFormState | null>(null);
  const [solveId, setSolveId] = useState<string | null>(null);
  const [job, setJob] = useState<JobState>(initialJobState);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!solveId) return;
    setJob(initialJobState);
    return subscribeJob({ url: jobEventsUrl(solveId), onState: setJob });
  }, [solveId]);

  const submit = async (f: SpotFormState = form) => {
    setBusy(true);
    setErrors({});
    const { data, error } = await api.POST("/solves", { body: toRequest(f) });
    setBusy(false);
    if (error) {
      const e = error as { detail?: string; errors?: { field: string; detail: string }[] };
      const map: Record<string, string> = { _: e.detail ?? t.errors.generic };
      for (const fe of e.errors ?? []) map[fe.field] = fe.detail;
      setErrors(map);
      return;
    }
    if (data) {
      setSubmitted(f);
      setSolveId(data.id);
    }
  };

  const stale = !!submitted && JSON.stringify(submitted) !== JSON.stringify(form);
  const done = job.status === "completed" || job.status === "stopped";

  return (
    <main>
      <h1>{t.appTitle}</h1>
      <SpotForm value={form} onChange={setForm} onSubmit={() => submit()} errors={errors} busy={busy} />
      {solveId && (
        <SolveProgress
          solveId={solveId}
          job={job}
          stale={stale}
          onRestore={() => submitted && setForm(submitted)}
          onNewSolve={() => submit(form)}
        />
      )}
      {solveId && done && !stale && <TreeNavigator key={solveId} solveId={solveId} />}
    </main>
  );
}
