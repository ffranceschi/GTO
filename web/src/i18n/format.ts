// Formatadores pt-BR (Princípio VIII): vírgula decimal, %, bb, bytes e datas relativas.

const nf = (digits: number) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function formatNumber(value: number, digits = 1): string {
  return nf(digits).format(value);
}

/** 0.819 → "81,9%" */
export function formatPct(fraction: number, digits = 1): string {
  return `${formatNumber(fraction * 100, digits)}%`;
}

/** Valor já em %: 0.49 → "0,49%" */
export function formatPctValue(pct: number, digits = 2): string {
  return `${formatNumber(pct, digits)}%`;
}

/** 7.5 → "7,5 bb" (até 2 casas, sem zeros à direita) */
export function formatBb(bb: number): string {
  const s = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(bb);
  return `${s} bb`;
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes;
  let i = 0;
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i += 1;
  }
  return `${formatNumber(v, i === 0 ? 0 : 1)} ${units[i]}`;
}

/** Diferença em dias inteiros a partir de agora: "em 5 dias", "hoje", "há 2 dias" */
export function formatRelativeDays(iso: string, now: Date = new Date()): string {
  const days = Math.round((new Date(iso).getTime() - now.getTime()) / 86_400_000);
  if (days === 0) return "hoje";
  if (days > 0) return days === 1 ? "em 1 dia" : `em ${days} dias`;
  return days === -1 ? "há 1 dia" : `há ${-days} dias`;
}

export function formatSeconds(s: number): string {
  if (s < 60) return `${formatNumber(s, 1)} s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s - m * 60);
  return `${m} min ${r} s`;
}
