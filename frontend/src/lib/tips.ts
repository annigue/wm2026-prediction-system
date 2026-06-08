import type { PredictionSummary } from "@/types";

export interface Tip {
  score: string;        // z.B. "2:1"
  method: "xg" | "top_scoreline";
  label: string;        // Erklärung
  outcome: "home" | "draw" | "away";
  confidence?: number;  // Wahrscheinlichkeit dieses genauen Ergebnisses
}

/**
 * Berechnet den konkreten Tipp aus einer Spielprognose.
 *
 * Primär: xG-Tipp (gerundete Expected Goals) — zeigt den Stärkeunterschied,
 * vermeidet Wiederholung gleicher Scores, intuitiver für Tipprunden.
 *
 * Sekundär: Wahrscheinlichstes Ergebnis (top_scorelines[0]) aus dem Modell.
 */
export function computeTips(pred: PredictionSummary): {
  xgTip: Tip;
  modelTip: Tip | null;
} {
  // ── xG-Tipp ─────────────────────────────────────────────────────────────
  const h = Math.round(pred.xg_home);
  const a = Math.round(pred.xg_away);
  const xgScore = `${h}:${a}`;
  const xgOutcome: Tip["outcome"] = h > a ? "home" : h < a ? "away" : "draw";

  const xgTip: Tip = {
    score: xgScore,
    method: "xg",
    label: `xG ${pred.xg_home.toFixed(2)} : ${pred.xg_away.toFixed(2)}`,
    outcome: xgOutcome,
  };

  // ── Modell-Tipp (wahrscheinlichstes Ergebnis) ────────────────────────────
  let modelTip: Tip | null = null;
  if (pred.top_scoreline) {
    const [sh, sa] = pred.top_scoreline.split(":").map(Number);
    const mOutcome: Tip["outcome"] = sh > sa ? "home" : sh < sa ? "away" : "draw";
    modelTip = {
      score: pred.top_scoreline,
      method: "top_scoreline",
      label: "wahrscheinlichstes Ergebnis",
      outcome: mOutcome,
    };
  }

  return { xgTip, modelTip };
}

// ── Tipp-Auswertung gegen das tatsächliche Ergebnis (Kicktipp-Standard) ──────
// Exakt = 4 · gleiche Tordifferenz (inkl. beide Remis) = 3 · Tendenz = 2 · sonst 0.
// Identisch zur Backend-Logik (tipping_engine._points).
export interface TipEval {
  points: number;
  kind: "exact" | "diff" | "tendency" | "miss";
  label: string;
}

export function evaluateTip(
  tipScore: string,
  result: { home_goals: number; away_goals: number },
): TipEval | null {
  const parts = tipScore.split(":").map((n) => parseInt(n.trim(), 10));
  if (parts.length !== 2 || parts.some((n) => Number.isNaN(n))) return null;
  const [ti, tj] = parts;
  const ai = result.home_goals;
  const aj = result.away_goals;
  if (ti === ai && tj === aj) return { points: 4, kind: "exact", label: "Exakt" };
  const td = ti - tj;
  const ad = ai - aj;
  if (td === ad) return { points: 3, kind: "diff", label: "Tordifferenz" };
  if ((td > 0 && ad > 0) || (td < 0 && ad < 0)) return { points: 2, kind: "tendency", label: "Tendenz" };
  return { points: 0, kind: "miss", label: "Daneben" };
}

export function evalColor(kind: TipEval["kind"]) {
  return kind === "exact"
    ? "text-green-400"
    : kind === "diff"
    ? "text-emerald-400"
    : kind === "tendency"
    ? "text-yellow-400"
    : "text-red-400";
}

export function outcomeColor(outcome: Tip["outcome"]) {
  return outcome === "home" ? "text-blue-400" : outcome === "away" ? "text-red-400" : "text-yellow-400";
}

export function outcomeBg(outcome: Tip["outcome"]) {
  return outcome === "home" ? "bg-blue-900/30 border-blue-700" : outcome === "away" ? "bg-red-900/30 border-red-700" : "bg-yellow-900/30 border-yellow-700";
}
