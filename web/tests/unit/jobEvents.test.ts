import { BACKOFF_MS, type JobState, type SocketLike, subscribeJob } from "../../src/api/jobEvents";

class FakeSocket implements SocketLike {
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  close() {}
  send(m: object) {
    this.onmessage?.({ data: JSON.stringify(m) });
  }
}

const base = { job_id: "j", job_kind: "solve" };

describe("subscribeJob", () => {
  it("reconstrói do snapshot, descarta seq repetido e acumula o histórico", () => {
    const sockets: FakeSocket[] = [];
    const states: JobState[] = [];
    subscribeJob({ url: "ws://x", onState: (s) => states.push(s), createSocket: () => {
      const s = new FakeSocket(); sockets.push(s); return s;
    } });
    const s = sockets[0]!;
    s.send({ ...base, type: "snapshot", seq: 3, status: "running", iteration: 10, history: [[5, 0.1, 9]] });
    s.send({ ...base, type: "progress", seq: 4, iteration: 20, exploitability_pct: 3, exploitability_iteration: 20, elapsed_s: 1 });
    s.send({ ...base, type: "progress", seq: 4, iteration: 99 });
    s.send({ ...base, type: "status", seq: 5, status: "paused" });
    const last = states.at(-1)!;
    expect(last.iteration).toBe(20);
    expect(last.status).toBe("paused");
    expect(last.history).toEqual([[5, 0.1, 9], [20, 1, 3]]);
  });

  it("reconecta com backoff 1 s, 2 s, 4 s… até 10 s e para em finished/4404", () => {
    const sockets: FakeSocket[] = [];
    const delays: number[] = [];
    const pending: (() => void)[] = [];
    subscribeJob({
      url: "ws://x",
      onState: () => {},
      createSocket: () => { const s = new FakeSocket(); sockets.push(s); return s; },
      schedule: (fn, ms) => { delays.push(ms); pending.push(fn); },
    });
    for (let i = 0; i < 6; i++) {
      sockets.at(-1)!.onclose?.({ code: 1006 });
      pending.shift()!();
    }
    expect(delays).toEqual([...BACKOFF_MS, 10000]);
    const s = sockets.at(-1)!;
    s.send({ ...base, type: "snapshot", seq: 0, status: "running" });
    s.send({ ...base, type: "finished", seq: 1, status: "completed" });
    s.onclose?.({ code: 1000 });
    expect(pending).toHaveLength(0);
  });
});
