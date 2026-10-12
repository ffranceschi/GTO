import type { Schemas } from "../../api/client";

export type SolveRequest = Schemas["SolveRequest"];

export type Street = "flop" | "turn" | "river";
export type Pos = "oop" | "ip";
export const STREETS: Street[] = ["flop", "turn", "river"];
export const POSITIONS: Pos[] = ["oop", "ip"];

export type TreeFormState = {
  bets: Record<Street, Record<Pos, string>>;
  raises: Record<Street, Record<Pos, string>>;
  maxRaises: string;
  threshold: string;
  addAllin: boolean;
  donk: boolean;
};

export type SpotFormState = {
  oopRange: string;
  ipRange: string;
  board: string;
  pot: string;
  stack: string;
  target: string;
  timeLimit: string;
  tree: TreeFormState;
};

const fill = (v: string) =>
  Object.fromEntries(STREETS.map((s) => [s, { oop: v, ip: v }])) as Record<Street, Record<Pos, string>>;

export function uniformTree(bets: string, raises: string, maxRaises = "3"): TreeFormState {
  return { bets: fill(bets), raises: fill(raises), maxRaises, threshold: "67", addAllin: false, donk: false };
}

export const OOP_REF =
  "22-TT, A2s-AQs, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A8o-AQo, K9o+, Q9o+, J9o+, T9o, 98o";
export const IP_REF =
  "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A5o+, K9o+, Q9o+, J9o+, T9o, 98o";

export const DEFAULT_FORM: SpotFormState = {
  oopRange: OOP_REF,
  ipRange: IP_REF,
  board: "Ks 7d 2c Jh 3s",
  pot: "10",
  stack: "50",
  target: "0,5",
  timeLimit: "",
  tree: uniformTree("33, 75", "100"),
};

/** Padrão do tempo-limite pela street do board (FR-012): river 60 s, turn 120 s, flop 15 min. */
export function defaultTimeLimit(boardCards: number): number {
  return boardCards === 3 ? 900 : boardCards === 4 ? 120 : 60;
}

export const parseNum = (s: string) => Number(s.replace(",", ".").trim());

export function boardCards(board: string): string[] {
  return board.trim().split(/[\s,]+/).filter(Boolean);
}

function pctList(s: string): number[] {
  return s
    .split(/[;\s]+|,(?=\s)/)
    .map((x) => x.replace(/,$/, "").trim())
    .filter(Boolean)
    .map((x) => parseNum(x) / 100);
}

const pctText = (v: number[] | undefined) =>
  (v ?? []).map((x) => String(Math.round(x * 10000) / 100).replace(".", ",")).join(", ");

export type ApiTreeConfig = Schemas["TreeConfig"];

export function treeToConfig(t: TreeFormState): ApiTreeConfig {
  const sizes = (src: Record<Street, Record<Pos, string>>) =>
    Object.fromEntries(STREETS.map((s) => [s, { oop: pctList(src[s].oop), ip: pctList(src[s].ip) }]));
  return {
    bet_sizes: sizes(t.bets),
    raise_sizes: sizes(t.raises),
    max_raises_per_street: Math.round(parseNum(t.maxRaises)),
    allin_threshold: parseNum(t.threshold) / 100,
    add_allin_action: t.addAllin,
    allow_donk: t.donk,
  } as ApiTreeConfig;
}

export function configToTree(c: ApiTreeConfig): TreeFormState {
  const sizes = (src: ApiTreeConfig["bet_sizes"]) =>
    Object.fromEntries(
      STREETS.map((s) => [s, { oop: pctText(src[s]?.oop), ip: pctText(src[s]?.ip) }]),
    ) as Record<Street, Record<Pos, string>>;
  return {
    bets: sizes(c.bet_sizes),
    raises: sizes(c.raise_sizes),
    maxRaises: String(c.max_raises_per_street),
    threshold: String(Math.round(c.allin_threshold * 100)),
    addAllin: !!c.add_allin_action,
    donk: !!c.allow_donk,
  };
}

export function toSpot(f: SpotFormState): SolveRequest["spot"] {
  return {
    oop_range: { notation: f.oopRange },
    ip_range: { notation: f.ipRange },
    board: boardCards(f.board),
    pot: parseNum(f.pot),
    effective_stack: parseNum(f.stack),
  };
}

export function toRequest(f: SpotFormState): SolveRequest {
  const cards = boardCards(f.board);
  return {
    spot: toSpot(f),
    tree: treeToConfig(f.tree),
    params: {
      target_exploitability_pct: parseNum(f.target),
      time_limit_s: f.timeLimit.trim() ? parseNum(f.timeLimit) : defaultTimeLimit(cards.length),
    },
  } as unknown as SolveRequest;
}
