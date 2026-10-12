import type { Schemas } from "../../api/client";

export type SolveRequest = Schemas["SolveRequest"];

export type SpotFormState = {
  oopRange: string;
  ipRange: string;
  board: string;
  pot: string;
  stack: string;
  target: string;
  timeLimit: string;
  bets: string;
  raises: string;
};

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
  bets: "33, 75",
  raises: "100",
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
  return s.split(/[,;\s]+/).filter(Boolean).map((x) => parseNum(x) / 100);
}

export function toRequest(f: SpotFormState): SolveRequest {
  const bets = pctList(f.bets);
  const raises = pctList(f.raises);
  const sizes = (v: number[]) => ({
    flop: { oop: v, ip: v },
    turn: { oop: v, ip: v },
    river: { oop: v, ip: v },
  });
  const cards = boardCards(f.board);
  return {
    spot: {
      oop_range: { notation: f.oopRange },
      ip_range: { notation: f.ipRange },
      board: cards,
      pot: parseNum(f.pot),
      effective_stack: parseNum(f.stack),
    },
    tree: {
      bet_sizes: sizes(bets),
      raise_sizes: sizes(raises),
      max_raises_per_street: 3,
      allin_threshold: 0.67,
      add_allin_action: false,
      allow_donk: false,
    },
    params: {
      target_exploitability_pct: parseNum(f.target),
      time_limit_s: f.timeLimit.trim() ? parseNum(f.timeLimit) : defaultTimeLimit(cards.length),
    },
  } as unknown as SolveRequest;
}
