// Combos de duas cartas na mesma ordem do motor (gto_engine.cards): carta = rank × 4 + naipe,
// ranks 2..A, naipes s, h, d, c; combo k percorre os pares a < b em ordem lexicográfica.

export const N_COMBOS = 1326;
const RANK_CHARS = "23456789TJQKA";
const SUIT_CHARS = "shdc";

export const cardStr = (c: number) => RANK_CHARS[c >> 2]! + SUIT_CHARS[c & 3]!;

export function parseCard(s: string): number | null {
  const r = RANK_CHARS.indexOf((s[0] ?? "").toUpperCase());
  const su = SUIT_CHARS.indexOf((s[1] ?? "").toLowerCase());
  return s.length === 2 && r >= 0 && su >= 0 ? r * 4 + su : null;
}

/** COMBOS[k] = [carta maior, carta menor] (maior rank primeiro; no mesmo rank, s, h, d, c). */
export const COMBOS: [number, number][] = [];
for (let a = 0; a < 52; a++) {
  for (let b = a + 1; b < 52; b++) {
    const hiFirst = (b >> 2) > (a >> 2) || ((b >> 2) === (a >> 2) && (b & 3) < (a & 3));
    COMBOS.push(hiFirst ? [b, a] : [a, b]);
  }
}

export const comboName = (k: number) => cardStr(COMBOS[k]![0]) + cardStr(COMBOS[k]![1]);

/** Célula da grade (AA, AKs, AKo) do combo k. */
export function handOf(k: number): string {
  const [hi, lo] = COMBOS[k]!;
  const r1 = RANK_CHARS[hi >> 2]!;
  const r2 = RANK_CHARS[lo >> 2]!;
  if (r1 === r2) return r1 + r2;
  return r1 + r2 + ((hi & 3) === (lo & 3) ? "s" : "o");
}

/** Combos de cada célula, na ordem de naipes do motor. */
export const HAND_COMBOS: Record<string, number[]> = {};
COMBOS.forEach((_, k) => (HAND_COMBOS[handOf(k)] ??= []).push(k));

export function deadMask(dead: string[]): boolean[] {
  const cards = new Set(dead.map(parseCard).filter((c): c is number => c !== null));
  return COMBOS.map(([a, b]) => cards.has(a) || cards.has(b));
}

/** Combos efetivos: soma dos pesos dos combos sem cartas mortas (FR-011). */
export function countCombos(weights: number[], dead: boolean[]): number {
  let s = 0;
  for (let k = 0; k < N_COMBOS; k++) if (!dead[k]) s += weights[k] ?? 0;
  return s;
}

/** Peso médio por célula (0–1) para a faixa proporcional da grade. */
export function cellWeights(weights: number[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [hand, ks] of Object.entries(HAND_COMBOS)) {
    out[hand] = ks.reduce((s, k) => s + (weights[k] ?? 0), 0) / ks.length;
  }
  return out;
}

export const emptyWeights = () => new Array<number>(N_COMBOS).fill(0);
