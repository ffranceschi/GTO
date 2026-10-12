// Cliente WebSocket de jobs (contracts/websocket.md): reconexão com backoff, descarte por `seq`
// e reconstrução do estado a partir do `snapshot`.

export type JobMessage = {
  type: "snapshot" | "progress" | "status" | "finished" | "error";
  job_id: string;
  job_kind: string;
  seq: number;
  [k: string]: unknown;
};

export type JobState = {
  status: string;
  queuePosition: number | null;
  iteration: number;
  exploitabilityPct: number | null;
  exploitabilityIteration: number | null;
  elapsedS: number;
  iterationsPerS: number;
  history: [number, number, number][];
  progress: number | null;
  finished: JobMessage | null;
  error: { code: string; detail: string } | null;
};

export const initialJobState: JobState = {
  status: "queued",
  queuePosition: null,
  iteration: 0,
  exploitabilityPct: null,
  exploitabilityIteration: null,
  elapsedS: 0,
  iterationsPerS: 0,
  history: [],
  progress: null,
  finished: null,
  error: null,
};

const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
const numOrNull = (v: unknown) => (typeof v === "number" ? v : null);

/** Aplica uma mensagem ao estado (função pura, testável). */
export function reduceJob(state: JobState, m: JobMessage): JobState {
  switch (m.type) {
    case "snapshot":
      return {
        ...initialJobState,
        status: String(m.status),
        queuePosition: numOrNull(m.queue_position),
        iteration: num(m.iteration, 0),
        exploitabilityPct: numOrNull(m.exploitability_pct),
        exploitabilityIteration: numOrNull(m.exploitability_iteration),
        elapsedS: num(m.elapsed_s, 0),
        iterationsPerS: num(m.iterations_per_s, 0),
        history: (m.history as [number, number, number][] | undefined) ?? [],
        progress: numOrNull(m.progress),
      };
    case "progress": {
      const expl = numOrNull(m.exploitability_pct);
      const eIt = numOrNull(m.exploitability_iteration);
      const history =
        expl !== null && eIt !== null && eIt !== state.exploitabilityIteration
          ? [...state.history, [eIt, num(m.elapsed_s, 0), expl] as [number, number, number]]
          : state.history;
      return {
        ...state,
        iteration: num(m.iteration, state.iteration),
        exploitabilityPct: expl ?? state.exploitabilityPct,
        exploitabilityIteration: eIt ?? state.exploitabilityIteration,
        elapsedS: num(m.elapsed_s, state.elapsedS),
        iterationsPerS: num(m.iterations_per_s, state.iterationsPerS),
        progress: numOrNull(m.progress) ?? state.progress,
        history,
      };
    }
    case "status":
      return { ...state, status: String(m.status), queuePosition: numOrNull(m.queue_position) };
    case "error":
      return { ...state, error: { code: String(m.code), detail: String(m.detail) } };
    case "finished":
      return {
        ...state,
        status: String(m.status),
        queuePosition: null,
        iteration: num(m.iterations, state.iteration),
        exploitabilityPct: numOrNull(m.exploitability_pct) ?? state.exploitabilityPct,
        finished: m,
      };
  }
}

export type SocketLike = {
  onmessage: ((ev: { data: string }) => void) | null;
  onclose: ((ev: { code: number }) => void) | null;
  close: () => void;
};

export type Options = {
  url: string;
  onState: (s: JobState) => void;
  createSocket?: (url: string) => SocketLike;
  schedule?: (fn: () => void, ms: number) => unknown;
};

export const BACKOFF_MS = [1000, 2000, 4000, 8000, 10000];

/** Conecta ao WebSocket do job; reconecta até receber `finished` ou fechar com 4404. */
export function subscribeJob(opts: Options): () => void {
  const create = opts.createSocket ?? ((u: string) => new WebSocket(u) as unknown as SocketLike);
  const schedule = opts.schedule ?? ((fn: () => void, ms: number) => setTimeout(fn, ms));
  let state = initialJobState;
  let lastSeq = -1;
  let attempt = 0;
  let stopped = false;
  let done = false;
  let socket: SocketLike | null = null;

  const connect = () => {
    if (stopped) return;
    socket = create(opts.url);
    socket.onmessage = (ev) => {
      const m = JSON.parse(ev.data) as JobMessage;
      if (m.type === "snapshot") {
        attempt = 0;
        lastSeq = m.seq;
        state = reduceJob(state, m);
      } else {
        if (m.seq <= lastSeq) return; // duplicada ou antiga
        lastSeq = m.seq;
        state = reduceJob(state, m);
      }
      if (m.type === "finished") done = true;
      opts.onState(state);
    };
    socket.onclose = (ev) => {
      if (stopped || done || ev.code === 4404 || ev.code === 1000) return;
      const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]!;
      attempt += 1;
      schedule(connect, delay);
    };
  };
  connect();
  return () => {
    stopped = true;
    socket?.close();
  };
}

export function jobEventsUrl(jobId: string, loc: Location = window.location): string {
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}/api/v1/jobs/${jobId}/events`;
}
